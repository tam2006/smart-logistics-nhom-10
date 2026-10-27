import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUTPUT = DATA / "processed"


def doc_csv(duong_dan):
    with duong_dan.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def ghi_csv(ten_file, du_lieu, cac_cot):
    duong_dan = OUTPUT / ten_file
    with duong_dan.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cac_cot)
        writer.writeheader()
        writer.writerows(du_lieu)
    print(f"Đã lưu: {duong_dan}")


# Gom dữ liệu, giữ nhãn để phân biệt hai bộ
cac_kien = []

for bo in ["demo", "final_test"]:
    du_lieu = doc_csv(DATA / "reference" / bo / "parcels.csv")

    if len(du_lieu) != 30:
        raise ValueError(f"Bộ {bo} phải có đúng 30 kiện.")

    for dong in du_lieu:
        cac_kien.append({
            "code": dong["code"],
            "order_id": dong["order_id"],
            "destination": dong["destination"],
            "destination_key": dong["destination_key"],
            "state": dong["state"],
            "source_status": dong["source_status"],
            "subset": bo,
        })

if len({k["code"] for k in cac_kien}) != 60:
    raise ValueError("Mã kiện bị trùng.")

if len({k["order_id"] for k in cac_kien}) != 60:
    raise ValueError("Mã đơn nguồn bị trùng.")

# Quy tắc do nhóm đặt cho trạm mô phỏng
quy_tac = [
    {
        "destination_key": "sao paulo",
        "state": "SP",
        "destination": "São Paulo",
        "gate": 1,
    },
    {
        "destination_key": "rio de janeiro",
        "state": "RJ",
        "destination": "Rio de Janeiro",
        "gate": 2,
    },
    {
        "destination_key": "belo horizonte",
        "state": "MG",
        "destination": "Belo Horizonte",
        "gate": 3,
    },
]

OUTPUT.mkdir(parents=True, exist_ok=True)

ghi_csv(
    "parcels.csv",
    cac_kien,
    [
        "code", "order_id", "destination", "destination_key",
        "state", "source_status", "subset",
    ],
)

ghi_csv(
    "routing_rules.csv",
    quy_tac,
    ["destination_key", "state", "destination", "gate"],
)

print(f"\nSẵn sàng: {len(cac_kien)} kiện và {len(quy_tac)} quy tắc.")
print("Chưa tạo database hoặc backend.")