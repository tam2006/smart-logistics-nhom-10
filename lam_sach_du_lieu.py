import csv
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
OUTPUT = BASE / "data" / "processed"


def doc_csv(ten_file):
    with (RAW / ten_file).open(
        encoding="utf-8-sig", newline=""
    ) as f:
        return list(csv.DictReader(f))


def chuan_hoa_thanh_pho(ten):
    # Bỏ dấu, chuyển chữ thường và gộp khoảng trắng
    ten = unicodedata.normalize("NFKD", ten)
    ten = "".join(
        ky_tu for ky_tu in ten
        if not unicodedata.combining(ky_tu)
    )
    return " ".join(ten.lower().split())


orders = doc_csv("olist_orders_dataset.csv")
customers = doc_csv("olist_customers_dataset.csv")

# Kiểm tra khóa trước khi ghép, tránh ghi đè khách hàng trùng mã
for ten_bang, du_lieu, khoa in [
    ("orders", orders, "order_id"),
    ("customers", customers, "customer_id"),
]:
    cac_ma = [dong[khoa].strip() for dong in du_lieu]

    if any(not ma for ma in cac_ma):
        raise ValueError(f"Bảng {ten_bang} có mã trống.")

    if len(cac_ma) != len(set(cac_ma)):
        raise ValueError(f"Bảng {ten_bang} có mã trùng.")

khach_theo_ma = {
    dong["customer_id"].strip(): dong
    for dong in customers
}

ket_qua = []
khong_khop = 0
thieu_diem_den = 0

for don in orders:
    ma_khach = don["customer_id"].strip()
    khach = khach_theo_ma.get(ma_khach)

    if khach is None:
        khong_khop += 1
        continue

    thanh_pho_goc = khach["customer_city"]
    bang_goc = khach["customer_state"]

    thanh_pho = chuan_hoa_thanh_pho(thanh_pho_goc)
    bang = bang_goc.strip().upper()

    if not thanh_pho or not bang:
        thieu_diem_den += 1
        continue

    ket_qua.append({
        "order_id": don["order_id"].strip(),
        "customer_id": ma_khach,
        "source_status": don["order_status"].strip().lower(),
        "source_city": thanh_pho_goc,
        "source_state": bang_goc,
        "destination_key": thanh_pho,
        "state": bang,
    })

# Dừng để kiểm tra nếu có dữ liệu chưa ghép được hoặc thiếu điểm đến
if khong_khop or thieu_diem_den:
    raise ValueError(
        f"Cần kiểm tra: {khong_khop} đơn không khớp khách hàng; "
        f"{thieu_diem_den} đơn thiếu điểm đến. Chưa xuất dữ liệu."
    )

# Tự tạo thư mục đầu ra, không sửa hai tệp gốc
OUTPUT.mkdir(parents=True, exist_ok=True)

tep_ra = OUTPUT / "orders_with_destinations.csv"
cac_cot = [
    "order_id", "customer_id", "source_status",
    "source_city", "source_state", "destination_key", "state",
]

with tep_ra.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=cac_cot)
    writer.writeheader()
    writer.writerows(ket_qua)

print(f"Số đơn đầu vào: {len(orders):,}")
print(f"Số khách hàng đầu vào: {len(customers):,}")
print(f"Số đơn không khớp khách hàng: {khong_khop}")
print(f"Số đơn thiếu điểm đến: {thieu_diem_den}")
print(f"Số đơn sau ghép: {len(ket_qua):,}")
print(f"Đã lưu: {tep_ra}")
print("Dữ liệu gốc được giữ nguyên.")