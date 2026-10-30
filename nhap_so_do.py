"""Kiểm tra JSON đo độc lập trước khi đưa vào báo cáo."""

import csv
import hashlib
import html
import json
import math
import re
import shutil
from datetime import datetime
from pathlib import Path


def can(condition, message):
    if not condition:
        raise ValueError("Số đo bổ sung: " + message)


def doc(path):
    def pairs(items):
        result = {}

        for key, value in items:
            can(key not in result, f"JSON lặp khóa {key}")
            result[key] = value

        return result

    with Path(path).open(encoding="utf-8-sig") as f:
        result = json.load(f, object_pairs_hook=pairs)

    can(isinstance(result, dict), "JSON phải là đối tượng")
    return result


def so(value):
    can(
        type(value) in (int, float)
        and math.isfinite(value)
        and value >= 0,
        "thời gian hoặc tỷ lệ không hợp lệ",
    )
    return value


def bang(actual, expected, label):
    if expected is None:
        can(actual is None, f"{label} phải để trống")

    elif type(expected) is int:
        can(
            type(actual) is int and actual == expected,
            f"{label} không khớp",
        )

    else:
        can(
            math.isclose(
                so(actual),
                expected,
                rel_tol=1e-8,
                abs_tol=0.011,
            ),
            f"{label} không khớp",
        )


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ten(value):
    can(
        isinstance(value, str)
        and value not in ("", ".", "..")
        and not any(c in value for c in "/\\:"),
        "tên ảnh không hợp lệ",
    )

    can(
        Path(value).suffix.lower() in (".png", ".jpg", ".jpeg"),
        "sai loại ảnh",
    )

    return value


def thoi_diem(report):
    start = datetime.fromisoformat(
        report["started_at"].replace("Z", "+00:00")
    )
    end = datetime.fromisoformat(
        report["finished_at"].replace("Z", "+00:00")
    )

    can(
        start.tzinfo is not None
        and end.tzinfo is not None
        and end >= start,
        "mốc thời gian thiếu múi giờ hoặc bị đảo",
    )

    return (end - start).total_seconds() * 1000


def dap_an(path):
    with Path(path).open(
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.DictReader(f, strict=True)
        fields = reader.fieldnames or []

        can(
            len(fields) == len(set(fields)),
            "CSV lặp tiêu đề",
        )

        explicit = {
            "image_name",
            "expected_payload",
        }.issubset(fields)

        can(
            explicit
            or {"code", "qr_payload"}.issubset(fields),
            "CSV thiếu cột đáp án",
        )

        result = {}

        for row in reader:
            can(
                None not in row
                and all(v is not None for v in row.values()),
                "CSV sai số cột",
            )

            name = (
                row["image_name"].strip()
                if explicit
                else row["code"].strip() + ".png"
            )

            payload = (
                row["expected_payload"]
                if explicit
                else row["qr_payload"]
            )

            ten(name)
            can(name not in result, "CSV lặp tên ảnh")

            can(
                explicit or bool(payload.strip()),
                "đáp án QR rỗng",
            )

            result[name] = payload

    can(bool(result), "CSV chưa có đáp án")
    return result


def kiem_qr(path, manifest, images, expected):
    data = doc(path)

    can(
        type(data.get("schema_version")) is int
        and data["schema_version"] == 1,
        "phiên bản JSON QR chưa hỗ trợ",
    )

    can(
        data.get("decoder_version") == "jsqr-canvas-v1",
        "sai phiên bản đọc QR",
    )

    thoi_diem(data)

    can(
        data.get("manifest_sha256") == sha(manifest),
        "CSV khác tệp đã dùng khi đo",
    )

    answers = dap_an(manifest)
    rows = data["results"]

    can(
        isinstance(rows, list)
        and len(rows) == len(answers),
        "JSON QR thiếu dòng",
    )

    seen = set()
    positive = 0
    negative = 0
    good_pos = 0
    good_neg = 0
    missing = 0
    errors = 0

    for row in rows:
        name = ten(row["image_name"])

        can(
            name in answers and name not in seen,
            "JSON QR lặp ảnh hoặc ngoài đáp án",
        )

        seen.add(name)

        payload = answers[name]
        is_qr = payload != ""

        can(
            row.get("expected_payload") == payload
            and row.get("expects_qr") is is_qr,
            "đáp án trong JSON khác CSV",
        )

        positive += int(is_qr)
        negative += int(not is_qr)

        state = row.get("status")
        image = Path(images) / name

        if state in ("missing_file", "file_error"):
            can(
                row.get("correct") is False,
                "ảnh thiếu/lỗi không thể đúng",
            )

            missing += int(state == "missing_file")
            errors += int(state == "file_error")
            continue

        can(
            image.is_file(),
            f"không có ảnh nguồn {name}",
        )

        can(
            row.get("image_sha256") == sha(image),
            f"ảnh {name} khác ảnh đã đo",
        )

        found = row.get("found")
        actual = row.get("decoded_payload")

        can(
            type(found) is bool
            and isinstance(actual, str),
            "kết quả giải mã sai kiểu",
        )

        can(
            found or actual == "",
            "không tìm thấy QR nhưng vẫn có nội dung",
        )

        correct = (
            found and actual == payload
            if is_qr
            else not found
        )

        if correct:
            status = "correct"
        elif is_qr and not found:
            status = "unreadable"
        elif is_qr:
            status = "mismatch"
        else:
            status = "false_positive"

        can(
            row.get("correct") is correct
            and state == status,
            "kết quả QR không nhất quán",
        )

        so(row["read_ms"])

        good_pos += int(is_qr and correct)
        good_neg += int(not is_qr and correct)

    def rate(numerator, denominator):
        if denominator == 0:
            return None

        return numerator * 100 / denominator

    calculated = {
        "expected_images": len(answers),
        "correct_images": good_pos + good_neg,
        "positive_images": positive,
        "negative_images": negative,
        "qr_decode_accuracy_pct": rate(good_pos, positive),
        "no_qr_correct_rejection_pct": rate(
            good_neg,
            negative,
        ),
        "overall_expected_result_pct": rate(
            good_pos + good_neg,
            len(answers),
        ),
        "missing_images": missing,
        "file_errors": errors,
    }

    for key, value in calculated.items():
        bang(data["summary"].get(key), value, key)

    timing = data.get("timing_valid")

    can(
        type(timing) is bool,
        "thiếu trạng thái đo thời gian QR",
    )

    can(
        (
            timing
            and data.get("timing_invalid_reason") is None
        )
        or (
            not timing
            and bool(data.get("timing_invalid_reason"))
        ),
        "lý do gián đoạn QR không khớp",
    )

    complete = not missing and not errors

    codes = [
        value
        for value in answers.values()
        if value != ""
    ]

    full = (
        len(codes) == len(expected)
        and set(codes) == set(expected)
    )

    return {
        "run_id": data["run_id"],
        "summary": calculated,
        "usable_accuracy": complete,
        "timing_valid": timing,
        "matches_full_reference": full,
        "exclusion_reasons": (
            []
            if complete
            else ["Thiếu ảnh hoặc lỗi tệp"]
        ),
        "qr_decode_accuracy_pct": (
            calculated["qr_decode_accuracy_pct"]
            if complete
            else None
        ),
    }


def kiem_nang_suat(path, session, history, expected):
    data = doc(path)

    can(
        type(data.get("schema_version")) is int
        and data["schema_version"] == 1
        and data.get("metric")
        == "batch_simulation_throughput"
        and data.get("measurement_version")
        == "batch-throughput-v1",
        "sai phiên bản năng suất",
    )

    wall = thoi_diem(data)

    can(
        data.get("session_id") == session["id"],
        "JSON năng suất thuộc phiên khác",
    )

    can(
        data.get("decoder_version") == "jsqr-canvas-v1",
        "sai bộ đọc năng suất",
    )

    can(
        data.get("finished") is True,
        "lô chưa hoàn tất",
    )

    valid = data.get("valid")
    reasons = data.get("invalid_reasons")

    can(
        type(valid) is bool
        and isinstance(reasons, list)
        and all(
            isinstance(reason, str) and reason
            for reason in reasons
        ),
        "sai trạng thái năng suất",
    )

    can(
        valid == (not reasons),
        "trạng thái và lý do loại không khớp",
    )

    elapsed = so(data["elapsed_ms"])

    can(
        elapsed > 0,
        "thời gian lô phải lớn hơn 0",
    )

    so(data["configured_delay_ms"])
    so(data["configured_animation_ms"])

    rows = data["results"]

    can(
        isinstance(rows, list) and bool(rows),
        "lô chưa có kết quả",
    )

    db = {
        row["request_id"]: row
        for row in history
    }

    can(
        len(db) == len(history),
        "lịch sử lặp request_id",
    )

    requests = set()
    names = set()
    codes = []
    acknowledgements = []

    successes = 0
    confirmed = 0
    errors = 0

    for index, row in enumerate(rows, 1):
        bang(row.get("index"), index, "index")

        name = ten(row["image_name"])
        can(name not in names, "lô lặp tên ảnh")
        names.add(name)

        rid = row.get("request_id")

        can(
            type(row.get("success")) is bool,
            "success phải là boolean",
        )

        if rid is None:
            can(
                row.get("history_id") is None
                and row["success"] is False
                and row.get(
                    "completion_ack_ms_from_start"
                ) is None
                and bool(row.get("error")),
                "lỗi tệp chứa xác nhận lịch sử",
            )

            errors += 1
            continue

        can(
            rid in db and rid not in requests,
            "request_id lặp hoặc không thuộc lịch sử phiên",
        )

        requests.add(rid)
        saved = db[rid]

        can(
            saved["session_id"] == session["id"]
            and saved["source"] == "qr",
            "nguồn lịch sử sai",
        )

        for key, db_key in (
            ("history_id", "id"),
            ("decoded_code", "code"),
            ("gate", "gate"),
            ("status", "status"),
        ):
            can(
                row.get(key) == saved[db_key],
                f"{key} khác database",
            )

        can(
            row["success"] == (saved["success"] == 1),
            "thành công khác database",
        )

        measurement = saved.get("measurement") or {}

        can(
            measurement.get("image_name") == name
            and measurement.get("image_sha256")
            == row.get("image_sha256")
            and re.fullmatch(
                r"[0-9a-f]{64}",
                row.get("image_sha256") or "",
            ) is not None,
            "tên/hash ảnh không khớp số đo đã lưu",
        )

        ack = so(row["completion_ack_ms_from_start"])

        can(
            ack <= elapsed + 0.01
            and (
                not acknowledgements
                or ack >= acknowledgements[-1]
            ),
            "thứ tự hoặc mốc hoàn tất không hợp lệ",
        )

        acknowledgements.append(ack)

        confirmed += 1
        successes += int(row["success"])
        codes.append(saved["code"])

    counts = {
        "input_images": len(rows),
        "confirmed_history_rows": confirmed,
        "successful_parcels": successes,
        "business_error_rows": confirmed - successes,
        "file_errors": errors,
    }

    for key, value in counts.items():
        bang(data.get(key), value, key)

    if valid:
        can(
            abs(wall - elapsed) <= 1000,
            "hai đồng hồ chênh lệch quá lớn",
        )

        if rows[-1].get("request_id") is not None:
            can(
                abs(
                    acknowledgements[-1] - elapsed
                ) <= 0.01,
                "lô kết thúc khác xác nhận cuối",
            )

    rate = (
        successes * 60000 / elapsed
        if valid
        else None
    )

    outcome_rate = (
        confirmed * 60000 / elapsed
        if valid
        else None
    )

    bang(
        data.get("simulated_throughput_parcels_per_min"),
        rate,
        "năng suất",
    )

    bang(
        data.get("confirmed_outcomes_per_min"),
        outcome_rate,
        "lượt/phút",
    )

    full = (
        not errors
        and len(codes) == len(expected)
        and set(codes) == set(expected)
        and requests == set(db)
        and session["status"] == "closed"
    )

    return {
        "run_id": data["run_id"],
        "session_id": session["id"],
        "valid": valid,
        "exclusion_reasons": reasons,
        "matches_full_reference": full,
        "input_images": len(rows),
        "successful_parcels": successes,
        "confirmed_history_rows": confirmed,
        "business_error_rows": confirmed - successes,
        "file_errors": errors,
        "elapsed_ms": elapsed,
        "configured_delay_ms": data["configured_delay_ms"],
        "configured_animation_ms": (
            data["configured_animation_ms"]
        ),
        "simulated_throughput_parcels_per_minute": rate,
    }


def nhap(
    qr,
    manifest,
    images,
    throughput,
    session,
    history,
    expected,
):
    can(
        all((qr, manifest, images))
        or not any((qr, manifest, images)),
        (
            "cần đủ --qr-evaluation, "
            "--qr-manifest và --qr-images"
        ),
    )

    return {
        "schema_version": 1,
        "qr": (
            kiem_qr(qr, manifest, images, expected)
            if qr
            else None
        ),
        "throughput": (
            kiem_nang_suat(
                throughput,
                session,
                history,
                expected,
            )
            if throughput
            else None
        ),
    }


def gan(summary, metrics):
    summary["independent_metrics"] = metrics

    summary["qr_decode_accuracy_pct"] = (
        metrics.get("qr") or {}
    ).get("qr_decode_accuracy_pct")

    summary["simulated_throughput_parcels_per_minute"] = (
        metrics.get("throughput") or {}
    ).get("simulated_throughput_parcels_per_minute")


def luu(folder, qr, manifest, images, throughput):
    if not qr and not throughput:
        return

    root = Path(folder) / "so_do_nguon"
    root.mkdir()

    if qr:
        shutil.copyfile(
            qr,
            root / "qr_evaluation.json",
        )

        shutil.copyfile(
            manifest,
            root / "answers.csv",
        )

        target = root / "images"
        target.mkdir()

        for name in dap_an(manifest):
            image = Path(images) / name

            if image.is_file():
                shutil.copyfile(
                    image,
                    target / name,
                )

    if throughput:
        shutil.copyfile(
            throughput,
            root / "batch_throughput.json",
        )


def doc_lai(
    folder,
    session,
    history,
    expected,
    formal=False,
):
    root = Path(folder) / "so_do_nguon"

    qr = root / "qr_evaluation.json"
    throughput = root / "batch_throughput.json"

    has_qr = qr.is_file()
    has_throughput = throughput.is_file()

    result = nhap(
        qr if has_qr else None,
        root / "answers.csv" if has_qr else None,
        root / "images" if has_qr else None,
        throughput if has_throughput else None,
        session,
        history,
        expected,
    )

    if formal:
        q = result["qr"]
        t = result["throughput"]

        can(
            q is not None
            and q["usable_accuracy"]
            and q["matches_full_reference"],
            (
                "báo cáo chính thức cần đánh giá QR đủ bộ, "
                "không thiếu ảnh/lỗi tệp"
            ),
        )

        can(
            t is not None
            and t["valid"]
            and t["matches_full_reference"],
            (
                "báo cáo chính thức cần năng suất hợp lệ, "
                "đủ bộ và phiên đã đóng"
            ),
        )

    return result


def van_ban(metrics):
    lines = ["SO DO DOC LAP DA DOI CHIEU:"]

    q = metrics.get("qr")
    t = metrics.get("throughput")

    if q:
        s = q["summary"]

        lines.extend([
            (
                f"QR: {q['qr_decode_accuracy_pct']}% "
                f"trên {s['positive_images']} ảnh có QR."
            ),
            (
                "Từ chối đúng ảnh không QR: "
                f"{s['no_qr_correct_rejection_pct']}% "
                f"({s['negative_images']} ảnh)."
            ),
            (
                "QR đủ bộ tham chiếu: "
                f"{q['matches_full_reference']}; "
                "thời gian hợp lệ: "
                f"{q['timing_valid']}."
            ),
        ])

        lines.extend(q["exclusion_reasons"])

    else:
        lines.append("Chưa nhập JSON đánh giá QR.")

    if t:
        lines.extend([
            (
                "Năng suất mô phỏng: "
                f"{t['simulated_throughput_parcels_per_minute']} "
                "kiện/phút."
            ),
            (
                f"{t['successful_parcels']} kiện thành công / "
                f"{t['elapsed_ms']} ms; "
                f"đầu vào {t['input_images']} ảnh."
            ),
            (
                "Năng suất đủ bộ và phiên đóng: "
                f"{t['matches_full_reference']}."
            ),
        ])

        lines.extend(t["exclusion_reasons"])

    else:
        lines.append("Chưa nhập JSON năng suất.")

    lines.append(
        "Số liệu chỉ mô tả lần thử đã chọn; "
        "không phải năng suất băng chuyền thật."
    )

    return "\n".join(lines) + "\n"


def html_so_do(by_subset):
    parts = []

    for subset, metrics in by_subset.items():
        parts.append(
            "<section><h2>Số đo độc lập — "
            + html.escape(subset)
            + "</h2><pre style='white-space:pre-wrap'>"
            + html.escape(van_ban(metrics))
            + "</pre></section>"
        )

    return "".join(parts)