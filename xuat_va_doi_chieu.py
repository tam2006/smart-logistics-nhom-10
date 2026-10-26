import argparse
import csv
import json
import math
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


BASE = Path(__file__).resolve().parent

HISTORY_FIELDS = [
    "id",
    "request_id",
    "session_id",
    "code",
    "destination",
    "gate",
    "success",
    "status",
    "reason",
    "source",
    "decision_ms",
    "created_at",
]

MEASUREMENT_FIELDS = [
    "measurement_version",
    "mode",
    "image_name",
    "image_sha256",
    "valid",
    "invalid_reason",
    "read_ms",
    "prepare_ms",
    "pipeline_ms",
    "animation_ms",
]

TIMINGS = [
    "read_ms",
    "prepare_ms",
    "pipeline_ms",
    "animation_ms",
]


def doc_dap_an(path, subset):
    if not path.is_file():
        raise ValueError(f"Không tìm thấy tệp đáp án: {path}")

    expected = {}

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"code", "expected_gate", "expected_status"}

        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                "Tệp đáp án cần cột code, expected_gate, expected_status."
            )

        for line, row in enumerate(reader, start=2):
            code = (row["code"] or "").strip()
            gate_text = (row["expected_gate"] or "").strip()
            status = (row["expected_status"] or "").strip()

            if re.fullmatch(r"KH[0-9]{3}", code) is None:
                raise ValueError(
                    f"Mã đáp án không hợp lệ ở dòng {line}."
                )

            if code in expected:
                raise ValueError(f"Mã đáp án bị lặp: {code}")

            if gate_text not in {"1", "2", "3"} or status != "success":
                raise ValueError(f"Đáp án không hợp lệ cho {code}.")

            expected[code] = {
                "expected_gate": int(gate_text),
                "expected_status": status,
            }

    start = 1 if subset == "demo" else 31
    required_codes = {
        f"KH{number:03d}"
        for number in range(start, start + 30)
    }

    if set(expected) != required_codes:
        raise ValueError(
            f"Đáp án chưa khớp 30 mã của bộ {subset}."
        )

    return expected


def doc_phien(database, session_id):
    if not database.is_file():
        raise ValueError(f"Không tìm thấy database: {database}")

    # Chỉ đọc database, không tạo database mới.
    uri = database.resolve().as_uri() + "?mode=ro"

    with closing(
        sqlite3.connect(uri, uri=True, timeout=10)
    ) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")

        if not session_id:
            choices = conn.execute("""
                SELECT
                    s.id,
                    s.name,
                    s.status,
                    s.created_at,
                    COUNT(h.id) AS total
                FROM sessions AS s
                LEFT JOIN history AS h
                    ON h.session_id = s.id
                GROUP BY s.id
                ORDER BY s.created_at DESC, s.id DESC
                LIMIT 20
            """).fetchall()

            if not choices:
                raise ValueError("Chưa có phiên nào để xuất.")

            print(
                "\n20 phiên gần nhất "
                "(hoặc tất cả nếu ít hơn 20):"
            )

            for number, item in enumerate(choices, start=1):
                label = (
                    "đã đóng"
                    if item["status"] == "closed"
                    else "đang mở"
                )
                print(
                    f"{number:2}. {item['name']} | "
                    f"{label} | {item['total']} lượt"
                )

            answer = input(
                "\nNhập SỐ THỨ TỰ của phiên cần xuất: "
            ).strip()

            if not answer.isascii() or not answer.isdigit():
                raise ValueError(
                    "Cần nhập số thứ tự trong danh sách."
                )

            selected = int(answer)

            if not 1 <= selected <= len(choices):
                raise ValueError(
                    "Số thứ tự nằm ngoài danh sách."
                )

            session_id = choices[selected - 1]["id"]

        # Phiên, lịch sử và số đo được đọc trong cùng snapshot.
        conn.execute("BEGIN")

        session = conn.execute("""
            SELECT
                id,
                name,
                status,
                created_at,
                closed_at
            FROM sessions
            WHERE id = ?
        """, (session_id,)).fetchone()

        if session is None:
            raise ValueError("Không tìm thấy phiên đã chọn.")

        rows = conn.execute("""
            SELECT
                id,
                request_id,
                session_id,
                code,
                destination,
                gate,
                success,
                status,
                reason,
                source,
                decision_ms,
                created_at
            FROM history
            WHERE session_id = ?
            ORDER BY id ASC
        """, (session_id,)).fetchall()

        rows = [dict(row) for row in rows]

        has_measurements = conn.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'qr_measurements'
        """).fetchone() is not None

        measurements = {}

        if has_measurements:
            items = conn.execute("""
                SELECT q.*
                FROM qr_measurements AS q
                JOIN history AS h
                    ON h.request_id = q.request_id
                WHERE h.session_id = ?
            """, (session_id,)).fetchall()

            measurements = {
                item["request_id"]: dict(item)
                for item in items
            }

        for row in rows:
            row["measurement"] = measurements.get(
                row["request_id"]
            )

        return dict(session), rows


def ti_le(numerator, denominator):
    if denominator == 0:
        return None

    return round(numerator * 100 / denominator, 2)


def so_hop_le(value):
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and value >= 0
    )


def trang_thai_so_do(row):
    m = row.get("measurement")

    if m is None:
        return "missing", "Chưa có số đo đã lưu"

    if row["source"] != "qr":
        return "invalid", "Số đo gắn với nguồn không phải qr"

    if m.get("valid") != 1:
        return (
            "invalid",
            m.get("invalid_reason")
            or "Số đo bị đánh dấu không hợp lệ",
        )

    if m.get("measurement_version") != 1:
        return "invalid", "Phiên bản số đo chưa được hỗ trợ"

    if m.get("mode") not in ("single", "batch"):
        return "invalid", "Chế độ đo không hợp lệ"

    if (
        not isinstance(m.get("image_name"), str)
        or not m["image_name"].strip()
    ):
        return "invalid", "Thiếu tên ảnh"

    if m.get("invalid_reason") is not None:
        return (
            "invalid",
            "Số đo hợp lệ nhưng vẫn có lý do loại",
        )

    if not all(so_hop_le(m.get(key)) for key in TIMINGS):
        return (
            "invalid",
            "Thời gian thiếu, âm hoặc không hữu hạn",
        )

    if m["pipeline_ms"] < max(m["read_ms"], m["prepare_ms"]):
        return (
            "invalid",
            "Thời gian QR -> cửa không nhất quán",
        )

    return "valid", ""


def thong_ke(values):
    values = sorted(values)

    # P95 theo nearest-rank.
    # Với ít mẫu, P95 có thể bằng giá trị lớn nhất.
    return {
        "samples": len(values),
        "mean": (
            round(statistics.mean(values), 3)
            if values else None
        ),
        "median": (
            round(statistics.median(values), 3)
            if values else None
        ),
        "p95": (
            round(
                values[math.ceil(0.95 * len(values)) - 1],
                3,
            )
            if values else None
        ),
        "max": round(max(values), 3) if values else None,
    }


def thong_ke_nhom(rows):
    return {
        key: thong_ke([
            row["measurement"][key]
            for row in rows
        ])
        for key in TIMINGS
    }


def tong_hop_qr(rows):
    qr = [
        row for row in rows
        if row["source"] == "qr"
    ]

    valid = [
        row for row in qr
        if trang_thai_so_do(row)[0] == "valid"
    ]

    counts = Counter(
        trang_thai_so_do(row)[0]
        for row in qr
    )

    return {
        "measurement_type": "qr_image_to_prepared_route",
        "qr_history_attempts": len(qr),
        "valid_measurements": counts["valid"],
        "invalid_measurements": counts["invalid"],
        "missing_measurements": counts["missing"],
        "valid_coverage_pct": ti_le(len(valid), len(qr)),
        "all_valid_attempts": thong_ke_nhom(valid),
        "valid_successful_attempts": thong_ke_nhom([
            row for row in valid
            if row["success"] == 1
            and row["status"] == "success"
        ]),
        "by_mode": {
            mode: thong_ke_nhom([
                row for row in valid
                if row["measurement"]["mode"] == mode
            ])
            for mode in ("single", "batch")
        },
        "exclusion_reasons": dict(Counter(
            trang_thai_so_do(row)[1]
            for row in qr
            if trang_thai_so_do(row)[0] != "valid"
        )),
        "non_qr_attempts_with_measurement": sum(
            row["source"] != "qr"
            and row.get("measurement") is not None
            for row in rows
        ),
    }


def doi_chieu(session, rows, expected, subset):
    groups = defaultdict(list)

    for row in rows:
        groups[row["code"]].append(row)

    comparison = []

    for code, answer in sorted(expected.items()):
        attempts = sorted(
            groups.get(code, []),
            key=lambda row: row["id"],
        )

        first = attempts[0] if attempts else None

        successes = [
            row for row in attempts
            if row["success"] == 1
        ]

        first_correct = bool(
            first
            and first["success"] == 1
            and first["status"] == answer["expected_status"]
            and first["gate"] == answer["expected_gate"]
        )

        if not attempts:
            result = "chua_xu_ly"
        elif not successes:
            result = "chua_thanh_cong"
        elif len(successes) > 1:
            result = "bat_thuong_nhieu_luot_thanh_cong"
        elif (
            successes[0]["gate"] == answer["expected_gate"]
            and successes[0]["status"] == answer["expected_status"]
        ):
            result = "dung_cua"
        else:
            result = "sai_cua_hoac_trang_thai"

        comparison.append({
            "code": code,
            **answer,
            "attempts": len(attempts),
            "first_history_id": first["id"] if first else None,
            "first_status": first["status"] if first else None,
            "first_gate": first["gate"] if first else None,
            "first_correct": int(first_correct),
            "successful_attempts": len(successes),
            "completed_gate": (
                successes[0]["gate"]
                if len(successes) == 1 else None
            ),
            "comparison": result,
        })

    counts = Counter(
        item["comparison"] for item in comparison
    )

    attempted = sum(
        item["attempts"] > 0 for item in comparison
    )

    first_correct = sum(
        item["first_correct"] for item in comparison
    )

    outside = [
        row for row in rows
        if row["code"] not in expected
    ]

    times = [
        float(row["decision_ms"])
        for row in rows
        if isinstance(row["decision_ms"], (int, float))
        and math.isfinite(row["decision_ms"])
        and row["decision_ms"] >= 0
    ]

    clean_run = (
        counts["dung_cua"] == len(expected)
        and first_correct == len(expected)
        and len(rows) == len(expected)
        and not outside
    )

    if clean_run and session["status"] == "closed":
        conclusion = "DAT_DU_BO"
    elif clean_run:
        conclusion = "DU_BO_DUNG_CUA_NHUNG_PHIEN_CON_MO"
    elif counts["chua_xu_ly"]:
        conclusion = "CHUA_DU_BO"
    else:
        conclusion = "CAN_XEM_CHI_TIET"

    summary = {
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "session": session,
        "subset": subset,
        "expected_parcels": len(expected),
        "history_attempts": len(rows),
        "successful_attempts": sum(
            row["success"] == 1 for row in rows
        ),
        "unsuccessful_attempts": sum(
            row["success"] != 1 for row in rows
        ),
        "status_counts": dict(Counter(
            row["status"] for row in rows
        )),
        "source_counts": dict(Counter(
            row["source"] for row in rows
        )),
        "expected_parcels_attempted": attempted,
        "correctly_completed_parcels": counts["dung_cua"],
        "wrong_gate_or_status_parcels": (
            counts["sai_cua_hoac_trang_thai"]
        ),
        "not_successful_parcels": counts["chua_thanh_cong"],
        "multiple_success_parcels": (
            counts["bat_thuong_nhieu_luot_thanh_cong"]
        ),
        "missing_parcels": counts["chua_xu_ly"],
        "outside_reference_attempts": len(outside),
        "first_attempt_correct_parcels": first_correct,
        "first_attempt_correct_pct_of_attempted": ti_le(
            first_correct, attempted
        ),
        "first_attempt_correct_pct_of_full_set": ti_le(
            first_correct, len(expected)
        ),
        "correct_completion_pct_of_full_set": ti_le(
            counts["dung_cua"], len(expected)
        ),
        "decision_ms_valid_samples": len(times),
        "decision_ms_mean_all_attempts": (
            round(statistics.mean(times), 3)
            if times else None
        ),
        "decision_ms_median_all_attempts": (
            round(statistics.median(times), 3)
            if times else None
        ),
        "decision_ms_max_all_attempts": (
            round(max(times), 3)
            if times else None
        ),
        "conclusion": conclusion,
        "notes": [
            (
                "Đối chiếu mã, cửa và trạng thái với "
                "expected_answers.csv độc lập."
            ),
            (
                "Đúng lần đầu dùng lượt có ID nhỏ nhất "
                "của từng mã trong bộ đáp án."
            ),
            (
                "Đúng cửa chỉ được tính khi mã có đúng "
                "một lượt thành công khớp đáp án."
            ),
            (
                "Thời gian quyết định lấy từ backend, "
                "gồm các lượt trong phiên."
            ),
            (
                "Số đo QR lấy từ qr_measurements. Chỉ thống kê "
                "thời gian khi số đo hợp lệ, phiên bản 1 "
                "và nguồn là qr."
            ),
            (
                "QR -> xác định cửa không gồm hoạt ảnh, "
                "khoảng nghỉ giữa ảnh và thao tác chọn tệp. "
                "Không dùng nghịch đảo thời gian này làm "
                "thông lượng mô phỏng thực tế."
            ),
            (
                "Chưa đánh giá độ chính xác đọc QR hay tỷ lệ "
                "xử lý lỗi: cần ảnh đầu vào, đáp án và cả lượt "
                "đọc ảnh thất bại. Đối chiếu hiện tại chỉ áp dụng "
                "bộ 30 kiện hợp lệ."
            ),
            (
                "Phiên đang mở là kết quả tạm tại thời điểm đọc; "
                "bộ thiếu chưa được kết luận đạt đủ bộ."
            ),
        ],
    }

    summary["schema_version"] = 2
    summary["routing_conclusion"] = conclusion
    summary["qr_metrics"] = tong_hop_qr(rows)
    summary["qr_decode_accuracy_pct"] = None
    summary["simulated_throughput_parcels_per_minute"] = None

    return comparison, summary


def dong_xuat(row):
    m = row.get("measurement") or {}
    state, reason = trang_thai_so_do(row)

    return {
        **{key: row.get(key) for key in HISTORY_FIELDS},
        "measurement_present": int(
            row.get("measurement") is not None
        ),
        **{key: m.get(key) for key in MEASUREMENT_FIELDS},
        "measurement_created_at": m.get("created_at"),
        "measurement_check": state,
        "measurement_exclusion_reason": reason,
    }


def ghi_csv(path, fields, rows):
    def excel_cell(value):
        if (
            isinstance(value, str)
            and value.startswith(
                ("=", "+", "-", "@", "\t", "\r", "\n")
            )
        ):
            return "'" + value

        return value

    with path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                field: excel_cell(row.get(field))
                for field in fields
            })


def noi_dung_tong_ket(summary):
    s = summary
    session = s["session"]
    first_rate = s["first_attempt_correct_pct_of_attempted"]

    first_text = (
        "chưa có dữ liệu"
        if first_rate is None
        else f"{first_rate}%"
    )

    lines = [
        "SMARTLOGISTICS QR - KET QUA DOI CHIEU",
        f"Phiên: {session['name']}",
        f"ID phiên: {session['id']}",
        f"Trạng thái phiên: {session['status']}",
        (
            f"Bộ đáp án: {s['subset']} "
            f"({s['expected_parcels']} kiện)"
        ),
        f"Thời điểm xuất UTC: {s['exported_at_utc']}",
        "",
        f"Tổng lượt lịch sử: {s['history_attempts']}",
        f"Lượt thành công: {s['successful_attempts']}",
        f"Lượt không thành công: {s['unsuccessful_attempts']}",
        (
            "Kiện trong đáp án đã có lượt xử lý: "
            f"{s['expected_parcels_attempted']}"
        ),
        (
            "Kiện hoàn tất đúng cửa: "
            f"{s['correctly_completed_parcels']}"
        ),
        (
            "Kiện sai cửa/trạng thái: "
            f"{s['wrong_gate_or_status_parcels']}"
        ),
        (
            "Kiện đã thử nhưng chưa thành công: "
            f"{s['not_successful_parcels']}"
        ),
        (
            "Kiện có nhiều lượt thành công bất thường: "
            f"{s['multiple_success_parcels']}"
        ),
        f"Kiện chưa xử lý: {s['missing_parcels']}",
        (
            "Lượt có mã ngoài bộ đáp án: "
            f"{s['outside_reference_attempts']}"
        ),
        "",
        (
            "Đúng ngay lần đầu trên số mã đã thử: "
            f"{s['first_attempt_correct_parcels']}/"
            f"{s['expected_parcels_attempted']} ({first_text})"
        ),
        (
            "Hoàn tất đúng cửa trên toàn bộ: "
            f"{s['correctly_completed_parcels']}/"
            f"{s['expected_parcels']} "
            f"({s['correct_completion_pct_of_full_set']}%)"
        ),
        (
            "Quyết định trung bình (ms): "
            f"{s['decision_ms_mean_all_attempts']}"
        ),
        (
            "Quyết định trung vị (ms): "
            f"{s['decision_ms_median_all_attempts']}"
        ),
        (
            "Quyết định lớn nhất (ms): "
            f"{s['decision_ms_max_all_attempts']}"
        ),
        (
            "Số lượt có số đo thời gian hợp lệ: "
            f"{s['decision_ms_valid_samples']}"
        ),
        f"Kết luận: {s['conclusion']}",
        "",
        "GHI CHU:",
        *[f"- {note}" for note in s["notes"]],
    ]

    q = s["qr_metrics"]
    t = q["all_valid_attempts"]["pipeline_ms"]

    lines.extend([
        "",
        "SO DO QR DA LUU (ms):",
        f"Lượt QR trong lịch sử: {q['qr_history_attempts']}",
        f"Số đo hợp lệ: {q['valid_measurements']}",
        f"Số đo bị loại: {q['invalid_measurements']}",
        f"Lượt QR chưa có số đo: {q['missing_measurements']}",
        f"QR -> cửa trung bình: {t['mean']}",
        f"QR -> cửa trung vị: {t['median']}",
        f"QR -> cửa P95 (nearest-rank): {t['p95']}",
        "Hoạt ảnh được thống kê riêng trong summary.json.",
        "Kết luận đủ bộ ở trên chỉ xét định tuyến và lịch sử.",
        "Chưa có kết luận đạt toàn bộ yêu cầu đồ án.",
    ])

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Xuất lịch sử và đối chiếu đáp án QR."
    )

    parser.add_argument(
        "--subset",
        choices=["demo", "final_test"],
        default="demo",
    )
    parser.add_argument("--session-id")
    parser.add_argument(
        "--database",
        type=Path,
        default=BASE / "instance" / "smartlogistics.db",
    )
    parser.add_argument("--reference", type=Path)

    args = parser.parse_args()

    reference = (
        args.reference
        or BASE / "data" / "reference"
        / args.subset / "expected_answers.csv"
    )

    expected = doc_dap_an(reference, args.subset)
    session, rows = doc_phien(args.database, args.session_id)

    comparison, summary = doi_chieu(
        session, rows, expected, args.subset
    )

    summary["reference_file"] = str(reference.resolve())

    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S_%fZ"
    )
    folder = BASE / "reports" / f"{stamp}_{args.subset}"
    folder.mkdir(parents=True, exist_ok=False)

    comparison_fields = [
        "code",
        "expected_gate",
        "expected_status",
        "attempts",
        "first_history_id",
        "first_status",
        "first_gate",
        "first_correct",
        "successful_attempts",
        "completed_gate",
        "comparison",
    ]

    ghi_csv(
        folder / "history.csv",
        HISTORY_FIELDS,
        rows,
    )

    ghi_csv(
        folder / "qr_measurements.csv",
        HISTORY_FIELDS
        + ["measurement_present"]
        + MEASUREMENT_FIELDS
        + [
            "measurement_created_at",
            "measurement_check",
            "measurement_exclusion_reason",
        ],
        [
            dong_xuat(row)
            for row in rows
            if row["source"] == "qr"
            or row.get("measurement") is not None
        ],
    )

    ghi_csv(
        folder / "comparison.csv",
        comparison_fields,
        comparison,
    )

    (folder / "summary.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    text = noi_dung_tong_ket(summary)

    (folder / "tong_ket.txt").write_text(
        text,
        encoding="utf-8-sig",
    )

    print("\n" + text)
    print(f"Đã lưu 5 tệp trong THƯ MỤC: {folder}")
    print(
        "Chỉ đọc database; "
        "không tạo phiên hoặc thêm lịch sử."
    )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        OSError,
        sqlite3.Error,
        csv.Error,
    ) as error:
        raise SystemExit(
            f"Không xuất được báo cáo: {error}"
        )
    except (KeyboardInterrupt, EOFError):
        raise SystemExit("Đã dừng thao tác xuất.")