import argparse
import csv
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from xuat_va_doi_chieu import doi_chieu, ghi_csv, thong_ke, ti_le


BASE = Path(__file__).resolve().parent
MANUAL_TYPE = "manual_code_lookup_to_gate_click"
TIME_FIELDS = ("read_ms", "prepare_ms", "pipeline_ms", "animation_ms")

TABLE_FIELDS = [
    "phuong_phap", "so_kien", "da_thu", "dung_lan_dau",
    "ty_le_dung_tren_da_thu_pct", "ty_le_dung_tren_30_pct",
    "so_mau_thoi_gian", "pham_vi_do_thoi_gian",
    "trung_binh_ms", "trung_vi_ms", "p95_ms", "lon_nhat_ms",
]


def doc_json(path):
    with path.open(encoding="utf-8-sig") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"JSON không phải đối tượng: {path}")

    return data


def doc_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(f"CSV thiếu tiêu đề: {path}")

        return list(reader)


def so(value, label):
    if isinstance(value, bool) or value is None or value == "":
        raise ValueError(f"Thiếu hoặc sai số: {label}")

    number = float(value)

    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Số âm hoặc không hữu hạn: {label}")

    return number


def nguyen(value, label):
    number = so(value, label)

    if number != int(number):
        raise ValueError(f"Cần số nguyên: {label}")

    return int(number)


def khop(actual, expected, label, tolerance=0.011):
    if actual is None or expected is None:
        if actual is not expected:
            raise ValueError(f"Số liệu không khớp: {label}")
    elif abs(so(actual, label) - so(expected, label)) > tolerance:
        raise ValueError(f"Số liệu không khớp: {label}")


def bo_ma(subset):
    start = 1 if subset == "demo" else 31

    return {
        f"KH{n:03d}"
        for n in range(start, start + 30)
    }


def tim_bao_cao(folder, subset, manual=False):
    name = "manual_summary.json" if manual else "summary.json"
    candidates = []

    for path in sorted(folder.glob(f"*/{name}")):
        try:
            data = doc_json(path)

            if data.get("subset") != subset:
                continue

            if manual and data.get("measurement") != MANUAL_TYPE:
                continue

            when = datetime.fromisoformat(data["exported_at_utc"])

            if when.tzinfo is None:
                raise ValueError("Thời điểm xuất thiếu múi giờ")

            key = str(path) if manual else data["session"]["id"]
            candidates.append((key, when, path, data))

        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"Bỏ qua {path.parent.name}: {error}")

    # Một phiên có thể được xuất nhiều lần:
    # chỉ giữ bản xuất mới nhất của từng phiên.
    latest = {}

    for key, when, path, data in candidates:
        if key not in latest or when > latest[key][0]:
            latest[key] = (when, path, data)

    return [
        (p, d)
        for _, p, d in sorted(
            latest.values(),
            key=lambda item: item[0],
            reverse=True,
        )
    ]


def chon_bao_cao(candidates, label, manual=False):
    if not candidates:
        raise ValueError(
            f"Chưa có báo cáo {label}. "
            "Cần chạy và xuất đúng bộ trước khi tổng hợp chính thức."
        )

    print(f"\nCHỌN {label.upper()}")

    for n, (path, data) in enumerate(candidates, 1):
        if manual:
            text = (
                f"{data.get('participant', '?')} | "
                f"đã trả lời {data.get('answered', '?')}/30 | "
                f"ngắt {data.get('interrupted_presentations', '?')} lần"
            )
        else:
            session = data["session"]
            text = (
                f"{session['name']} | {session['status']} | "
                f"đã thử {data.get('expected_parcels_attempted', '?')}/30"
            )

        print(f"{n}. {text}\n   {path.parent.name}")

    if len(candidates) == 1:
        print("Dùng mục 1.")
        return candidates[0]

    answer = input("Nhập số thứ tự: ").strip()

    if not answer.isascii() or not answer.isdigit():
        raise ValueError("Cần nhập số thứ tự trong danh sách.")

    n = int(answer)

    if not 1 <= n <= len(candidates):
        raise ValueError("Số thứ tự nằm ngoài danh sách.")

    return candidates[n - 1]


def kiem_tra_tu_dong(path, data, subset, preview=False):
    if data.get("schema_version") != 2 or "qr_metrics" not in data:
        raise ValueError(
            "Báo cáo QR cũ: chạy lại xuat_va_doi_chieu.py."
        )

    if (
        data.get("subset") != subset
        or data.get("expected_parcels") != 30
    ):
        raise ValueError(
            "Báo cáo QR sai bộ hoặc không có 30 đáp án."
        )

    comparison = doc_csv(path.parent / "comparison.csv")

    if (
        len(comparison) != 30
        or {r["code"] for r in comparison} != bo_ma(subset)
    ):
        raise ValueError(
            "comparison.csv thiếu, lặp hoặc sai mã."
        )

    expected = {}

    for row in comparison:
        gate = nguyen(row["expected_gate"], "expected_gate")

        if (
            gate not in (1, 2, 3)
            or row["expected_status"] != "success"
        ):
            raise ValueError(
                "Đáp án trong comparison.csv không hợp lệ."
            )

        expected[row["code"]] = {
            "expected_gate": gate,
            "expected_status": "success",
        }

    history = doc_csv(path.parent / "history.csv")
    ids, requests = set(), set()

    for row in history:
        for field in ("id", "gate", "success"):
            row[field] = (
                nguyen(row[field], field)
                if row[field] != ""
                else None
            )

        if row["id"] is None or row["success"] not in (0, 1):
            raise ValueError(
                "ID hoặc success trong lịch sử không hợp lệ."
            )

        if row["gate"] not in (None, 1, 2, 3):
            raise ValueError(
                "Cửa trong lịch sử không hợp lệ."
            )

        rid = row["request_id"]

        if not rid or rid in requests or row["id"] in ids:
            raise ValueError(
                "Lịch sử thiếu hoặc lặp ID/request_id."
            )

        if row["session_id"] != data["session"]["id"]:
            raise ValueError(
                "Lịch sử không thuộc phiên đã chọn."
            )

        ids.add(row["id"])
        requests.add(rid)

        row["decision_ms"] = (
            so(row["decision_ms"], "decision_ms")
            if row["decision_ms"] != ""
            else None
        )

        row["measurement"] = None

    measured = doc_csv(path.parent / "qr_measurements.csv")
    by_request = {
        r["request_id"]: r
        for r in history
    }
    seen = set()

    for item in measured:
        rid = item["request_id"]

        if rid not in by_request or rid in seen:
            raise ValueError(
                "Số đo QR có request_id lặp hoặc ngoài lịch sử."
            )

        seen.add(rid)
        row = by_request[rid]

        if (
            item["code"] != row["code"]
            or item["source"] != row["source"]
            or item["session_id"] != row["session_id"]
        ):
            raise ValueError(
                "Số đo QR không khớp lịch sử."
            )

        present = nguyen(
            item["measurement_present"],
            "measurement_present",
        )

        if present not in (0, 1):
            raise ValueError(
                "measurement_present phải là 0 hoặc 1."
            )

        if present:
            m = dict(item)

            for field in ("measurement_version", "valid"):
                m[field] = nguyen(item[field], field)

            for field in TIME_FIELDS:
                m[field] = (
                    so(item[field], field)
                    if item[field] != ""
                    else None
                )

            m["invalid_reason"] = item["invalid_reason"] or None
            row["measurement"] = m

    if any(
        r["source"] == "qr" and r["request_id"] not in seen
        for r in history
    ):
        raise ValueError(
            "qr_measurements.csv thiếu dòng cho lượt QR."
        )

    calculated, checked = doi_chieu(
        data["session"],
        history,
        expected,
        subset,
    )

    check_by_code = {
        r["code"]: r
        for r in calculated
    }

    for row in comparison:
        actual = check_by_code[row["code"]]

        for field in (
            "attempts",
            "first_correct",
            "successful_attempts",
        ):
            khop(row[field], actual[field], field, 0)

        if row["comparison"] != actual["comparison"]:
            raise ValueError(
                "comparison.csv không khớp lịch sử."
            )

    for field in (
        "history_attempts",
        "expected_parcels_attempted",
        "first_attempt_correct_parcels",
        "correctly_completed_parcels",
    ):
        khop(data[field], checked[field], field, 0)

    q = checked["qr_metrics"]
    original = data["qr_metrics"]

    for field in (
        "qr_history_attempts",
        "valid_measurements",
        "invalid_measurements",
        "missing_measurements",
    ):
        khop(original[field], q[field], field, 0)

    for field in TIME_FIELDS:
        for metric, value in q["all_valid_attempts"][field].items():
            khop(
                original["all_valid_attempts"][field][metric],
                value,
                metric,
            )

    if not preview:
        if data["session"]["status"] != "closed":
            raise ValueError(
                "Cần đóng phiên rồi xuất lại báo cáo QR."
            )

        if (
            len(history) != 30
            or len({r["code"] for r in history}) != 30
            or {r["code"] for r in history} != bo_ma(subset)
        ):
            raise ValueError(
                "Lần đánh giá cần đúng 30 mã, mỗi mã một lượt."
            )

        if (
            q["qr_history_attempts"] != 30
            or q["valid_measurements"] != 30
        ):
            raise ValueError(
                "Cần 30 lượt nguồn QR có số đo hợp lệ."
            )

    return checked, calculated


def kiem_tra_thu_cong(path, data, reference):
    if (
        data.get("measurement") != MANUAL_TYPE
        or data.get("schema_version") != 2
    ):
        raise ValueError(
            "Bài thủ công cần đo đọc mã -> tra bảng -> chọn cửa, bản 2."
        )

    if (
        data.get("subset") != "final_test"
        or data.get("expected_parcels") != 30
    ):
        raise ValueError(
            "Bài thủ công cần bộ final_test 30 kiện."
        )

    if nguyen(
        data["interrupted_presentations"],
        "interrupted_presentations",
    ) != 0:
        raise ValueError(
            "Bài thủ công bị ngắt; dùng bài hoàn tất không bị ngắt."
        )

    if type(data.get("shuffle_seed")) is not int:
        raise ValueError(
            "Bài thủ công thiếu seed xáo trộn."
        )

    rows = doc_csv(path.parent / "manual_trials.csv")

    expected = {
        r["code"]: r["expected_gate"]
        for r in reference
    }

    seen, times, correct = set(), [], 0

    for row in rows:
        code = row["code"]

        if code not in expected or code in seen:
            raise ValueError(
                "Bài thủ công lặp mã hoặc sai bộ final_test."
            )

        seen.add(code)

        gate = nguyen(row["expected_gate"], "expected_gate")
        chosen = nguyen(row["chosen_gate"], "chosen_gate")
        answer = nguyen(row["correct"], "correct")

        if chosen not in (1, 2, 3) or gate != expected[code]:
            raise ValueError(
                f"Lựa chọn hoặc đáp án sai định dạng: {code}"
            )

        if answer != int(chosen == gate):
            raise ValueError(
                f"Cột correct không khớp lựa chọn: {code}"
            )

        correct += answer
        times.append(so(row["manual_ms"], "manual_ms"))

    if len(rows) != 30 or seen != set(expected):
        raise ValueError(
            "Bài thủ công chưa hoàn tất 30 kiện."
        )

    if [r["code"] for r in rows] != data.get("trial_order"):
        raise ValueError(
            "Thứ tự bài thủ công không khớp trial_order."
        )

    khop(data["answered"], len(rows), "answered", 0)
    khop(data["correct"], correct, "correct", 0)
    khop(data["manual_ms_sum"], sum(times), "manual_ms_sum")

    stats = thong_ke(times)

    for field, metric in (
        ("manual_ms_mean", "mean"),
        ("manual_ms_median", "median"),
        ("manual_ms_max", "max"),
    ):
        khop(data[field], stats[metric], field)

    khop(
        data["correct_pct_of_full_set"],
        ti_le(correct, 30),
        "correct_pct",
    )

    return rows, stats


def dong_bang(label, attempted, correct, stats, scope):
    return dict(zip(TABLE_FIELDS, [
        label,
        30,
        attempted,
        correct,
        ti_le(correct, attempted),
        ti_le(correct, 30),
        stats["samples"],
        scope,
        stats["mean"],
        stats["median"],
        stats["p95"],
        stats["max"],
    ]))


def tao_html(table, wrong, summary):
    def esc(value):
        return html.escape(
            "Chưa có" if value is None else str(value)
        )

    labels = [
        "Phương pháp / bộ",
        "Số kiện trong bộ",
        "Đã thử",
        "Đúng lần đầu",
        "Đúng / đã thử (%)",
        "Đúng / 30 (%)",
        "Mẫu thời gian",
        "Phạm vi đo",
        "Trung bình (ms)",
        "Trung vị (ms)",
        "P95 (ms)",
        "Lớn nhất (ms)",
    ]

    head = "".join(
        f"<th>{esc(x)}</th>"
        for x in labels
    )

    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{esc(row[key])}</td>"
            for key in TABLE_FIELDS
        )
        + "</tr>"
        for row in table
    )

    notes = "".join(
        f"<li>{esc(x)}</li>"
        for x in summary["notes"]
    )

    sources = "".join(
        f"<li>{esc(k)}: <code>{esc(v)}</code></li>"
        for k, v in summary["sources"].items()
    )

    wrong_html = "".join(
        f"<li>{esc(r['code'])}: chọn cửa {esc(r['chosen_gate'])}, "
        f"đáp án {esc(r['expected_gate'])}.</li>"
        for r in wrong
    ) or (
        "<li>Không có lượt sai trong bài thủ công được chọn, "
        "hoặc chưa chọn bài.</li>"
    )

    return f'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartLogistics QR - Đánh giá</title>
<style>
body {{
    font: 15px/1.6 "Segoe UI", Arial, sans-serif;
    background: #f2f5fa;
    color: #203149;
    margin: 0;
}}
main {{
    max-width: 1400px;
    margin: auto;
    padding: 24px;
}}
section {{
    background: white;
    padding: 22px;
    margin: 18px 0;
    border-radius: 12px;
}}
h1, h2 {{ color: #173a60; }}
.scroll {{ overflow-x: auto; }}
table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 14px;
}}
th, td {{
    padding: 10px;
    border-bottom: 1px solid #ddd;
    text-align: left;
    vertical-align: top;
}}
th {{ background: #edf3fb; }}
code {{ overflow-wrap: anywhere; }}
@media print {{
    body {{ background: white; }}
    main {{ padding: 0; }}
}}
</style>
</head>
<body>
<main>
<section>
    <h1>SmartLogistics QR — Kết quả đánh giá</h1>
    <p><b>{esc(summary["report_status"])}</b></p>
    <p>
        Mô phỏng phân loại ba cửa. Dữ liệu tham chiếu Olist;
        mã kiện và quy tắc do nhóm thiết lập.
    </p>
    <p>
        Thời điểm tổng hợp UTC:
        {esc(summary["created_at_utc"])}
    </p>
</section>
<section>
    <h2>Kết quả các lần thử được chọn</h2>
    <div class="scroll">
        <table>
            <thead><tr>{head}</tr></thead>
            <tbody>{body}</tbody>
        </table>
    </div>
    <p>
        Chênh lệch tỷ lệ đúng final_test
        (tự động trừ thủ công):
        {esc(summary["accuracy_difference_percentage_points"])}
        điểm phần trăm.
    </p>
</section>
<section>
    <h2>Lượt chọn sai thủ công</h2>
    <ul>{wrong_html}</ul>
</section>
<section>
    <h2>Phạm vi và giới hạn</h2>
    <ul>{notes}</ul>
</section>
<section>
    <h2>Nguồn số liệu</h2>
    <ul>{sources}</ul>
    <p>Chỉ tổng hợp, không sửa các báo cáo nguồn.</p>
</section>
</main>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(
        description="Tổng hợp kết quả SmartLogistics QR."
    )

    parser.add_argument(
        "--preview",
        action="store_true",
        help="Xem thử một báo cáo QR.",
    )

    parser.add_argument(
        "--subset",
        choices=["demo", "final_test"],
        default="demo",
    )

    args = parser.parse_args()
    reports = BASE / "reports"

    table, sources, auto_metrics, wrong = [], {}, {}, []
    manual_meta = None
    final = reference = None

    subsets = (
        [args.subset]
        if args.preview
        else ["demo", "final_test"]
    )

    for subset in subsets:
        path, data = chon_bao_cao(
            tim_bao_cao(reports, subset),
            f"tự động {subset}",
        )

        checked, comparison = kiem_tra_tu_dong(
            path,
            data,
            subset,
            args.preview,
        )

        q = checked["qr_metrics"]

        table.append(dong_bang(
            f"Tự động - {subset}",
            checked["expected_parcels_attempted"],
            checked["first_attempt_correct_parcels"],
            q["all_valid_attempts"]["pipeline_ms"],
            "Đọc ảnh QR -> nhận cửa từ prepare; không gồm hoạt ảnh",
        ))

        sources[f"Tự động {subset}"] = str(path.resolve())
        auto_metrics[subset] = q

        if subset == "final_test":
            final, reference = checked, comparison

    difference = None

    if not args.preview:
        path, data = chon_bao_cao(
            tim_bao_cao(
                reports,
                "final_test",
                manual=True,
            ),
            "thủ công final_test",
            manual=True,
        )

        rows, stats = kiem_tra_thu_cong(
            path,
            data,
            reference,
        )

        correct = sum(int(r["correct"]) for r in rows)

        table.append(dong_bang(
            "Thủ công - final_test",
            len(rows),
            correct,
            stats,
            "Hiện mã -> tra bảng mã/điểm đến/cửa -> bấm chọn cửa",
        ))

        wrong = [
            r for r in rows
            if r["correct"] == "0"
        ]

        sources["Thủ công final_test"] = str(path.resolve())

        manual_meta = {
            "participant": data["participant"],
            "shuffle_seed": data["shuffle_seed"],
            "trial_order": data["trial_order"],
            "interrupted_presentations": 0,
            "measurement": MANUAL_TYPE,
        }

        difference = round(
            final["first_attempt_correct_pct_of_full_set"]
            - ti_le(correct, 30),
            2,
        )

    summary = {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_status": (
            "XEM THỬ — CHƯA DÙNG LÀM KẾT QUẢ ĐÁNH GIÁ CHÍNH THỨC"
            if args.preview
            else "TỔNG HỢP CÁC LẦN THỬ ĐỦ BỘ ĐƯỢC CHỌN"
        ),
        "sources": sources,
        "table": table,
        "qr_metrics": auto_metrics,
        "manual": manual_meta,
        "manual_incorrect_trials": wrong,
        "accuracy_difference_percentage_points": difference,
        "speedup_ratio": None,
        "qr_decode_accuracy_pct": None,
        "simulated_throughput_parcels_per_minute": None,
        "notes": [
            (
                "Độ đúng trong bảng là đối chiếu mã/cửa/trạng thái "
                "với đáp án; chưa phải độ chính xác đọc QR "
                "trên toàn bộ ảnh đầu vào."
            ),
            (
                "Thời gian tự động dùng pipeline_ms đã lưu. "
                "Số đo thiếu hoặc bị gián đoạn không được đưa "
                "vào thống kê; xem số mẫu và qr_metrics trong JSON."
            ),
            (
                "Đọc ảnh, gửi/nhận prepare và hoạt ảnh được "
                "thống kê riêng trong JSON; không cộng hoạt ảnh "
                "vào thời gian xác định cửa."
            ),
            (
                "Thủ công dùng bài đọc mã, tra bảng rồi chọn cửa. "
                "Bài cũ chỉ đọc điểm đến không được gộp "
                "vào phép đo mới."
            ),
            (
                "Hai phương pháp có đầu vào và thao tác khác nhau; "
                "không tính tỷ số để kết luận nhanh hơn bao nhiêu lần. "
                "Chưa đo thời gian xử lý vật lý ngoài thực tế."
            ),
            (
                "Mỗi dòng là một lần thử được chọn. Một người "
                "và một lần chạy chưa đủ khái quát; cần nhiều "
                "lần thử với thứ tự xáo trộn và lưu seed."
            ),
            (
                "P95 dùng nearest-rank. Với ít mẫu, P95 có thể "
                "bằng giá trị lớn nhất."
            ),
            (
                "Chưa có kết luận đạt toàn bộ đồ án. Cần đánh giá "
                "riêng ảnh lỗi, gửi lại yêu cầu, đồng thời, "
                "lịch sử và thông lượng mô phỏng."
            ),
        ],
    }

    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S_%fZ"
    )

    folder = reports / f"{stamp}_tong_hop"
    folder.mkdir(parents=True, exist_ok=False)

    ghi_csv(
        folder / "bang_tong_hop.csv",
        TABLE_FIELDS,
        table,
    )

    ghi_csv(
        folder / "kien_sai_thu_cong.csv",
        [
            "code",
            "destination",
            "chosen_gate",
            "expected_gate",
            "manual_ms",
        ],
        wrong,
    )

    (folder / "ket_qua_tong_hop.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    (folder / "bao_cao_danh_gia.html").write_text(
        tao_html(table, wrong, summary),
        encoding="utf-8",
    )

    print("\n" + summary["report_status"])

    for row in table:
        print(
            f"{row['phuong_phap']}: "
            f"đúng {row['dung_lan_dau']}/{row['da_thu']} đã thử; "
            f"{row['so_mau_thoi_gian']} mẫu thời gian; "
            f"trung bình {row['trung_binh_ms']} ms"
        )

    print(f"Đã lưu 4 tệp trong: {folder}")
    print("Mở bao_cao_danh_gia.html bằng trình duyệt.")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        csv.Error,
        OverflowError,
    ) as error:
        raise SystemExit(
            f"Chưa tổng hợp được: {error}"
        )
    except (KeyboardInterrupt, EOFError):
        raise SystemExit("Đã dừng tổng hợp.")