import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from flask import Blueprint, jsonify, request


BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "instance" / "smartlogistics.db"

session_api = Blueprint("session_api", __name__)


def ket_noi():
    conn = sqlite3.connect(
        DB_PATH.resolve().as_uri() + "?mode=rw",
        uri=True,
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


@session_api.post("/api/sessions")
def tao_phien():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            status="invalid_input",
            message="Cần gửi một đối tượng JSON.",
        ), 400

    name = data.get("name", "Phiên mô phỏng")

    if (
        not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 100
    ):
        return jsonify(
            status="invalid_input",
            message="Tên phiên phải dài từ 1 đến 100 ký tự.",
        ), 400

    session = {
        "id": str(uuid4()),
        "name": name.strip(),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "closed_at": None,
    }

    with closing(ket_noi()) as conn:
        with conn:
            conn.execute("""
                INSERT INTO sessions (
                    id, name, status, created_at, closed_at
                )
                VALUES (
                    :id, :name, :status, :created_at, :closed_at
                )
            """, session)

    return jsonify(session), 201


@session_api.get("/api/sessions")
def danh_sach_phien():
    with closing(ket_noi()) as conn:
        rows = conn.execute("""
            SELECT
                s.id,
                s.name,
                s.status,
                s.created_at,
                s.closed_at,

                (
                    SELECT COUNT(*)
                    FROM processing_requests AS p
                    WHERE p.session_id = s.id
                      AND p.completed_at IS NULL
                ) AS pending,

                COALESCE(SUM(
                    CASE
                        WHEN h.success = 1 AND h.gate = 1
                        THEN 1
                        ELSE 0
                    END
                ), 0) AS gate_1,

                COALESCE(SUM(
                    CASE
                        WHEN h.success = 1 AND h.gate = 2
                        THEN 1
                        ELSE 0
                    END
                ), 0) AS gate_2,

                COALESCE(SUM(
                    CASE
                        WHEN h.success = 1 AND h.gate = 3
                        THEN 1
                        ELSE 0
                    END
                ), 0) AS gate_3,

                COUNT(h.id) AS total,
                COALESCE(SUM(h.success), 0) AS successes,

                COUNT(h.id) - COALESCE(SUM(h.success), 0)
                    AS unsuccessful

            FROM sessions AS s
            LEFT JOIN history AS h ON h.session_id = s.id
            GROUP BY s.id
            ORDER BY s.created_at DESC, s.id DESC
            LIMIT 50
        """).fetchall()

    return jsonify(
        sessions=[dict(row) for row in rows],
        limit=50,
    )


@session_api.post("/api/sessions/<session_id>/close")
def dong_phien(session_id):
    try:
        session_id = str(UUID(session_id))

    except ValueError:
        return jsonify(
            status="invalid_input",
            message="Mã phiên phải là UUID hợp lệ.",
        ), 400

    with closing(ket_noi()) as conn:
        with conn:
            conn.execute("BEGIN IMMEDIATE")

            session = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()

            if session is None:
                return jsonify(
                    status="session_not_found",
                    message="Phiên chạy không tồn tại.",
                ), 404

            if session["status"] == "active":
                pending = conn.execute("""
                    SELECT request_id
                    FROM processing_requests
                    WHERE session_id = ?
                      AND completed_at IS NULL
                """, (session_id,)).fetchone()

                if pending is not None:
                    return jsonify(
                        status="session_busy",
                        message=(
                            "Phiên còn lượt chưa hoàn tất. "
                            "Khôi phục và xử lý xong trước khi đóng."
                        ),
                    ), 409

                closed_at = datetime.now(timezone.utc).isoformat()

                conn.execute("""
                    UPDATE sessions
                    SET status = 'closed', closed_at = ?
                    WHERE id = ?
                """, (closed_at, session_id))

            result = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()

    return jsonify(dict(result)), 200