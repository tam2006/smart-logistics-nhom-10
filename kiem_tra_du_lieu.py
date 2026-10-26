import csv
from pathlib import Path

# Thư mục chứa tệp code
BASE = Path(__file__).resolve().parent

# Thư mục chứa dữ liệu gốc
RAW = BASE / "data" / "raw"


def kiem_tra(ten_file, cot_ma):
    duong_dan = RAW / ten_file

    if not duong_dan.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy tệp: {duong_dan}"
        )

    with duong_dan.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        reader = csv.DictReader(f)
        cac_cot = reader.fieldnames
        du_lieu = list(reader)

    print(f"\n===== {ten_file} =====")
    print(f"Số dòng dữ liệu: {len(du_lieu):,}")
    print(f"Số cột: {len(cac_cot)}")

    print("\nSố ô trống theo từng cột:")
    for cot in cac_cot:
        so_trong = sum(
            dong[cot] is None or dong[cot].strip() == ""
            for dong in du_lieu
        )
        print(f"  {cot}: {so_trong:,}")

    # Đếm những dòng lặp dư sau lần xuất hiện đầu tiên
    cac_dong = [
        tuple(dong[cot] for cot in cac_cot)
        for dong in du_lieu
    ]
    trung_dong = len(cac_dong) - len(set(cac_dong))
    print(f"\nSố dòng lặp dư, giống toàn bộ cột: {trung_dong:,}")

    # Kiểm tra mã định danh bị lặp, không tính mã trống
    cac_ma = [
        dong[cot_ma]
        for dong in du_lieu
        if dong[cot_ma] and dong[cot_ma].strip()
    ]
    trung_ma = len(cac_ma) - len(set(cac_ma))
    print(f"Số lượt mã {cot_ma} lặp dư: {trung_ma:,}")


kiem_tra("olist_orders_dataset.csv", "order_id")
kiem_tra("olist_customers_dataset.csv", "customer_id")

print("\nKiểm tra hoàn tất. Chưa thay đổi dữ liệu gốc.")