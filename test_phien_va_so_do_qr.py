"""Bo sung kiem thu backend nhom 10 - session va so do QR.

Chay tai thu muc goc repository:
    python -m unittest -v test_phien_va_so_do_qr.py

Dung database tam cua test_completion_flow.py, KHONG sua database that.
"""

import contextlib
import sqlite3
import unittest
from uuid import uuid4

from test_completion_flow import CompletionTests


class PhienVaSoDoQRTests(unittest.TestCase):
    """Tai su dung fixture SQLite tam va Flask test client co san."""

    def setUp(self):
        CompletionTests.setUp(self)

    def tearDown(self):
        CompletionTests.tearDown(self)

    def payload(self, code="KH001", source="qr", request_id=None):
        return {
            "session_id": self.sid,
            "request_id": request_id or str(uuid4()),
            "code": code,
            "source": source,
        }

    def prepare(self, payload):
        return self.client.post("/api/history/prepare", json=payload)

    def complete(self, payload, body=None):
        url = f"/api/history/{payload['request_id']}/complete"
        if body is None:
            return self.client.post(url)
        return self.client.post(url, json=body)

    def db_count(self, table):
        # Ten bang la hang so do code cung cap, khong nhan du lieu tu client.
        if table not in {"history", "qr_measurements", "processing_requests"}:
            raise ValueError("Bang khong duoc ho tro")
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    @staticmethod
    def measurement(**overrides):
        result = {
            "measurement_version": 1,
            "mode": "single",
            "image_name": "KH001.png",
            "image_sha256": "a" * 64,
            "read_ms": 8.0,
            "prepare_ms": 4.0,
            "pipeline_ms": 12.0,
            "animation_ms": 30.0,
            "valid": True,
            "invalid_reason": None,
        }
        result.update(overrides)
        return result

    def assert_no_saved_result(self, expected_pending=1):
        self.assertEqual(self.db_count("history"), 0)
        self.assertEqual(self.db_count("qr_measurements"), 0)
        self.assertEqual(self.db_count("processing_requests"), expected_pending)

    def test_cannot_close_session_with_pending_request(self):
        payload = self.payload()
        self.assertEqual(self.prepare(payload).status_code, 201)
        response = self.client.post(f"/api/sessions/{self.sid}/close")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["status"], "session_busy")
        self.assert_no_saved_result()
        recovered = self.client.get(f"/api/sessions/{self.sid}/pending")
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.get_json()["pending"], payload)

    def test_cannot_prepare_new_request_in_closed_session(self):
        closed = self.client.post(f"/api/sessions/{self.sid}/close")
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.get_json()["status"], "closed")
        response = self.prepare(self.payload())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["status"], "session_closed")
        self.assert_no_saved_result(expected_pending=0)

    def test_valid_qr_measurement_saved_once_and_retry_is_idempotent(self):
        payload = self.payload()
        self.assertEqual(self.prepare(payload).status_code, 201)
        body = {"measurement": self.measurement()}
        first = self.complete(payload, body)
        self.assertEqual(first.status_code, 201, first.get_data(as_text=True))
        self.assertEqual(first.get_json()["status"], "success")
        self.assertEqual(self.db_count("history"), 1)
        self.assertEqual(self.db_count("qr_measurements"), 1)

        # Gui lai complete voi so do khac khong duoc ghi de.
        second = self.complete(payload, {"measurement": self.measurement(read_ms=99.0, pipeline_ms=100.0)})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json(), first.get_json())
        self.assertEqual(self.db_count("history"), 1)
        self.assertEqual(self.db_count("qr_measurements"), 1)
        measure = self.client.get(f"/api/history/{payload['request_id']}/measurement")
        self.assertEqual(measure.status_code, 200)
        self.assertEqual(measure.get_json()["measurement"]["read_ms"], 8.0)

    def test_manual_input_does_not_create_qr_measurement(self):
        payload = self.payload(source="manual")
        self.assertEqual(self.prepare(payload).status_code, 201)
        response = self.complete(payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.db_count("history"), 1)
        self.assertEqual(self.db_count("qr_measurements"), 0)
        measure = self.client.get(f"/api/history/{payload['request_id']}/measurement")
        self.assertEqual(measure.status_code, 200)
        self.assertIsNone(measure.get_json()["measurement"])

    def test_manual_input_rejects_qr_measurement_without_writing(self):
        payload = self.payload(source="manual")
        self.assertEqual(self.prepare(payload).status_code, 201)
        response = self.complete(payload, {"measurement": self.measurement()})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "invalid_input")
        self.assert_no_saved_result()
        # Loi khong lam hong request, van co the complete khong kem measurement.
        self.assertEqual(self.complete(payload).status_code, 201)
        self.assertEqual(self.db_count("history"), 1)
        self.assertEqual(self.db_count("qr_measurements"), 0)

    def test_invalid_measurement_values_are_rejected_without_writing(self):
        invalid_cases = [
            ("negative", {"read_ms": -1}),
            ("text", {"read_ms": "12"}),
            ("boolean", {"read_ms": True}),
            ("nan", {"read_ms": float("nan")}),
            ("infinite", {"read_ms": float("inf")}),
            ("invalid_valid_flag", {"valid": "true"}),
            ("invalid_mode", {"mode": "unknown"}),
            ("invalid_digest", {"image_sha256": "abc"}),
            ("pipeline_too_small", {"pipeline_ms": 2}),
            ("unexpected_field", {"other_field": 1}),
            ("invalid_reason_for_valid", {"invalid_reason": "stopped"}),
            ("missing_reason_for_invalid", {"valid": False, "invalid_reason": None}),
        ]
        for title, overrides in invalid_cases:
            with self.subTest(case=title):
                payload = self.payload()
                self.assertEqual(self.prepare(payload).status_code, 201)
                result = self.complete(payload, {"measurement": self.measurement(**overrides)})
                self.assertEqual(result.status_code, 400, (title, result.get_data(as_text=True)))
                self.assertEqual(result.get_json()["status"], "invalid_measurement")
                self.assertEqual(self.db_count("history"), 0)
                self.assertEqual(self.db_count("qr_measurements"), 0)
                # Ket thuc request dang cho de tiep tuc test case ke tiep.
                self.assertEqual(self.complete(payload).status_code, 201)
                # Xoa chi du lieu thu tren database tam de assert doc lap.
                with contextlib.closing(sqlite3.connect(self.db)) as conn:
                    with conn:
                        conn.execute("DELETE FROM qr_measurements")
                        conn.execute("DELETE FROM history")
                        conn.execute("DELETE FROM processing_requests")

    def test_interrupted_qr_measurement_is_marked_invalid(self):
        payload = self.payload()
        self.assertEqual(self.prepare(payload).status_code, 201)
        body = {"measurement": self.measurement(
            valid=False, invalid_reason="Camera interrupted",
            read_ms=None, prepare_ms=None, pipeline_ms=None,
            animation_ms=None,
        )}
        finished = self.complete(payload, body)
        self.assertEqual(finished.status_code, 201, finished.get_data(as_text=True))
        measure = self.client.get(f"/api/history/{payload['request_id']}/measurement")
        self.assertEqual(measure.status_code, 200)
        saved = measure.get_json()["measurement"]
        self.assertIs(saved["valid"], False)
        self.assertEqual(saved["invalid_reason"], "Camera interrupted")
        self.assertIsNone(saved["read_ms"])
        self.assertEqual(self.db_count("history"), 1)
        self.assertEqual(self.db_count("qr_measurements"), 1)

    def test_reject_invalid_complete_body_without_writing(self):
        payload = self.payload()
        self.assertEqual(self.prepare(payload).status_code, 201)
        result = self.complete(payload, {"unexpected": 1})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.get_json()["status"], "invalid_input")
        self.assert_no_saved_result()


if __name__ == "__main__":
    unittest.main(verbosity=2)
