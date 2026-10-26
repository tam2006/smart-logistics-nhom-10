import argparse
import csv
import json
import math
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from xuat_va_doi_chieu import doc_dap_an, ghi_csv


BASE = Path(__file__).resolve().parent
SEED = 20261018
MEASUREMENT = "manual_code_lookup_to_gate_click"


def chuan_bi(base, subset, seed):
    folder = base / "data" / "reference" / subset
    expected = doc_dap_an(
        folder / "expected_answers.csv",
        subset,
    )

    with (folder / "parcels.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        required = {
            "code",
            "destination",
            "destination_key",
            "state",
        }

        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                "parcels.csv thiếu cột mã hoặc điểm đến."
            )

        parcels = {}

        for row in reader:
            item = {
                key: (row[key] or "").strip()
                for key in required
            }

            if (
                not all(item.values())
                or item["code"] in parcels
            ):
                raise ValueError(
                    "Dữ liệu kiện bị thiếu hoặc trùng mã."
                )

            parcels[item["code"]] = item

    if set(parcels) != set(expected):
        raise ValueError("Bộ kiện không khớp bộ đáp án.")

    # Kiểm tra bảng tra và đáp án khớp quy tắc ứng dụng.
    rules = {}

    with (base / "data/processed/routing_rules.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if not {
            "destination_key",
            "state",
            "gate",
        }.issubset(reader.fieldnames or []):
            raise ValueError(
                "routing_rules.csv thiếu cột quy tắc."
            )

        for row in reader:
            key = (
                row["destination_key"].strip(),
                row["state"].strip(),
            )
            gate = int(row["gate"])

            if key in rules or gate not in (1, 2, 3):
                raise ValueError(
                    "Quy tắc cửa bị trùng hoặc không hợp lệ."
                )

            rules[key] = gate

    trials = []

    for code, item in sorted(parcels.items()):
        key = (
            item["destination_key"],
            item["state"],
        )

        if rules.get(key) != expected[code]["expected_gate"]:
            raise ValueError(
                f"Quy tắc và đáp án không khớp: {code}"
            )

        trials.append({
            **item,
            **expected[code],
        })

    random.Random(seed).shuffle(trials)

    return trials


def tong_ket(
    rows,
    trials,
    subset,
    participant,
    interruptions,
    seed,
):
    if not trials or len(rows) > len(trials):
        raise ValueError("Số lượt trả lời không hợp lệ.")

    for number, row in enumerate(rows):
        item = trials[number]

        if (
            row["trial"] != number + 1
            or row["code"] != item["code"]
            or row["chosen_gate"] not in (1, 2, 3)
            or row["expected_gate"] != item["expected_gate"]
            or row["correct"] != int(
                row["chosen_gate"] == item["expected_gate"]
            )
        ):
            raise ValueError(
                "Kết quả không khớp thứ tự hoặc đáp án."
            )

    times = [row["manual_ms"] for row in rows]

    if any(
        not math.isfinite(value) or value < 0
        for value in times
    ):
        raise ValueError("Thời gian đo không hợp lệ.")

    correct = sum(row["correct"] for row in rows)
    total = len(trials)

    return {
        "schema_version": 2,
        "measurement": MEASUREMENT,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "participant": participant,
        "subset": subset,
        "shuffle_seed": seed,
        "trial_order": [
            item["code"] for item in trials
        ],
        "lookup_order": sorted(
            item["code"] for item in trials
        ),
        "expected_parcels": total,
        "answered": len(rows),
        "correct": correct,
        "incorrect": len(rows) - correct,
        "unanswered": total - len(rows),
        "accuracy_pct_of_answered": (
            round(correct * 100 / len(rows), 2)
            if rows else None
        ),
        "correct_pct_of_full_set": round(
            correct * 100 / total,
            2,
        ),
        "manual_ms_mean": (
            round(statistics.mean(times), 3)
            if times else None
        ),
        "manual_ms_median": (
            round(statistics.median(times), 3)
            if times else None
        ),
        "manual_ms_max": (
            round(max(times), 3)
            if times else None
        ),
        "manual_ms_sum": round(sum(times), 3),
        "interrupted_presentations": interruptions,
        "conclusion": (
            "HOAN_TAT"
            if len(rows) == total
            else "CHUA_HOAN_TAT"
        ),
        "notes": [
            "Đo từ lúc bắt đầu hiện mã kiện và bảng tra "
            "đến lúc bấm chọn cửa.",
            "Người thử tự tìm mã trong bảng; "
            "không tự lọc hoặc tô dòng đáp án.",
            "Bảng tra có mã kiện, điểm đến, bang và cửa; "
            "sắp theo mã kiện.",
            "Không tính thời gian nghỉ giữa kiện "
            "hoặc xuất báo cáo.",
            "Tạm dừng bỏ lượt đang đo; "
            "tiếp tục đo lại cùng kiện từ đầu.",
            "Lượt bị ngắt có thể gây hiệu ứng ghi nhớ; "
            "cần công bố số lần ngắt.",
            "Không so trực tiếp thời gian này "
            "với decision_ms backend.",
            "Đây là mô phỏng thao tác tra bảng, "
            "không đo băng chuyền thật.",
            "Chương trình không ghi hoặc sửa "
            "database ứng dụng.",
        ],
    }


def luu_bao_cao(
    base,
    rows,
    trials,
    subset,
    participant,
    interruptions,
    seed,
):
    summary = tong_ket(
        rows,
        trials,
        subset,
        participant,
        interruptions,
        seed,
    )

    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S_%fZ"
    )

    folder = (
        base
        / "reports"
        / f"{stamp}_manual_lookup_{subset}"
    )
    folder.mkdir(parents=True, exist_ok=False)

    fields = [
        "trial",
        "code",
        "destination",
        "state",
        "chosen_gate",
        "expected_gate",
        "correct",
        "manual_ms",
        "recorded_at_utc",
    ]

    ghi_csv(
        folder / "manual_trials.csv",
        fields,
        rows,
    )

    lookup_rows = [
        {
            "code": item["code"],
            "destination": item["destination"],
            "state": item["state"],
            "gate": item["expected_gate"],
        }
        for item in sorted(
            trials,
            key=lambda item: item["code"],
        )
    ]

    ghi_csv(
        folder / "manual_lookup.csv",
        ["code", "destination", "state", "gate"],
        lookup_rows,
    )

    (folder / "manual_summary.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    lines = [
        "SMARTLOGISTICS QR - BASELINE TRA BANG THU CONG",
        (
            f"Người thử: {participant} | "
            f"Bộ: {subset} | Seed: {seed}"
        ),
        f"Đã trả lời: {len(rows)}/{len(trials)}",
        (
            f"Đúng: {summary['correct']} | "
            f"Sai: {summary['incorrect']}"
        ),
        (
            "Độ chính xác trên số đã trả lời: "
            f"{summary['accuracy_pct_of_answered']}%"
        ),
        (
            "Thời gian trung bình đọc mã - tra bảng "
            "- chọn cửa (ms): "
            f"{summary['manual_ms_mean']}"
        ),
        f"Số lần ngắt: {interruptions}",
        f"Kết luận: {summary['conclusion']}",
        "",
        *summary["notes"],
    ]

    (folder / "tong_ket_thu_cong.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8-sig",
    )

    print("\n" + "\n".join(lines))
    print(
        f"\nĐã lưu 4 tệp trong: {folder}",
        flush=True,
    )

    return folder, summary


def mo_cua_so(trials, subset, participant, seed):
    import tkinter as tk
    from tkinter import messagebox, ttk

    window = tk.Tk()
    window.title(
        "SmartLogistics QR - Baseline tra bảng thủ công"
    )
    window.geometry("1000x780")
    window.minsize(820, 680)

    frame = ttk.Frame(window, padding=16)
    frame.pack(fill="both", expand=True)

    rows = []
    index = 0
    started = None
    mode = "ready"
    interruptions = 0
    saved_folder = None

    ttk.Label(
        frame,
        text="ĐỌC MÃ - TRA BẢNG - CHỌN CỬA",
        font=("Segoe UI", 17, "bold"),
    ).pack()

    ttk.Label(
        frame,
        text=(
            f"Bộ: {subset} | Người thử: {participant} "
            f"| Seed: {seed}"
        ),
    ).pack(pady=5)

    ttk.Label(
        frame,
        text=(
            "Tự tìm mã kiện trong bảng bên dưới "
            "rồi bấm cửa tương ứng."
        ),
    ).pack()

    progress = ttk.Label(frame, text="Sẵn sàng")
    progress.pack(pady=5)

    label = ttk.Label(
        frame,
        text="Bấm Bắt đầu để hiện mã kiện.",
        font=("Segoe UI", 24, "bold"),
    )
    label.pack(pady=8)

    table_frame = ttk.Frame(frame)
    table_frame.pack(
        fill="both",
        expand=True,
        pady=8,
    )

    columns = ("code", "destination", "state", "gate")

    table = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings",
        height=13,
        selectmode="none",
    )

    for key, title, width in zip(
        columns,
        ("Mã kiện", "Điểm đến", "Bang", "Cửa"),
        (120, 350, 80, 80),
    ):
        table.heading(key, text=title)
        table.column(
            key,
            width=width,
            anchor="w",
        )

    scrollbar = ttk.Scrollbar(
        table_frame,
        orient="vertical",
        command=table.yview,
    )
    table.configure(
        yscrollcommand=scrollbar.set,
    )

    scrollbar.pack(side="right", fill="y")
    table.pack(
        side="left",
        fill="both",
        expand=True,
    )

    detail = ttk.Label(
        frame,
        text="Bảng tra chỉ hiện khi bắt đầu xử lý kiện.",
        wraplength=900,
    )
    detail.pack(pady=5)

    gate_frame = ttk.Frame(frame)
    gate_frame.pack(pady=6)

    controls = ttk.Frame(frame)
    controls.pack(pady=6)

    gate_buttons = []

    def lock():
        for button in gate_buttons:
            button.configure(state="disabled")

    def hide_lookup():
        table.delete(*table.get_children())

    def save():
        nonlocal saved_folder

        if saved_folder is not None:
            return True

        try:
            saved_folder, _ = luu_bao_cao(
                BASE,
                rows,
                trials,
                subset,
                participant,
                interruptions,
                seed,
            )
            return True

        except (OSError, ValueError, csv.Error) as error:
            messagebox.showerror(
                "Chưa lưu được",
                str(error),
                parent=window,
            )
            return False

    def finish():
        nonlocal mode, started

        mode = "finished"
        started = None

        lock()
        hide_lookup()

        next_button.configure(state="disabled")
        pause_button.configure(state="disabled")

        label.configure(text="Đã kết thúc bài đo")
        progress.configure(
            text=f"Đã trả lời {len(rows)}/{len(trials)}"
        )

        if save():
            detail.configure(
                text=f"Đã lưu: {saved_folder}"
            )
        else:
            detail.configure(
                text=(
                    "Chưa lưu được. "
                    "Bấm Kết thúc / lưu để thử lại."
                )
            )

    def present():
        nonlocal mode, started

        if mode not in ("ready", "between", "paused"):
            return

        if index >= len(trials):
            finish()
            return

        hide_lookup()

        progress.configure(
            text=f"Kiện {index + 1}/{len(trials)}"
        )
        next_button.configure(state="disabled")
        pause_button.configure(state="normal")

        detail.configure(
            text=(
                "Đang đo: đọc mã, tìm dòng trong bảng "
                "và chọn cửa."
            )
        )

        mode = "measuring"

        # Bắt đầu đo ngay trước khi tiết lộ mã và bảng tra.
        started = perf_counter()

        label.configure(text=trials[index]["code"])

        for item in sorted(
            trials,
            key=lambda item: item["code"],
        ):
            table.insert(
                "",
                "end",
                values=(
                    item["code"],
                    item["destination"],
                    item["state"],
                    item["expected_gate"],
                ),
            )

        table.yview_moveto(0)

        for button in gate_buttons:
            button.configure(state="normal")

    def answer(gate):
        nonlocal index, mode, started

        if mode != "measuring" or started is None:
            return

        elapsed = (perf_counter() - started) * 1000

        mode = "between"
        started = None

        lock()
        hide_lookup()

        item = trials[index]

        rows.append({
            "trial": index + 1,
            "code": item["code"],
            "destination": item["destination"],
            "state": item["state"],
            "chosen_gate": gate,
            "expected_gate": item["expected_gate"],
            "correct": int(
                gate == item["expected_gate"]
            ),
            "manual_ms": round(elapsed, 3),
            "recorded_at_utc": (
                datetime.now(timezone.utc).isoformat()
            ),
        })

        index += 1

        pause_button.configure(state="disabled")
        label.configure(text="Đã ghi lựa chọn")
        progress.configure(
            text=f"Đã trả lời {index}/{len(trials)}"
        )
        detail.configure(
            text=(
                "Có thể nghỉ. "
                "Bấm Kiện tiếp theo khi sẵn sàng."
            )
        )

        if index == len(trials):
            finish()
        else:
            next_button.configure(
                state="normal",
                text="Kiện tiếp theo",
            )

    def pause():
        nonlocal mode, started, interruptions

        if mode != "measuring":
            return

        mode = "paused"
        started = None
        interruptions += 1

        lock()
        hide_lookup()

        label.configure(text="Đã tạm dừng")
        detail.configure(
            text=(
                "Đã bỏ số đo đang dở; "
                "tiếp tục đo lại cùng kiện."
            )
        )
        pause_button.configure(state="disabled")
        next_button.configure(
            state="normal",
            text="Tiếp tục cùng kiện",
        )

    def exit_app():
        if mode == "measuring":
            pause()

        if (
            rows
            and saved_folder is None
            and mode != "finished"
        ):
            if not messagebox.askyesno(
                "Kết thúc?",
                "Kết thúc và lưu các kiện đã trả lời?",
                parent=window,
            ):
                return

        if not rows or save():
            window.destroy()
        else:
            finish()

    for gate in (1, 2, 3):
        button = ttk.Button(
            gate_frame,
            text=f"Chọn cửa {gate}",
            state="disabled",
            width=18,
            command=lambda value=gate: answer(value),
        )
        button.pack(side="left", padx=6)
        gate_buttons.append(button)

    next_button = ttk.Button(
        controls,
        text="Bắt đầu",
        command=present,
    )
    next_button.pack(side="left", padx=6)

    pause_button = ttk.Button(
        controls,
        text="Tạm dừng kiện này",
        state="disabled",
        command=pause,
    )
    pause_button.pack(side="left", padx=6)

    ttk.Button(
        controls,
        text="Kết thúc / lưu",
        command=exit_app,
    ).pack(side="left", padx=6)

    ttk.Label(
        frame,
        text=(
            "Giữ cửa sổ hoạt động khi đo. "
            "Chỉ xem điểm số sau khi kết thúc."
        ),
    ).pack(pady=6)

    window.bind(
        "<Unmap>",
        lambda event: (
            pause()
            if event.widget is window
            else None
        ),
    )
    window.protocol("WM_DELETE_WINDOW", exit_app)

    window.mainloop()


def main():
    parser = argparse.ArgumentParser(
        description="Đo baseline tra bảng thủ công."
    )
    parser.add_argument(
        "--subset",
        choices=["demo", "final_test"],
        default="demo",
    )
    parser.add_argument(
        "--participant",
        default="Nguoi_thu_01",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
    )

    args = parser.parse_args()

    if not args.participant.strip():
        raise ValueError(
            "Tên người thử không được để trống."
        )

    trials = chuan_bi(
        BASE,
        args.subset,
        args.seed,
    )

    mo_cua_so(
        trials,
        args.subset,
        args.participant.strip(),
        args.seed,
    )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        csv.Error,
        ImportError,
    ) as error:
        print(
            f"Không chạy được bài đo: {error}",
            file=sys.stderr,
        )
        raise SystemExit(1)