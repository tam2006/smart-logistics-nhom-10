import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import app as app_module
import session_routes


BASE = Path(__file__).resolve().parent
ORIGINAL_DB = BASE / "instance" / "smartlogistics.db"


class DestinationErrorTests(unittest.TestCase):
    def setUp(self):
        # Mỗi bài kiểm tra dùng một bản sao database riêng.
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

        self.test_db = (
            Path(self.temp_directory.name) / "test_smartlogistics.db"
        )

        # Chỉ mở database chính ở chế độ đọc.
        source = sqlite3.connect(
            ORIGINAL_DB.resolve().as_uri() + "?mode=ro",
            uri=True,
        )

        try:
            target = sqlite3.connect(self.test_db)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()

        # Chuyển các kết nối của ứng dụng sang database tạm.
        app_db_patch = patch.object(
            app_module,
            "DB_PATH",
            self.test_db,
        )
        app_db_patch.start()
        self.addCleanup(app_db_patch.stop)

        session_db_patch = patch.object(
            session_routes,
            "DB_PATH",
            self.test_db,
        )
        session_db_patch.start()
        self.addCleanup(session_db_patch.stop)

        self.client = app_module.app.test_client()

        response = self.client.post(
            "/api/sessions",
            json={"name": "Temporary destination test"},
        )

        self.assertEqual(
            response.status_code,
            201,
            response.get_data(as_text=True),
        )

        self.session_id = response.get_json()["id"]

    def add_parcel(self, code, destination, destination_key, state):
        conn = sqlite3.connect(self.test_db)

        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO parcels (
                        code,
                        order_id,
                        destination,
                        destination_key,
                        state,
                        source_status,
                        subset
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        code,
                        f"temporary-test-{uuid4()}",
                        destination,
                        destination_key,
                        state,
                        "delivered",
                        "demo",
                    ),
                )
        finally:
            conn.close()

    def get_history(self):
        response = self.client.get(
            "/api/history",
            query_string={"session_id": self.session_id},
        )

        self.assertEqual(response.status_code, 200)

        return response.get_json()["history"]

    def check_error(self, code, expected_status):
        # Tra cứu chỉ trả lỗi, không ghi lịch sử.
        lookup = self.client.get(f"/api/parcels/{code}")

        self.assertEqual(lookup.status_code, 422)
        self.assertEqual(
            lookup.get_json()["status"],
            expected_status,
        )
        self.assertEqual(self.get_history(), [])

        request_id = str(uuid4())

        payload = {
            "session_id": self.session_id,
            "request_id": request_id,
            "code": code,
            "source": "api",
        }

        # Bước 1: chuẩn bị, chưa ghi lịch sử hoàn tất.
        prepared = self.client.post(
            "/api/history/prepare",
            json=payload,
        )

        self.assertEqual(
            prepared.status_code,
            201,
            prepared.get_data(as_text=True),
        )

        data = prepared.get_json()

        self.assertEqual(data["phase"], "pending")
        self.assertEqual(
            data["result"]["status"],
            expected_status,
        )
        self.assertIs(data["result"]["success"], False)
        self.assertIsNone(data["result"]["gate"])

        # Chưa xác nhận hoàn tất nên lịch sử vẫn trống.
        self.assertEqual(self.get_history(), [])

        # Gửi lại bước chuẩn bị phải giữ nguyên lượt đang chờ.
        prepare_retry = self.client.post(
            "/api/history/prepare",
            json=payload,
        )

        self.assertEqual(prepare_retry.status_code, 200)
        self.assertEqual(prepare_retry.get_json(), data)
        self.assertEqual(self.get_history(), [])

        # Bước 2: giả lập giao diện xác nhận đã xử lý xong.
        # Đây là kiểm thử API, không chạy hoạt ảnh trình duyệt.
        response = self.client.post(
            f"/api/history/{request_id}/complete",
        )

        self.assertEqual(
            response.status_code,
            201,
            response.get_data(as_text=True),
        )

        result = response.get_json()

        self.assertEqual(result["request_id"], request_id)
        self.assertEqual(result["code"], code)
        self.assertEqual(result["status"], expected_status)
        self.assertIs(result["success"], False)
        self.assertIsNone(result["gate"])

        # Gửi lại xác nhận không được thêm bản ghi.
        retry = self.client.post(
            f"/api/history/{request_id}/complete",
        )

        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.get_json(), result)

        # Lượt lỗi phải được lưu đúng một lần.
        history = self.get_history()

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], result["id"])
        self.assertEqual(history[0]["request_id"], request_id)
        self.assertEqual(
            history[0]["status"],
            expected_status,
        )
        self.assertIs(history[0]["success"], False)
        self.assertIsNone(history[0]["gate"])

    def test_missing_destination(self):
        self.add_parcel(
            code="KH901",
            destination=None,
            destination_key=None,
            state=None,
        )

        self.check_error(
            code="KH901",
            expected_status="missing_destination",
        )

    def test_unconfigured_destination(self):
        # Bảo đảm điểm đến thử nghiệm không có quy tắc
        # trong database tạm.
        conn = sqlite3.connect(self.test_db)

        try:
            with conn:
                conn.execute(
                    """
                    DELETE FROM routing_rules
                    WHERE destination_key = ? AND state = ?
                    """,
                    ("curitiba", "PR"),
                )
        finally:
            conn.close()

        self.add_parcel(
            code="KH902",
            destination="Curitiba",
            destination_key="curitiba",
            state="PR",
        )

        self.check_error(
            code="KH902",
            expected_status="unconfigured_destination",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)