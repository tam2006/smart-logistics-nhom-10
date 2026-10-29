import csv
import io
import hashlib
import json
import math
import re
from contextlib import closing
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

from flask import Blueprint, jsonify, request
from session_routes import ket_noi


history_api = Blueprint("history_api", __name__)


def now():
    return datetime.now(timezone.utc).isoformat()


def loi(status, message, http_code):
    return jsonify(
        status=status,
        message=message,
    ), http_code


def ket_qua_json(row):
    result = dict(row)
    result.pop("request_fingerprint", None)
    result["success"] = bool(result["success"])
    return result


def validate_measurement(data):
    if not isinstance(data, dict):
        raise ValueError(
            "measurement phải là đối tượng JSON."
        )

    allowed = {
        "measurement_version",
        "mode",
        "image_name",
        "image_sha256",
        "read_ms",
        "prepare_ms",
        "pipeline_ms",
        "animation_ms",
        "valid",
        "invalid_reason",
    }

    if set(data) - allowed:
        raise ValueError(
            "measurement chứa trường không được hỗ trợ."
        )

    version = data.get("measurement_version", 1)

    if type(version) is not int or version != 1:
        raise ValueError(
            "measurement_version phải là số nguyên 1."
        )

    mode = data.get("mode")

    if mode not in ("single", "batch"):
        raise ValueError(
            "mode chỉ nhận single hoặc batch."
        )

    name = data.get("image_name")

    if (
        not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 255
    ):
        raise ValueError(
            "image_name phải dài từ 1 đến 255 ký tự."
        )

    digest = data.get("image_sha256")

    if digest is not None:
        if (
            not isinstance(digest, str)
            or re.fullmatch(
                r"[0-9a-fA-F]{64}",
                digest,
            ) is None
        ):
            raise ValueError(
                "image_sha256 phải là chuỗi SHA-256 hợp lệ."
            )

        digest = digest.lower()

    valid = data.get("valid")

    if type(valid) is not bool:
        raise ValueError(
            "valid phải là true hoặc false."
        )

    reason = data.get("invalid_reason")

    if valid:
        if reason is not None:
            raise ValueError(
                "Số đo hợp lệ phải có invalid_reason là null."
            )
    else:
        if (
            not isinstance(reason, str)
            or not 1 <= len(reason.strip()) <= 500
        ):
            raise ValueError(
                "Số đo bị ngắt phải có lý do dài 1 đến 500 ký tự."
            )

        reason = reason.strip()

    result = {
        "measurement_version": version,
        "mode": mode,
        "image_name": name.strip(),
        "image_sha256": digest,
        "valid": int(valid),
        "invalid_reason": reason,
    }

    for key in (
        "read_ms",
        "prepare_ms",
        "pipeline_ms",
        "animation_ms",
    ):
        value = data.get(key)

        if value is None and not valid:
            result[key] = None
            continue

        if type(value) not in (int, float):
            raise ValueError(
                f"{key} phải là số mili giây không âm."
            )

        try:
            value = float(value)
        except (OverflowError, ValueError):
            raise ValueError(
                f"{key} vượt phạm vi số hợp lệ."
            ) from None

        if not math.isfinite(value) or value < 0:
            raise ValueError(
                f"{key} phải hữu hạn và không âm."
            )

        result[key] = value

    if valid and result["pipeline_ms"] < max(
        result["read_ms"],
        result["prepare_ms"],
    ):
        raise ValueError(
            "pipeline_ms không được nhỏ hơn "
            "read_ms hoặc prepare_ms."
        )

    return result


def decide(conn, code, source, session_id):
    start = perf_counter()

    destination = None
    gate = None
    success = 0

    if code == "" and source == "qr":
        status = "qr_unreadable"
        reason = "Không đọc được mã QR."

    elif re.fullmatch(r"KH[0-9]{3}", code) is None:
        status = "invalid_code"
        reason = "Mã kiện phải có dạng KH001."

    else:
        parcel = conn.execute(
            "SELECT * FROM parcels WHERE code = ?",
            (code,),
        ).fetchone()

        if parcel is None:
            status = "not_found"
            reason = "Mã kiện không tồn tại."

        elif any(
            not (parcel[field] or "").strip()
            for field in (
                "destination",
                "destination_key",
                "state",
            )
        ):
            status = "missing_destination"
            reason = "Kiện thiếu thông tin điểm đến."

        else:
            destination = parcel["destination"]

            rule = conn.execute(
                """
                SELECT gate
                FROM routing_rules
                WHERE destination_key = ? AND state = ?
                """,
                (
                    parcel["destination_key"],
                    parcel["state"],
                ),
            ).fetchone()

            completed = conn.execute(
                """
                SELECT id
                FROM history
                WHERE session_id = ?
                  AND code = ?
                  AND success = 1
                """,
                (session_id, code),
            ).fetchone()

            if rule is None:
                status = "unconfigured_destination"
                reason = "Điểm đến chưa được cấu hình cửa."

            elif completed is not None:
                status = "duplicate"
                reason = "Kiện đã hoàn tất trong phiên này."

            else:
                gate = rule["gate"]
                success = 1
                status = "success"
                reason = f"Đã ghi nhận hoàn tất tại cửa {gate}."

    return dict(
        code=code,
        source=source,
        session_id=session_id,
        destination=destination,
        gate=gate,
        success=success,
        status=status,
        reason=reason,
        decision_ms=round(
            (perf_counter() - start) * 1000,
            3,
        ),
    )


def pending_json(row):
    result = json.loads(row["outcome_json"])
    result["request_id"] = row["request_id"]
    result["success"] = False

    if result["status"] == "success":
        result["status"] = "ready"
        result["reason"] = (
            f"Đã xác định cửa {result['gate']}; "
            "chờ mô phỏng hoàn tất."
        )

    return dict(
        phase="pending",
        result=result,
    )


@history_api.post("/api/history")
def old_api():
    return loi(
        "two_phase_required",
        "Dùng API prepare rồi complete để xử lý kiện.",
        409,
    )


@history_api.post("/api/history/prepare")
def prepare():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return loi(
            "invalid_input",
            "Cần gửi một đối tượng JSON.",
            400,
        )

    try:
        if not all(
            isinstance(data.get(key), str)
            for key in ("session_id", "request_id")
        ):
            raise ValueError

        sid = str(UUID(data["session_id"]))
        rid = str(UUID(data["request_id"]))

    except ValueError:
        return loi(
            "invalid_input",
            "session_id và request_id phải là UUID.",
            400,
        )

    code = data.get("code")
    source = data.get("source", "api")

    if (
        not isinstance(code, str)
        or len(code) > 64
        or source not in ("manual", "qr", "auto", "api")
    ):
        return loi(
            "invalid_input",
            "Mã kiện hoặc nguồn nhập không hợp lệ.",
            400,
        )

    content = json.dumps(
        dict(
            session_id=sid,
            code=code,
            source=source,
        ),
        sort_keys=True,
        ensure_ascii=False,
    )

    fingerprint = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()

    with closing(ket_noi()) as conn:
        with conn:
            conn.execute("BEGIN IMMEDIATE")

            old = conn.execute(
                "SELECT * FROM history WHERE request_id = ?",
                (rid,),
            ).fetchone()

            pending = conn.execute(
                """
                SELECT *
                FROM processing_requests
                WHERE request_id = ?
                """,
                (rid,),
            ).fetchone()

            existing = old if old is not None else pending

            if existing is not None:
                if (
                    existing["request_fingerprint"]
                    != fingerprint
                ):
                    return loi(
                        "request_id_conflict",
                        "request_id đã dùng cho nội dung khác.",
                        409,
                    )

                if old is not None:
                    return jsonify(
                        phase="completed",
                        result=ket_qua_json(old),
                    ), 200

                return jsonify(pending_json(pending)), 200

            session = conn.execute(
                "SELECT status FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()

            if session is None:
                return loi(
                    "session_not_found",
                    "Phiên không tồn tại.",
                    404,
                )

            if session["status"] != "active":
                return loi(
                    "session_closed",
                    "Phiên đã đóng.",
                    409,
                )

            occupied = conn.execute(
                """
                SELECT request_id
                FROM processing_requests
                WHERE session_id = ?
                  AND completed_at IS NULL
                """,
                (sid,),
            ).fetchone()

            if occupied is not None:
                return loi(
                    "session_busy",
                    "Phiên còn lượt chưa hoàn tất. "
                    "Bấm Làm mới để khôi phục.",
                    409,
                )

            outcome = decide(conn, code, source, sid)

            conn.execute(
                """
                INSERT INTO processing_requests (
                    request_id,
                    request_fingerprint,
                    session_id,
                    code,
                    source,
                    outcome_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    fingerprint,
                    sid,
                    code,
                    source,
                    json.dumps(outcome, ensure_ascii=False),
                    now(),
                ),
            )

            row = conn.execute(
                """
                SELECT *
                FROM processing_requests
                WHERE request_id = ?
                """,
                (rid,),
            ).fetchone()

    return jsonify(pending_json(row)), 201


@history_api.get("/api/sessions/<session_id>/pending")
def get_pending(session_id):
    try:
        sid = str(UUID(session_id))
    except ValueError:
        return loi(
            "invalid_input",
            "Mã phiên phải là UUID.",
            400,
        )

    with closing(ket_noi()) as conn:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (sid,),
        ).fetchone()

        if session is None:
            return loi(
                "session_not_found",
                "Phiên không tồn tại.",
                404,
            )

        row = conn.execute(
            """
            SELECT *
            FROM processing_requests
            WHERE session_id = ?
              AND completed_at IS NULL
            """,
            (sid,),
        ).fetchone()

    payload = None

    if row is not None:
        payload = dict(
            session_id=row["session_id"],
            request_id=row["request_id"],
            code=row["code"],
            source=row["source"],
        )

    return jsonify(pending=payload), 200


@history_api.post("/api/history/<request_id>/complete")
def complete(request_id):
    try:
        rid = str(UUID(request_id))
    except ValueError:
        return loi(
            "invalid_input",
            "Mã lượt phải là UUID.",
            400,
        )

    with closing(ket_noi()) as conn:
        with conn:
            conn.execute("BEGIN IMMEDIATE")

            old = conn.execute(
                "SELECT * FROM history WHERE request_id = ?",
                (rid,),
            ).fetchone()

            # Lượt cũ chỉ trả kết quả, không ghi đè số đo.
            if old is not None:
                return jsonify(ket_qua_json(old)), 200

            pending = conn.execute(
                """
                SELECT *
                FROM processing_requests
                WHERE request_id = ?
                """,
                (rid,),
            ).fetchone()

            if pending is None:
                return loi(
                    "request_not_found",
                    "Lượt xử lý không tồn tại.",
                    404,
                )

            session = conn.execute(
                "SELECT status FROM sessions WHERE id = ?",
                (pending["session_id"],),
            ).fetchone()

            if session["status"] != "active":
                return loi(
                    "session_closed",
                    "Phiên đã đóng.",
                    409,
                )

            # Giao diện cũ có thể chưa gửi số đo.
            measurement = None

            if request.get_data():
                body = request.get_json(silent=True)

                if (
                    not isinstance(body, dict)
                    or set(body) - {"measurement"}
                ):
                    return loi(
                        "invalid_input",
                        "Body chỉ nhận đối tượng "
                        "có trường measurement.",
                        400,
                    )

                if "measurement" in body:
                    if pending["source"] != "qr":
                        return loi(
                            "invalid_input",
                            "Chỉ lượt có nguồn qr "
                            "mới được gửi số đo QR.",
                            400,
                        )

                    try:
                        measurement = validate_measurement(
                            body["measurement"]
                        )
                    except ValueError as error:
                        return loi(
                            "invalid_measurement",
                            str(error),
                            400,
                        )

            # Cửa và trạng thái lấy từ quyết định backend.
            result = json.loads(pending["outcome_json"])

            result.update(
                request_id=rid,
                request_fingerprint=(
                    pending["request_fingerprint"]
                ),
                created_at=now(),
            )

            if result["success"]:
                completed = conn.execute(
                    """
                    SELECT id
                    FROM history
                    WHERE session_id = ?
                      AND code = ?
                      AND success = 1
                    """,
                    (
                        result["session_id"],
                        result["code"],
                    ),
                ).fetchone()

                if completed is not None:
                    result.update(
                        success=0,
                        status="duplicate",
                        gate=None,
                        reason=(
                            "Kiện đã hoàn tất trong phiên này."
                        ),
                    )

            cursor = conn.execute(
                """
                INSERT INTO history (
                    request_id,
                    request_fingerprint,
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
                )
                VALUES (
                    :request_id,
                    :request_fingerprint,
                    :session_id,
                    :code,
                    :destination,
                    :gate,
                    :success,
                    :status,
                    :reason,
                    :source,
                    :decision_ms,
                    :created_at
                )
                """,
                result,
            )

            # Lưu lịch sử và số đo trong cùng một giao dịch.
            if measurement is not None:
                measurement.update(
                    request_id=rid,
                    created_at=result["created_at"],
                )

                conn.execute(
                    """
                    INSERT INTO qr_measurements (
                        request_id,
                        measurement_version,
                        mode,
                        image_name,
                        image_sha256,
                        read_ms,
                        prepare_ms,
                        pipeline_ms,
                        animation_ms,
                        valid,
                        invalid_reason,
                        created_at
                    )
                    VALUES (
                        :request_id,
                        :measurement_version,
                        :mode,
                        :image_name,
                        :image_sha256,
                        :read_ms,
                        :prepare_ms,
                        :pipeline_ms,
                        :animation_ms,
                        :valid,
                        :invalid_reason,
                        :created_at
                    )
                    """,
                    measurement,
                )

            conn.execute(
                """
                UPDATE processing_requests
                SET completed_at = ?
                WHERE request_id = ?
                """,
                (
                    result["created_at"],
                    rid,
                ),
            )

            result["id"] = cursor.lastrowid

    return jsonify(ket_qua_json(result)), 201


@history_api.get("/api/history/<request_id>/measurement")
def xem_so_do(request_id):
    try:
        rid = str(UUID(request_id))
    except ValueError:
        return loi(
            "invalid_input",
            "Mã lượt phải là UUID.",
            400,
        )

    with closing(ket_noi()) as conn:
        old = conn.execute(
            "SELECT id FROM history WHERE request_id = ?",
            (rid,),
        ).fetchone()

        if old is None:
            return loi(
                "request_not_found",
                "Chưa có lượt hoàn tất này.",
                404,
            )

        row = conn.execute(
            """
            SELECT *
            FROM qr_measurements
            WHERE request_id = ?
            """,
            (rid,),
        ).fetchone()

    measurement = dict(row) if row is not None else None

    if measurement is not None:
        measurement["valid"] = bool(measurement["valid"])

    return jsonify(
        request_id=rid,
        measurement=measurement,
    ), 200


@history_api.get("/api/history")
def xem_lich_su():
    session_id = request.args.get("session_id")
    limit_text = request.args.get("limit", "100")
    before_text = request.args.get("before_id")

    if re.fullmatch(r"[0-9]{1,3}", limit_text) is None:
        return loi(
            "invalid_input",
            "limit phải là số nguyên từ 1 đến 100.",
            400,
        )

    limit = int(limit_text)

    if not 1 <= limit <= 100:
        return loi(
            "invalid_input",
            "limit phải là số nguyên từ 1 đến 100.",
            400,
        )

    before_id = None

    if before_text is not None:
        if re.fullmatch(r"[0-9]{1,19}", before_text) is None:
            return loi(
                "invalid_input",
                "before_id phải là ID nguyên dương hợp lệ.",
                400,
            )

        before_id = int(before_text)

        if not 1 <= before_id <= 9223372036854775807:
            return loi(
                "invalid_input",
                "before_id phải là ID nguyên dương hợp lệ.",
                400,
            )

    if session_id is not None:
        try:
            session_id = str(UUID(session_id))
        except ValueError:
            return loi(
                "invalid_input",
                "session_id phải là UUID hợp lệ.",
                400,
            )

    with closing(ket_noi()) as conn:
        if session_id is not None:
            session = conn.execute(
                "SELECT id FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()

            if session is None:
                return loi(
                    "session_not_found",
                    "Phiên chạy không tồn tại.",
                    404,
                )

        conditions = []
        params = []

        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)

        if before_id is not None:
            conditions.append("id < ?")
            params.append(before_id)

        sql = "SELECT * FROM history"

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit + 1)

        rows = conn.execute(sql, params).fetchall()

    has_more = len(rows) > limit
    page = rows[:limit]

    return jsonify(
        history=[ket_qua_json(row) for row in page],
        limit=limit,
        has_more=has_more,
        next_before_id=(
            page[-1]["id"] if has_more else None
        ),
    )
    @history_api.get("/api/history/export-csv")
def export_session_csv():
    session_id = request.args.get("session_id")
    
    if not session_id:
        return loi("invalid_input", "Chưa chọn phiên làm việc.", 400)

    try:
        sid = str(UUID(session_id))
    except ValueError:
        return loi("invalid_input", "session_id phải là UUID hợp lệ.", 400)

    with closing(ket_noi()) as conn:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (sid,),
        ).fetchone()

        if session is None:
            return loi("session_not_found", "Phiên chạy không tồn tại.", 404)

        # LẤY TOÀN BỘ LỊCH SỬ CỦA PHIÊN (Không phân trang, lấy hết tất cả các trang)
        rows = conn.execute(
            """
            SELECT * FROM history
            WHERE session_id = ?
            ORDER BY id DESC
            """,
            (sid,),
        ).fetchall()

        if not rows:
            return loi("empty_session", "Phiên hiện tại không có dữ liệu lịch sử.", 404)

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Tiêu đề cột đã thống nhất: Mã lượt, Mã kiện, Điểm đến, Cửa, Trạng thái, Lý do, Nguồn nhập, Thời gian ghi nhận
        writer.writerow([
            "Mã lượt", 
            "Mã kiện", 
            "Điểm đến", 
            "Cửa", 
            "Trạng thái", 
            "Lý do", 
            "Nguồn nhập", 
            "Thời gian ghi nhận"
        ])

        for row in rows:
            res = dict(row)
            writer.writerow([
                res.get("request_id", ""),
                res.get("code", ""),
                res.get("destination", ""),
                res.get("gate", ""),
                res.get("status", ""),
                res.get("reason", ""),
                res.get("source", ""),
                res.get("created_at", "")
            ])

        csv_data = output.getvalue().encode("utf-8-sig")
        output.close()

        filename = f"lich_su_phien_{sid}.csv"
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
