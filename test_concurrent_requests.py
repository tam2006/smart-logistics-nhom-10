import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import app as app_module
import test_destination_errors as destination_tests


class ConcurrentRequestTests(unittest.TestCase):
    # Mỗi bài dùng database tạm, không ghi vào database chính.
    setUp = destination_tests.DestinationErrorTests.setUp

    def make_payload(self, request_id=None):
        return {
            "session_id": self.session_id,
            "request_id": request_id or str(uuid4()),
            "code": "KH001",
            "source": "api",
        }

    def prepare(self, payload):
        return self.client.post(
            "/api/history/prepare", json=payload,
        )

    def complete(self, payload):
        return self.client.post(
            f"/api/history/{payload['request_id']}/complete",
        )

    def send_together(self, payloads, phase="prepare"):
        if phase not in ("prepare", "complete"):
            raise ValueError("phase phải là prepare hoặc complete.")

        barrier = Barrier(len(payloads))

        def send(payload):
            # Mỗi luồng có client riêng, cùng chờ trước khi gửi.
            with app_module.app.test_client() as client:
                barrier.wait(timeout=10)

                if phase == "prepare":
                    response = client.post(
                        "/api/history/prepare", json=payload,
                    )
                else:
                    response = client.post(
                        f"/api/history/{payload['request_id']}/complete",
                    )

                return response.status_code, response.get_json()

        with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
            futures = [pool.submit(send, p) for p in payloads]
            return [future.result(timeout=20) for future in futures]

    def get_history(self):
        response = self.client.get(
            "/api/history",
            query_string={"session_id": self.session_id},
        )

        self.assertEqual(response.status_code, 200)

        return response.get_json()["history"]

    def test_two_requests_same_parcel(self):
        # Hai lượt quét khác nhau: cùng kiện, khác request_id.
        payloads = [self.make_payload(), self.make_payload()]
        results = self.send_together(payloads)

        # Mỗi phiên chỉ cho phép một lượt đang chờ hoàn tất.
        self.assertEqual(
            sorted(code for code, _ in results),
            [201, 409],
            results,
        )
        self.assertEqual(self.get_history(), [])

        accepted_index = next(
            i for i, (code, _) in enumerate(results)
            if code == 201
        )
        waiting_index = 1 - accepted_index

        accepted = payloads[accepted_index]
        waiting = payloads[waiting_index]
        data = results[accepted_index][1]

        self.assertEqual(data["phase"], "pending")
        self.assertEqual(data["result"]["status"], "ready")
        self.assertIs(data["result"]["success"], False)

        self.assertEqual(
            results[waiting_index][1]["status"],
            "session_busy",
        )

        # Hoàn tất lượt được nhận trước.
        first = self.complete(accepted)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.get_json()["status"], "success")
        self.assertIs(first.get_json()["success"], True)

        # Thử lại lượt còn lại: bây giờ phải nhận ra kiện trùng.
        prepared = self.prepare(waiting)

        self.assertEqual(prepared.status_code, 201)
        self.assertEqual(
            prepared.get_json()["result"]["status"],
            "duplicate",
        )

        second = self.complete(waiting)

        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.get_json()["status"], "duplicate")
        self.assertIs(second.get_json()["success"], False)
        self.assertIsNone(second.get_json()["gate"])

        history = self.get_history()

        self.assertEqual(len(history), 2)
        self.assertEqual(
            sum(row["success"] for row in history),
            1,
        )
        self.assertEqual(
            {row["request_id"] for row in history},
            {p["request_id"] for p in payloads},
        )

    def test_same_request_sent_together(self):
        # Hai bản gửi của CÙNG một lượt, giống request_id.
        payload = self.make_payload()
        copies = [dict(payload), dict(payload)]

        prepared = self.send_together(copies)

        self.assertEqual(
            sorted(code for code, _ in prepared),
            [200, 201],
            prepared,
        )
        self.assertEqual(prepared[0][1], prepared[1][1])
        self.assertEqual(prepared[0][1]["phase"], "pending")
        self.assertEqual(
            prepared[0][1]["result"]["request_id"],
            payload["request_id"],
        )
        self.assertEqual(self.get_history(), [])

        # Hai xác nhận đồng thời cũng chỉ ghi một lần.
        completed = self.send_together(
            copies,
            phase="complete",
        )

        self.assertEqual(
            sorted(code for code, _ in completed),
            [200, 201],
            completed,
        )
        self.assertEqual(completed[0][1], completed[1][1])

        result = completed[0][1]

        self.assertEqual(result["status"], "success")
        self.assertIs(result["success"], True)

        history = self.get_history()

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], result["id"])
        self.assertEqual(
            history[0]["request_id"],
            payload["request_id"],
        )
        self.assertIs(history[0]["success"], True)

    def test_retry_saved_request_after_close(self):
        payload = self.make_payload()

        prepared = self.prepare(payload)

        self.assertEqual(prepared.status_code, 201)
        self.assertEqual(self.get_history(), [])

        first = self.complete(payload)

        self.assertEqual(first.status_code, 201)

        saved = first.get_json()

        self.assertIs(saved["success"], True)

        closed = self.client.post(
            f"/api/sessions/{self.session_id}/close",
        )

        self.assertEqual(closed.status_code, 200)
        self.assertEqual(
            closed.get_json()["status"],
            "closed",
        )

        # Phiên đã đóng vẫn cho xem lại kết quả của yêu cầu cũ.
        retry_prepare = self.prepare(payload)

        self.assertEqual(retry_prepare.status_code, 200)
        self.assertEqual(
            retry_prepare.get_json()["phase"],
            "completed",
        )
        self.assertEqual(
            retry_prepare.get_json()["result"],
            saved,
        )

        retry_complete = self.complete(payload)

        self.assertEqual(retry_complete.status_code, 200)
        self.assertEqual(retry_complete.get_json(), saved)

        # Nhưng yêu cầu mới trong phiên đã đóng phải bị chặn.
        new_request = self.prepare(self.make_payload())

        self.assertEqual(new_request.status_code, 409)
        self.assertEqual(
            new_request.get_json()["status"],
            "session_closed",
        )
        self.assertEqual(len(self.get_history()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)