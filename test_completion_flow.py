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


class QRMeasurementTests(unittest.TestCase):
    # Dùng lại database tạm và ứng dụng thử ở trên.
    # Không kế thừa lớp cũ để tránh chạy lặp bài thử.
    setUp = CompletionTests.setUp
    tearDown = CompletionTests.tearDown
    payload = CompletionTests.payload
    prepare = CompletionTests.prepare
    counts = CompletionTests.counts

    def measurement(self, **changes):
        data = {
            "measurement_version": 1,
            "mode": "batch",
            "image_name": "KH001.png",
            "image_sha256": "a" * 64,
            "read_ms": 12.5,
            "prepare_ms": 8.0,
            "pipeline_ms": 25.0,
            "animation_ms": 1800.0,
            "valid": True,
            "invalid_reason": None,
        }

        data.update(changes)
        return data

    def complete(self, payload, measurement):
        return self.client.post(
            f"/api/history/{payload['request_id']}/complete",
            json={"measurement": measurement},
        )

    def saved_measurement(self, payload):
        response = self.client.get(
            f"/api/history/{payload['request_id']}/measurement"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["request_id"],
            payload["request_id"],
        )

        return response.get_json()["measurement"]

    def measurement_count(self):
        with contextlib.closing(
            sqlite3.connect(self.db)
        ) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM qr_measurements"
            ).fetchone()[0]

    def assert_pending_without_writes(self, payload):
        self.assertEqual(self.counts(), (0, 0))
        self.assertEqual(self.measurement_count(), 0)

        response = self.client.get(
            f"/api/sessions/{self.sid}/pending"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["pending"],
            payload,
        )

        with contextlib.closing(
            sqlite3.connect(self.db)
        ) as conn:
            row = conn.execute(
                """
                SELECT completed_at
                FROM processing_requests
                WHERE request_id = ?
                """,
                (payload["request_id"],),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertIsNone(row[0])

    def test_valid_measurement_is_saved_with_history(self):
        payload = self.payload()

        self.assertEqual(
            self.prepare(payload).status_code,
            201,
        )

        measurement = self.measurement(
            image_sha256="AB" * 32,
            image_name="  KH001.png  ",
        )

        response = self.complete(payload, measurement)

        self.assertEqual(response.status_code, 201)

        result = response.get_json()

        self.assertTrue(result["success"])
        self.assertEqual(result["gate"], 1)
        self.assertEqual(self.counts(), (1, 1))
        self.assertEqual(self.measurement_count(), 1)

        saved = self.saved_measurement(payload)

        self.assertIs(saved["valid"], True)
        self.assertEqual(saved["measurement_version"], 1)
        self.assertEqual(saved["mode"], "batch")
        self.assertEqual(saved["image_name"], "KH001.png")
        self.assertEqual(saved["image_sha256"], "ab" * 32)
        self.assertIsNone(saved["invalid_reason"])

        for key in (
            "read_ms",
            "prepare_ms",
            "pipeline_ms",
            "animation_ms",
        ):
            self.assertEqual(
                saved[key],
                measurement[key],
            )

        self.assertEqual(
            saved["created_at"],
            result["created_at"],
        )

    def test_invalid_measurements_leave_request_pending(self):
        payload = self.payload()

        self.assertEqual(
            self.prepare(payload).status_code,
            201,
        )

        cases = [
            ("null", None),
            ("array", []),
            (
                "extra_field",
                self.measurement(gate=3),
            ),
            (
                "version_bool",
                self.measurement(
                    measurement_version=True
                ),
            ),
            (
                "version_float",
                self.measurement(
                    measurement_version=1.0
                ),
            ),
            (
                "version_unsupported",
                self.measurement(
                    measurement_version=2
                ),
            ),
            (
                "mode",
                self.measurement(mode="camera"),
            ),
            (
                "name_blank",
                self.measurement(image_name="   "),
            ),
            (
                "name_long",
                self.measurement(image_name="x" * 256),
            ),
            (
                "hash_short",
                self.measurement(
                    image_sha256="a" * 63
                ),
            ),
            (
                "hash_non_hex",
                self.measurement(
                    image_sha256="z" * 64
                ),
            ),
            (
                "valid_integer",
                self.measurement(valid=1),
            ),
            (
                "valid_string",
                self.measurement(valid="true"),
            ),
            (
                "valid_with_reason",
                self.measurement(
                    invalid_reason="pause"
                ),
            ),
            (
                "invalid_no_reason",
                self.measurement(valid=False),
            ),
            (
                "invalid_blank_reason",
                self.measurement(
                    valid=False,
                    invalid_reason="  ",
                ),
            ),
            (
                "invalid_long_reason",
                self.measurement(
                    valid=False,
                    invalid_reason="x" * 501,
                ),
            ),
            (
                "pipeline_short",
                self.measurement(pipeline_ms=1),
            ),
        ]

        for key in (
            "read_ms",
            "prepare_ms",
            "pipeline_ms",
            "animation_ms",
        ):
            for label, value in (
                ("negative", -1),
                ("bool", True),
                ("string", "12"),
                ("null", None),
                ("nan", float("nan")),
                ("infinity", float("inf")),
            ):
                cases.append(
                    (
                        f"{key}_{label}",
                        self.measurement(
                            **{key: value}
                        ),
                    )
                )

        for label, measurement in cases:
            with self.subTest(case=label):
                response = self.complete(
                    payload,
                    measurement,
                )

                self.assertEqual(
                    response.status_code,
                    400,
                )
                self.assertEqual(
                    response.get_json()["status"],
                    "invalid_measurement",
                )

                self.assert_pending_without_writes(
                    payload
                )

        # Sửa số đo rồi gửi lại cùng request_id.
        self.assertEqual(
            self.complete(
                payload,
                self.measurement(),
            ).status_code,
            201,
        )

        self.assertEqual(self.counts(), (1, 1))
        self.assertEqual(self.measurement_count(), 1)

    def test_non_qr_sources_cannot_store_qr_measurement(self):
        for source in ("manual", "auto", "api"):
            with self.subTest(source=source):
                payload = self.payload()
                payload["source"] = source

                self.assertEqual(
                    self.prepare(payload).status_code,
                    201,
                )

                before = self.counts()

                response = self.complete(
                    payload,
                    self.measurement(),
                )

                self.assertEqual(
                    response.status_code,
                    400,
                )
                self.assertEqual(
                    response.get_json()["status"],
                    "invalid_input",
                )
                self.assertEqual(
                    self.counts(),
                    before,
                )
                self.assertEqual(
                    self.measurement_count(),
                    0,
                )
                self.assertEqual(
                    self.client.get(
                        f"/api/sessions/{self.sid}/pending"
                    ).get_json()["pending"],
                    payload,
                )

                # Hoàn tất không kèm số đo để
                # giải phóng lượt đang chờ.
                response = self.client.post(
                    f"/api/history/{payload['request_id']}/complete"
                )

                self.assertEqual(
                    response.status_code,
                    201,
                )
                self.assertIsNone(
                    self.saved_measurement(payload)
                )

    def test_interrupted_measurement_is_saved_as_invalid(self):
        payload = self.payload("")

        self.assertEqual(
            self.prepare(payload).status_code,
            201,
        )

        measurement = self.measurement(
            mode="single",
            image_name="no_qr.png",
            image_sha256=None,
            valid=False,
            invalid_reason=(
                "  Trang bị ẩn khi đang đo.  "
            ),
            read_ms=None,
            prepare_ms=None,
            pipeline_ms=None,
            animation_ms=None,
        )

        response = self.complete(
            payload,
            measurement,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json()["status"],
            "qr_unreadable",
        )
        self.assertFalse(
            response.get_json()["success"]
        )
        self.assertEqual(self.counts(), (1, 0))

        saved = self.saved_measurement(payload)

        self.assertIs(saved["valid"], False)
        self.assertEqual(
            saved["invalid_reason"],
            "Trang bị ẩn khi đang đo.",
        )
        self.assertIsNone(saved["image_sha256"])

        for key in (
            "read_ms",
            "prepare_ms",
            "pipeline_ms",
            "animation_ms",
        ):
            self.assertIsNone(saved[key])

    def test_legacy_complete_without_measurement_still_works(self):
        payload = self.payload()

        self.assertEqual(
            self.prepare(payload).status_code,
            201,
        )

        response = self.client.post(
            f"/api/history/{payload['request_id']}/complete"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.counts(), (1, 1))
        self.assertEqual(self.measurement_count(), 0)
        self.assertIsNone(
            self.saved_measurement(payload)
        )

    def test_retry_after_close_does_not_overwrite_measurement(self):
        payload = self.payload()

        self.assertEqual(
            self.prepare(payload).status_code,
            201,
        )

        first = self.complete(
            payload,
            self.measurement(),
        )

        self.assertEqual(first.status_code, 201)

        saved = self.saved_measurement(payload)

        self.assertEqual(
            self.client.post(
                f"/api/sessions/{self.sid}/close"
            ).status_code,
            200,
        )

        retry = self.complete(
            payload,
            self.measurement(
                image_name="changed.png",
                pipeline_ms=999,
            ),
        )

        self.assertEqual(retry.status_code, 200)
        self.assertEqual(
            retry.get_json(),
            first.get_json(),
        )
        self.assertEqual(
            self.saved_measurement(payload),
            saved,
        )
        self.assertEqual(self.counts(), (1, 1))
        self.assertEqual(self.measurement_count(), 1)

    def assert_atomic_retry(self, trigger_sql):
        payload = self.payload()

        self.assertEqual(
            self.prepare(payload).status_code,
            201,
        )

        with contextlib.closing(
            sqlite3.connect(self.db)
        ) as conn:
            with conn:
                conn.execute(trigger_sql)

        # TESTING=True làm Flask chuyển lỗi SQLite
        # ra cho bài thử bắt.
        # Trigger chỉ tồn tại trong database tạm.
        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "forced_qr_test_failure",
        ):
            self.complete(
                payload,
                self.measurement(),
            )

        # Lịch sử, số đo và trạng thái hoàn tất
        # phải cùng hoàn tác.
        self.assert_pending_without_writes(payload)

        with contextlib.closing(
            sqlite3.connect(self.db)
        ) as conn:
            with conn:
                conn.execute(
                    "DROP TRIGGER force_qr_test_failure"
                )

        # Bỏ lỗi giả lập rồi gửi lại cùng request_id.
        response = self.complete(
            payload,
            self.measurement(),
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(self.counts(), (1, 1))
        self.assertEqual(self.measurement_count(), 1)
        self.assertIsNotNone(
            self.saved_measurement(payload)
        )

        pending = self.client.get(
            f"/api/sessions/{self.sid}/pending"
        )

        self.assertEqual(pending.status_code, 200)
        self.assertIsNone(pending.get_json()["pending"])

        with contextlib.closing(
            sqlite3.connect(self.db)
        ) as conn:
            completed_at = conn.execute(
                """
                SELECT completed_at
                FROM processing_requests
                WHERE request_id = ?
                """,
                (payload["request_id"],),
            ).fetchone()[0]

        self.assertIsNotNone(completed_at)

    def test_measurement_insert_failure_rolls_back_history(self):
        self.assert_atomic_retry("""
            CREATE TRIGGER force_qr_test_failure
            BEFORE INSERT ON qr_measurements
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'forced_qr_test_failure'
                );

        """)

    def test_completion_update_failure_rolls_back_history_and_measurement(self):
        self.assert_atomic_retry("""
            CREATE TRIGGER force_qr_test_failure
            BEFORE UPDATE OF completed_at
            ON processing_requests
            WHEN NEW.completed_at IS NOT NULL
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'forced_qr_test_failure'
                );
            END
        """)


if __name__ == "__main__":
    unittest.main(verbosity=2)