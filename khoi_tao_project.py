"""Khoi tao Smart Logistics - Nhom 10 bang mot lenh.

Chay rieng: python khoi_tao_project.py (tu choi neu DB da ton tai).
Tich hop web: dam_bao_san_sang_cho_web() (dung DB cu neu da hop le).
Khong xoa/ghi de DB da co, khong rollback bang cach xoa DB khi loi.
"""

import csv
import sqlite3
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "instance" / "smartlogistics.db"
DATA_PATH = BASE / "data" / "reference"
CAC_BUOC = (
    ("Chuẩn bị dữ liệu ứng dụng", "chuan_bi_du_lieu_ung_dung.py"),
    ("Khởi tạo database", "init_db.py"),
    ("Khởi tạo tracking", "init_tracking.py"),
    ("Nâng cấp xử lý", "nang_cap_xu_ly.py"),
)
COT_KIEN = {
    "code", "order_id", "destination", "destination_key", "state", "source_status"
}
CAC_BANG = {
    "parcels", "routing_rules", "sessions", "history",
    "processing_requests", "qr_measurements",
}


class LoiKhoiTao(RuntimeError):
    """Lỗi được báo rõ cho người chạy, không có thao tác xoá dữ liệu."""


def kiem_tra_file_chuong_trinh():
    for ten_buoc, ten_file in CAC_BUOC:
        duong_dan = BASE / ten_file
        if not duong_dan.is_file():
            raise LoiKhoiTao(f"Thiếu file {ten_file} (bước: {ten_buoc}).")
    if not (BASE / "requirements.txt").is_file():
        raise LoiKhoiTao("Thiếu requirements.txt trong thư mục project.")


def _doc_csv(duong_dan):
    if not duong_dan.is_file():
        raise LoiKhoiTao(f"Thiếu dữ liệu đầu vào: {duong_dan.relative_to(BASE)}")
    try:
        with duong_dan.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            cot = set(reader.fieldnames or [])
            if not COT_KIEN.issubset(cot):
                thieu = sorted(COT_KIEN - cot)
                raise LoiKhoiTao(
                    f"{duong_dan.relative_to(BASE)} thiếu cột: {', '.join(thieu)}"
                )
            return list(reader)
    except (UnicodeError, OSError, csv.Error) as error:
        raise LoiKhoiTao(f"Không đọc được {duong_dan}: {error}") from error


def kiem_tra_du_lieu_dau_vao():
    """Kiểm tra CSV nguồn trước khi sinh processed và database.

    Quy tắc 3 cửa được tạo bởi chuan_bi_du_lieu_ung_dung.py; kiểm tra
    chi tiết quy tắc / CSV processed vẫn do init_db.py của nhóm thực hiện.
    """
    ma_kien, ma_don = set(), set()
    quy_tac_hop_le = {
        ("sao paulo", "SP"), ("rio de janeiro", "RJ"),
        ("belo horizonte", "MG"),
    }
    for bo in ("demo", "final_test"):
        duong_dan = DATA_PATH / bo / "parcels.csv"
        cac_dong = _doc_csv(duong_dan)
        if len(cac_dong) != 30:
            raise LoiKhoiTao(f"Dữ liệu {bo} có {len(cac_dong)} kiện; cần đúng 30.")
        for vi_tri, dong in enumerate(cac_dong, 2):
            for cot in COT_KIEN:
                if not (dong.get(cot) or "").strip():
                    raise LoiKhoiTao(f"{bo}/parcels.csv dòng {vi_tri}: trống '{cot}'.")
            code = dong["code"].strip()
            order = dong["order_id"].strip()
            if code in ma_kien:
                raise LoiKhoiTao(f"Mã kiện trùng giữa các bộ: {code}.")
            if order in ma_don:
                raise LoiKhoiTao(f"Mã đơn nguồn trùng giữa các bộ: {order}.")
            ma_kien.add(code)
            ma_don.add(order)
            key = (dong["destination_key"].strip(), dong["state"].strip())
            if key not in quy_tac_hop_le:
                raise LoiKhoiTao(
                    f"Kiện {code}: điểm đến/bang không có quy tắc trong 3 cửa."
                )
    print("[OK] Dữ liệu nguồn hợp lệ: 30 demo + 30 final_test; mã không trùng.", flush=True)


def kiem_tra_database_san_sang():
    """Chỉ đọc SQLite, không tạo file database khi kiểm tra."""
    if not DB_PATH.is_file():
        raise LoiKhoiTao(f"Chưa có database tại {DB_PATH}.")
    try:
        conn = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            bang = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            thieu = CAC_BANG - bang
            if thieu:
                raise LoiKhoiTao(
                    "Database chưa khởi tạo đủ bảng: " + ", ".join(sorted(thieu))
                )
            so_kien = conn.execute("SELECT COUNT(*) FROM parcels").fetchone()[0]
            so_quy_tac = conn.execute("SELECT COUNT(*) FROM routing_rules").fetchone()[0]
            if (so_kien, so_quy_tac) != (60, 3):
                raise LoiKhoiTao(
                    f"Database chưa đúng dữ liệu: {so_kien} kiện, "
                    f"{so_quy_tac} quy tắc (cần 60 và 3)."
                )
            cac_cua = {
                row[0] for row in conn.execute("SELECT gate FROM routing_rules")
            }
            if cac_cua != {1, 2, 3}:
                raise LoiKhoiTao("Database thiếu quy tắc cửa 1, 2 hoặc 3.")
            kiem_tra = conn.execute("PRAGMA quick_check").fetchone()[0]
            if kiem_tra != "ok":
                raise LoiKhoiTao(f"SQLite quick_check không thành công: {kiem_tra}")
        finally:
            conn.close()
    except sqlite3.Error as error:
        raise LoiKhoiTao(f"Không đọc/kiểm tra được database: {error}") from error


def khoi_tao_moi():
    """Tuân thủ đề: gặp database tồn tại là dừng, không cập nhật."""
    if DB_PATH.exists() or DB_PATH.is_symlink():
        raise LoiKhoiTao(
            f"Database đã tồn tại: {DB_PATH}. Dừng để bảo vệ dữ liệu; "
            "không ghi đè hoặc xóa database."
        )
    kiem_tra_file_chuong_trinh()
    kiem_tra_du_lieu_dau_vao()
    for stt, (mo_ta, ten_file) in enumerate(CAC_BUOC, 1):
        # Kiểm tra lại trước bước tạo DB; không bao giờ cố chạy đè DB có sẵn.
        if stt <= 2 and (DB_PATH.exists() or DB_PATH.is_symlink()):
            raise LoiKhoiTao(
                f"Database xuất hiện trước bước {stt}; dừng để không ghi đè: {DB_PATH}"
            )
        print(f"\n[{stt}/4] {mo_ta}: {ten_file}", flush=True)
        try:
            ket_qua = subprocess.run(
                [sys.executable, str(BASE / ten_file)], cwd=BASE, check=False
            )
        except OSError as error:
            raise LoiKhoiTao(f"Không chạy được bước {stt} ({ten_file}): {error}") from error
        if ket_qua.returncode != 0:
            raise LoiKhoiTao(
                f"Bước {stt}/4 thất bại: {ten_file} (mã thoát {ket_qua.returncode}). "
                "Đã dừng, không chạy bước kế tiếp. "
                "Nếu database đã được tạo, giữ nguyên để kiểm tra thủ công."
            )
        if stt == 1:
            for ten in ("parcels.csv", "routing_rules.csv"):
                if not (BASE / "data" / "processed" / ten).is_file():
                    raise LoiKhoiTao(
                        f"Bước 1 không tạo được data/processed/{ten}."
                    )
        if stt == 2 and not DB_PATH.is_file():
            raise LoiKhoiTao("Bước 2 kết thúc nhưng chưa tạo database SQLite.")
    kiem_tra_database_san_sang()
    print("\n[THÀNH CÔNG] Khởi tạo project hoàn tất, database sẵn sàng.", flush=True)


def dam_bao_san_sang_cho_web():
    """Chỉ dùng khi chạy web: DB cũ hợp lệ thì dùng, chưa có thì tạo mới."""
    if DB_PATH.exists() or DB_PATH.is_symlink():
        kiem_tra_database_san_sang()
        print("[OK] Database có sẵn và hợp lệ; bỏ qua khởi tạo.", flush=True)
    else:
        print("[INFO] Chưa có database; khởi tạo lần đầu...", flush=True)
        khoi_tao_moi()


if __name__ == "__main__":
    try:
        khoi_tao_moi()
    except LoiKhoiTao as error:
        print(f"\n[LỖI KHỞI TẠO] {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
