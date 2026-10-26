import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent


def doc_csv(duong_dan):
    with duong_dan.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# Bảng Olist đã ghép và chuẩn hóa
nguon = doc_csv(
    BASE / "data" / "processed" / "orders_with_destinations.csv"
)
theo_ma_don = {dong["order_id"]: dong for dong in nguon}

if len(theo_ma_don) != len(nguon):
    raise ValueError("Bảng nguồn bị trùng mã đơn.")

cac_ma_kien = set()
cac_ma_don = set()
tong_loi = 0

for bo in ["demo", "final_test"]:
    duong_dan = BASE / "data" / "reference" / bo / "parcels.csv"
    cac_kien = doc_csv(duong_dan)
    so_khop = 0

    print(f"\n===== Bộ {bo}: {len(cac_kien)} kiện =====")

    if len(cac_kien) != 30:
        print("LỖI: Bộ dữ liệu phải có đúng 30 kiện.")
        tong_loi += 1

    for kien in cac_kien:
        ma = kien["code"]
        ma_don = kien["order_id"]
        loi = []

        if ma in cac_ma_kien:
            loi.append("trùng mã kiện")
        if ma_don in cac_ma_don:
            loi.append("trùng đơn nguồn")

        cac_ma_kien.add(ma)
        cac_ma_don.add(ma_don)

        don = theo_ma_don.get(ma_don)

        if don is None:
            loi.append("không tìm thấy đơn trong Olist")
        else:
            for cot in ["destination_key", "state", "source_status"]:
                if kien[cot] != don[cot]:
                    loi.append(f"không khớp {cot}")

        if loi:
            tong_loi += 1
            print(f"{ma}: LỖI — {', '.join(loi)}")
        else:
            so_khop += 1

    print(f"Số kiện khớp nguồn, không trùng: {so_khop}/{len(cac_kien)}")

print(f"\nTổng số lỗi phát hiện: {tong_loi}")

if tong_loi == 0:
    print("ĐỐI CHIẾU THÀNH CÔNG — Có thể giữ bộ mã kiện và QR hiện tại.")
else:
    print("Cần kiểm tra các lỗi phía trên trước khi tiếp tục.")