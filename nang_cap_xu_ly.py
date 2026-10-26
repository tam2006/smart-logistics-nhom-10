import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "instance" / "smartlogistics.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS processing_requests (
    request_id TEXT PRIMARY KEY,
    request_fingerprint TEXT NOT NULL,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    code TEXT NOT NULL,
    source TEXT NOT NULL
        CHECK(source IN ('manual', 'qr', 'auto', 'api')),
    outcome_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
"""

METRICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS qr_measurements (
    request_id TEXT PRIMARY KEY NOT NULL
        REFERENCES history(request_id),

    measurement_version INTEGER NOT NULL DEFAULT 1
        CHECK(measurement_version = 1),

    mode TEXT NOT NULL
        CHECK(mode IN ('single', 'batch')),

    image_name TEXT NOT NULL
        CHECK(length(trim(image_name)) > 0),

    image_sha256 TEXT CHECK(
        image_sha256 IS NULL OR (
            length(image_sha256) = 64
            AND image_sha256 NOT GLOB '*[^0-9a-f]*'
        )
    ),

    read_ms REAL
        CHECK(read_ms IS NULL OR read_ms >= 0),

    prepare_ms REAL
        CHECK(prepare_ms IS NULL OR prepare_ms >= 0),

    pipeline_ms REAL
        CHECK(pipeline_ms IS NULL OR pipeline_ms >= 0),

    animation_ms REAL
        CHECK(animation_ms IS NULL OR animation_ms >= 0),

    valid INTEGER NOT NULL
        CHECK(valid IN (0, 1)),

    invalid_reason TEXT,
    created_at TEXT NOT NULL,

    CHECK(
        valid = 0 OR (
            read_ms IS NOT NULL
            AND prepare_ms IS NOT NULL
            AND pipeline_ms IS NOT NULL
            AND animation_ms IS NOT NULL
            AND pipeline_ms >= read_ms
            AND pipeline_ms >= prepare_ms
        )
    ),

    CHECK(
        (valid = 1 AND invalid_reason IS NULL)
        OR (
            valid = 0
            AND invalid_reason IS NOT NULL
            AND length(trim(invalid_reason)) > 0
        )
    )
);
"""


def upgrade(database):
    database = Path(database)

    if not database.is_file():
        raise FileNotFoundError(
            "Không tìm thấy database. Kiểm tra đường dẫn; "
            "không khởi tạo lại nếu đang có dữ liệu cần giữ."
        )

    with closing(
        sqlite3.connect(
            database.resolve().as_uri() + "?mode=rw",
            uri=True,
            timeout=10,
        )
    ) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table'"
            )
        }

        if not {"sessions", "history"}.issubset(tables):
            raise ValueError(
                "Database chưa có bảng sessions và history. "
                "Cần chuẩn bị hai bảng này trước khi nâng cấp."
            )

        stamp = datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S_%fZ"
        )

        backup = database.with_name(
            f"{database.stem}_backup_{stamp}.db"
        )

        # Sao lưu đầy đủ trước khi thay đổi cấu trúc.
        with closing(sqlite3.connect(backup)) as target:
            conn.backup(target)

        # Các thay đổi cùng thành công hoặc cùng được hoàn tác.
        with conn:
            conn.execute("BEGIN IMMEDIATE")

            conn.execute(SCHEMA)

            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    one_pending_per_session
                ON processing_requests(session_id)
                WHERE completed_at IS NULL
            """)

            conn.execute(METRICS_SCHEMA)

    return backup


if __name__ == "__main__":
    try:
        backup = upgrade(DB_PATH)

    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"Nâng cấp chưa hoàn tất: {error}")
        raise SystemExit(1)

    print(f"Đã sao lưu: {backup}")
    print("Đã chuẩn bị bảng processing_requests.")
    print("Đã chuẩn bị bảng qr_measurements để lưu số đo QR.")
    print("Giữ nguyên kiện hàng, quy tắc, phiên và lịch sử cũ.")
    print(
        "Chưa thu thập số đo mới; "
        "cần cập nhật API và app.js tiếp theo."
    )