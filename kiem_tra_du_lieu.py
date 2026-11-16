"""Kiểm tra dữ liệu ứng dụng; thêm --raw để khảo sát dữ liệu Olist gốc.
Chỉ đọc CSV và danh sách ảnh, không sửa dữ liệu hoặc database.
"""

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"

COT_KIEN = {
    "code",
    "order_id",
    "destination",
    "destination_key",
    "state",
    "source_status",
}

QUY_TAC = {
    ("sao paulo", "SP"): 1,
    ("rio de janeiro", "RJ"): 2,
    ("belo horizonte", "MG"): 3,
}


def doc_csv(path, cot_can):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        cols = reader.fieldnames or []

        if not cols or len(cols) != len(set(cols)):
            raise ValueError(
                f"{path}: tiêu đề trống hoặc trùng cột."
            )

        if not cot_can.issubset(cols):
            raise ValueError(
                f"{path}: thiếu cột "
                f"{sorted(cot_can - set(cols))}."
            )

        rows = list(reader)

    for i, row in enumerate(rows, 2):
        if None in row or any(
            value is None for value in row.values()
        ):
            raise ValueError(
                f"{path}: dòng {i} thiếu hoặc thừa ô."
            )

    return cols, rows


def kiem_tra(ten_file, cot_ma):
    """Giữ chức năng khảo sát dữ liệu Olist gốc của nhóm."""
    cols, rows = doc_csv(RAW / ten_file, {cot_ma})

    print(f"\n===== {ten_file} =====")
    print(f"Số dòng dữ liệu: {len(rows):,}")
    print(f"Số cột: {len(cols)}")

    print("\nSố ô trống theo từng cột:")
    for col in cols:
        so_trong = sum(
            not row[col].strip() for row in rows
        )
        print(f"  {col}: {so_trong:,}")

    values = [
        tuple(row[col] for col in cols)
        for row in rows
    ]
    trung_dong = len(values) - len(set(values))

    print(
        "\nSố dòng lặp dư, giống toàn bộ cột: "
        f"{trung_dong:,}"
    )

    codes = [
        row[cot_ma]
        for row in rows
        if row[cot_ma].strip()
    ]
    trung_ma = len(codes) - len(set(codes))

    print(
        f"Số lượt mã {cot_ma} lặp dư: {trung_ma:,}"
    )


def kiem_tra_ung_dung():
    errors = []

    def loi(message):
        errors.append(message)
        print(f"[LỖI] {message}")

    def doc(path, cols):
        try:
            return doc_csv(path, cols)[1]
        except (
            OSError,
            UnicodeError,
            csv.Error,
            ValueError,
        ) as error:
            loi(str(error))
            return None

    def kiem_tra_kien(rows, label, expected_count):
        if len(rows) != expected_count:
            loi(
                f"{label}: có {len(rows)} kiện, "
                f"cần {expected_count}."
            )

        for field in ("code", "order_id"):
            counts = Counter(
                row[field] for row in rows
            )
            duplicates = sorted(
                key
                for key, count in counts.items()
                if count > 1
            )

            if duplicates:
                loi(
                    f"{label}: trùng {field}: "
                    f"{duplicates}."
                )

        gates = Counter()

        for i, row in enumerate(rows, 2):
            if any(
                not row[col].strip()
                for col in COT_KIEN
            ):
                loi(
                    f"{label}, dòng {i}: "
                    "có trường bắt buộc trống."
                )

            if any(
                row[col] != row[col].strip()
                for col in COT_KIEN
            ):
                loi(
                    f"{label}, dòng {i}: trường có "
                    "khoảng trắng đầu/cuối."
                )

            if re.fullmatch(
                r"KH[0-9]{3}", row["code"]
            ) is None:
                loi(
                    f"{label}, dòng {i}: mã kiện "
                    f"sai định dạng: {row['code']!r}."
                )

            key = (
                row["destination_key"],
                row["state"],
            )

            if key not in QUY_TAC:
                loi(
                    f"{label}, dòng {i}: điểm đến/bang "
                    f"chưa có quy tắc: {key}."
                )
            else:
                gates[QUY_TAC[key]] += 1

        target = expected_count // 3
        expected_gates = Counter({
            1: target,
            2: target,
            3: target,
        })

        if gates != expected_gates:
            loi(
                f"{label}: phân bố cửa {dict(gates)}, "
                f"cần mỗi cửa {target} kiện."
            )

    reference = {}

    for subset in ("demo", "final_test"):
        folder = (
            BASE / "data" / "reference" / subset
        )
        rows = doc(
            folder / "parcels.csv",
            COT_KIEN,
        )

        if rows is None:
            continue

        reference[subset] = rows
        kiem_tra_kien(rows, subset, 30)

        codes = {row["code"] for row in rows}

        try:
            images = [
                p
                for p in folder.iterdir()
                if p.is_file()
                and p.suffix.lower() in {
                    ".png",
                    ".jpg",
                    ".jpeg",
                }
            ]
        except OSError as error:
            loi(
                f"{subset}: không liệt kê được ảnh: "
                f"{error}"
            )
            images = []

        image_counts = Counter(
            p.stem for p in images
        )

        missing = sorted(
            codes - set(image_counts)
        )
        extra = sorted(
            set(image_counts) - codes
        )
        duplicates = sorted(
            code
            for code, count in image_counts.items()
            if count > 1
        )

        if missing:
            loi(
                f"{subset}: thiếu ảnh cho mã "
                f"{missing}."
            )

        if extra:
            loi(
                f"{subset}: ảnh dư có mã {extra}."
            )

        if duplicates:
            loi(
                f"{subset}: nhiều ảnh cho cùng mã "
                f"{duplicates}."
            )

        print(
            f"[ĐÃ ĐỌC] {subset}: {len(rows)} kiện, "
            f"{len(images)} ảnh."
        )

    if len(reference) == 2:
        all_rows = (
            reference["demo"]
            + reference["final_test"]
        )
        kiem_tra_kien(
            all_rows,
            "Tổng hai bộ tham chiếu",
            60,
        )

    processed = BASE / "data" / "processed"

    rules = doc(
        processed / "routing_rules.csv",
        {"destination_key", "state", "gate"},
    )

    if rules is not None:
        expected = Counter(
            (key, state, str(gate))
            for (key, state), gate in QUY_TAC.items()
        )
        actual = Counter(
            (
                row["destination_key"],
                row["state"],
                row["gate"],
            )
            for row in rules
        )

        if actual != expected:
            loi(
                "routing_rules.csv: cần đúng 3 quy tắc "
                "São Paulo/SP→1, Rio de Janeiro/RJ→2, "
                "Belo Horizonte/MG→3."
            )

    parcels = doc(
        processed / "parcels.csv",
        COT_KIEN | {"subset"},
    )

    if parcels is not None:
        kiem_tra_kien(
            parcels,
            "processed/parcels.csv",
            60,
        )

        if any(
            row["subset"] not in {
                "demo",
                "final_test",
            }
            for row in parcels
        ):
            loi(
                "processed/parcels.csv: subset phải "
                "là demo hoặc final_test."
            )

        if len(reference) == 2:
            cols = sorted(COT_KIEN)

            expected = Counter(
                (
                    subset,
                    *(row[col] for col in cols),
                )
                for subset, rows in reference.items()
                for row in rows
            )

            actual = Counter(
                (
                    row["subset"],
                    *(row[col] for col in cols),
                )
                for row in parcels
            )

            if actual != expected:
                loi(
                    "processed/parcels.csv không khớp "
                    "dữ liệu hai bộ tham chiếu."
                )

    if errors:
        print(
            f"\nTHẤT BẠI: phát hiện {len(errors)} lỗi; "
            "mã thoát 1."
        )
        return 1

    print(
        "\nĐẠT: 60 kiện; mỗi bộ 30 kiện, "
        "mỗi cửa 10 kiện; quy tắc và "
        "danh sách ảnh hợp lệ."
    )
    print(
        "Chưa giải mã nội dung ảnh QR; bước này "
        "chỉ kiểm tra tên và số lượng ảnh."
    )
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help=(
            "Khảo sát hai CSV Olist gốc thay cho "
            "kiểm tra dữ liệu ứng dụng."
        ),
    )
    args = parser.parse_args()

    if args.raw:
        try:
            kiem_tra(
                "olist_orders_dataset.csv",
                "order_id",
            )
            kiem_tra(
                "olist_customers_dataset.csv",
                "customer_id",
            )
        except (
            OSError,
            UnicodeError,
            csv.Error,
            ValueError,
        ) as error:
            print(f"[LỖI] {error}")
            return 1

        print(
            "\nKhảo sát hoàn tất; số ô trống/lặp "
            "là thống kê để làm sạch, không phải "
            "kết luận dữ liệu đạt."
        )
        return 0

    return kiem_tra_ung_dung()


if __name__ == "__main__":
    raise SystemExit(main())