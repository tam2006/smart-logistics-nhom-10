import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "instance" / "smartlogistics.db"


def main():
    if not DB_PATH.is_file():
        raise FileNotFoundError(
            "Chưa có database. Hãy chạy init_db.py trước."
        )

    conn = sqlite3.connect(DB_PATH)

    try:
        # Bật kiểm tra liên kết giữa lịch sử và phiên chạy
        conn.execute("PRAGMA foreign_keys = ON")

        with conn:
            # Mỗi bản ghi là một phiên chạy
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'closed')),
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                )
            """)

            # Mỗi bản ghi là kết quả của một lượt xử lý hoàn tất
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE,
                    request_fingerprint TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    code TEXT,
                    destination TEXT,
                    gate INTEGER CHECK (gate IN (1, 2, 3)),
                    success INTEGER NOT NULL
                        CHECK (success IN (0, 1)),
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    source TEXT NOT NULL
                        CHECK (source IN ('manual', 'qr', 'auto', 'api')),
                    decision_ms REAL NOT NULL
                        CHECK (decision_ms >= 0),
                    created_at TEXT NOT NULL,

                    FOREIGN KEY (session_id) REFERENCES sessions(id),

                    CHECK (
                        success = 0 OR (
                            status = 'success'
                            AND code IS NOT NULL
                            AND destination IS NOT NULL
                            AND gate IS NOT NULL
                        )
                    )
                )
            """)

            # Một kiện chỉ được thành công một lần trong cùng phiên
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    one_success_per_parcel_per_session
                ON history(session_id, code)
                WHERE success = 1
            """)

            # Hỗ trợ tìm lịch sử của một phiên
            conn.execute("""
                CREATE INDEX IF NOT EXISTS history_session_index
                ON history(session_id, id)
            """)

        print("Đã chuẩn bị bảng sessions và history.")

        for table in ["parcels", "routing_rules", "sessions", "history"]:
            # Tên bảng chỉ lấy từ danh sách cố định phía trên
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            print(f"  {table}: {count} bản ghi")

        print("\nDữ liệu kiện và quy tắc được giữ nguyên.")
        print("Chưa tạo phiên hoặc ghi lịch sử thử nghiệm.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()