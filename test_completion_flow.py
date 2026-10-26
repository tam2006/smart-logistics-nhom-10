import contextlib
import io
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from flask import Flask

import init_tracking
import session_routes

from history_routes import history_api
from nang_cap_xu_ly import upgrade


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.db"

        # closing đóng kết nối thật sự sau khi tạo dữ liệu thử.
        with contextlib.closing(
            sqlite3.connect(self.db)
        ) as conn:
            conn.executescript("""
                CREATE TABLE parcels (
                    code TEXT PRIMARY KEY,
                    destination TEXT,
                    destination_key TEXT,
                    state TEXT
                );

                CREATE TABLE routing_rules (
                    destination_key TEXT,
                    state TEXT,
                    gate INTEGER
                );

                INSERT INTO parcels
                VALUES ('KH001','São Paulo','sao paulo','SP');

                INSERT INTO parcels
                VALUES ('KH002','Rio de Janeiro','rio','RJ');

                INSERT INTO parcels
                VALUES ('KH901',NULL,NULL,NULL);

                INSERT INTO parcels
                VALUES ('KH902','Curitiba','curitiba','PR');

                INSERT INTO routing_rules
                VALUES ('sao paulo','SP',1);

                INSERT INTO routing_rules
                VALUES ('rio','RJ',2);
            """)

        with patch.object(init_tracking, "DB_PATH", self.db):
            with contextlib.redirect_stdout(io.StringIO()):
                init_tracking.main()

        upgrade(self.db)

        self.db_patch = patch.object(
            session_routes,
            "DB_PATH",
            self.db,
        )
        self.db_patch.start()

        self.app = Flask(__name__)
        self.app.config["TESTING"] = True

        self.app.register_blueprint(
            session_routes.session_api
        )
        self.app.register_blueprint(history_api)

        self.client = self.app.test_client()

        response = self.client.post(
            "/api/sessions",
            json={"name": "test"},
        )

        self.sid = response.get_json()["id"]

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def payload(self, code="KH001"):
        return dict(
            session_id=self.sid,
            request_id=str(uuid4()),
            code=code,
            source="qr",
        )

    def prepare(self, payload):
        return self.client.post(
            "/api/history/prepare",
            json=payload,
        )

    def finish(self, payload):
        return self.client.post(
            f"/api/history/{payload['request_id']}/complete"
        )

    def counts(self):
        with contextlib.closing(
            sqlite3.connect(self.db)
        ) as conn:
            return conn.execute("""
                SELECT COUNT(*), COALESCE(SUM(success), 0)
                FROM history
            """).fetchone()

    def test_wait_then_complete_and_retry_after_close(self):
        payload = self.payload()
        result = self.prepare(payload)

        self.assertEqual(result.status_code, 201)

        self.assertEqual(
            result.get_json()["result"]["status"],
            "ready",
        )

        self.assertFalse(
            result.get_json()["result"]["success"]
        )

        self.assertEqual(self.counts(), (0, 0))

        self.assertEqual(
            self.prepare(payload).status_code,
            200,
        )

        self.assertEqual(
            self.client.post(
                f"/api/sessions/{self.sid}/close"
            ).status_code,
            409,
        )

        self.assertEqual(
            self.finish(payload).status_code,
            201,
        )

        self.assertEqual(
            self.finish(payload).status_code,
            200,
        )

        self.assertEqual(self.counts(), (1, 1))

        self.assertEqual(
            self.client.post(
                f"/api/sessions/{self.sid}/close"
            ).status_code,
            200,
        )

        self.assertEqual(
            self.prepare(payload).get_json()["phase"],
            "completed",
        )

        self.assertEqual(
            self.finish(payload).status_code,
            200,
        )

        self.assertEqual(
            self.prepare(self.payload()).status_code,
            409,
        )

    def test_duplicate_does_not_add_success(self):
        payload = self.payload()
        self.prepare(payload)
        self.finish(payload)

        payload = self.payload()
        self.prepare(payload)

        result = self.finish(payload).get_json()

        self.assertEqual(result["status"], "duplicate")
        self.assertIsNone(result["gate"])
        self.assertEqual(self.counts(), (2, 1))

    def test_pending_recovery_busy_and_conflict(self):
        payload = self.payload()
        self.prepare(payload)

        recovered = self.client.get(
            f"/api/sessions/{self.sid}/pending"
        ).get_json()

        self.assertEqual(
            recovered["pending"],
            payload,
        )

        self.assertEqual(
            self.prepare(
                self.payload("KH002")
            ).get_json()["status"],
            "session_busy",
        )

        self.assertEqual(
            self.prepare({
                **payload,
                "code": "KH002",
            }).get_json()["status"],
            "request_id_conflict",
        )

    def test_errors_go_to_history_without_success(self):
        cases = [
            ("", "qr_unreadable"),
            ("ABC123", "invalid_code"),
            ("KH999", "not_found"),
            ("KH901", "missing_destination"),
            ("KH902", "unconfigured_destination"),
        ]

        for code, expected in cases:
            with self.subTest(code=code):
                payload = self.payload(code)
                self.prepare(payload)

                result = self.finish(payload).get_json()

                self.assertEqual(
                    result["status"],
                    expected,
                )

                self.assertFalse(result["success"])
                self.assertIsNone(result["gate"])

        self.assertEqual(self.counts(), (5, 0))

    def test_parallel_same_request_only_one_record(self):
        payload = self.payload()

        def prepare_once(_):
            with self.app.test_client() as client:
                response = client.post(
                    "/api/history/prepare",
                    json=payload,
                )
                return response.status_code

        def finish_once(_):
            with self.app.test_client() as client:
                response = client.post(
                    f"/api/history/{payload['request_id']}/complete"
                )
                return response.status_code

        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(
                sorted(
                    pool.map(prepare_once, range(2))
                ),
                [200, 201],
            )

        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(
                sorted(
                    pool.map(finish_once, range(2))
                ),
                [200, 201],
            )

        self.assertEqual(self.counts(), (1, 1))

    def test_backup_and_repeated_upgrade_keep_history(self):
        payload = self.payload()

        self.prepare(payload)
        self.finish(payload)

        backup = upgrade(self.db)

        self.assertEqual(self.counts(), (1, 1))

        with contextlib.closing(
            sqlite3.connect(backup)
        ) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM history"
                ).fetchone()[0],
                1,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)