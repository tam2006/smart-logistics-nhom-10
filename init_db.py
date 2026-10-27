import csv
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROCESSED = BASE / "data" / "processed"
DB_FOLDER = BASE / "instance"
DB_PATH = DB_FOLDER / "smartlogistics.db"


def doc_csv(ten_file):
    with (PROCESSED / ten_file).open(
        encoding="utf-8-sig", newline=""
    ) as f:
        return list(csv.DictReader(f))


def main():
    parcels = doc_csv("parcels.csv")
    rules = doc_csv("routing_rules.csv")

    # Kiểm tra dữ liệu trước khi nạp
    if len(parcels) != 60 or len(rules) != 3:
        raise ValueError("Cần đúng 60 kiện và 3 quy tắc.")

    if len({p["code"] for p in parcels}) != 60:
        raise ValueError("Có mã kiện bị trùng.")

    if len({p["order_id"] for p in parcels}) != 60:
        raise ValueError("Có mã đơn nguồn bị trùng.")

    rule_keys = [
        (r["destination_key"], r["state"]) for r in rules
    ]

    if len(set(rule_keys)) != 3:
        raise ValueError("Có quy tắc điểm đến bị trùng.")

    if {int(r["gate"]) for r in rules} != {1, 2, 3}:
        raise ValueError("Quy tắc phải có đủ cửa 1, 2 và 3.")

    for p in parcels:
        if not all(p[k].strip() for k in [
            "code", "order_id", "destination",
            "destination_key", "state", "source_status", "subset",
        ]):
            raise ValueError(f"Kiện {p['code']} có trường bị trống.")

        if p["subset"] not in {"demo", "final_test"}:
            raise ValueError(f"Kiện {p['code']} có bộ dữ liệu không hợp lệ.")

        if (p["destination_key"], p["state"]) not in rule_keys:
            raise ValueError(f"Kiện {p['code']} chưa có quy tắc cửa.")

    DB_FOLDER.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS routing_rules (
                    destination_key TEXT NOT NULL,
                    state TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    gate INTEGER NOT NULL CHECK (gate IN (1, 2, 3)),
                    PRIMARY KEY (destination_key, state)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS parcels (
                    code TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL UNIQUE,
                    destination TEXT,
                    destination_key TEXT,
                    state TEXT,
                    source_status TEXT NOT NULL,
                    subset TEXT NOT NULL
                        CHECK (subset IN ('demo', 'final_test'))
                )
            """)

            # Nạp mới hoặc cập nhật theo khóa, không nhân đôi bản ghi
            conn.executemany("""
                INSERT INTO routing_rules (
                    destination_key, state, destination, gate
                )
                VALUES (
                    :destination_key, :state, :destination, :gate
                )
                ON CONFLICT(destination_key, state) DO UPDATE SET
                    destination = excluded.destination,
                    gate = excluded.gate
            """, rules)

            conn.executemany("""
                INSERT INTO parcels (
                    code, order_id, destination, destination_key,
                    state, source_status, subset
                )
                VALUES (
                    :code, :order_id, :destination, :destination_key,
                    :state, :source_status, :subset
                )
                ON CONFLICT(code) DO UPDATE SET
                    order_id = excluded.order_id,
                    destination = excluded.destination,
                    destination_key = excluded.destination_key,
                    state = excluded.state,
                    source_status = excluded.source_status,
                    subset = excluded.subset
            """, parcels)

        print(f"Database: {DB_PATH}")

        for subset in ["demo", "final_test"]:
            count = conn.execute(
                "SELECT COUNT(*) FROM parcels WHERE subset = ?",
                (subset,),
            ).fetchone()[0]
            print(f"Bộ {subset}: {count} kiện")

        print("\nQuy tắc phân loại:")
        for destination, state, gate in conn.execute("""
            SELECT destination, state, gate
            FROM routing_rules
            ORDER BY gate
        """):
            print(f"  {destination} ({state}) → Cửa {gate}")

        print("\nTạo và nạp database thành công.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()