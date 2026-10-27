import re
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from session_routes import session_api
from history_routes import history_api


BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "instance" / "smartlogistics.db"

app = Flask(__name__)
app.json.ensure_ascii = False

app.register_blueprint(session_api)
app.register_blueprint(history_api)


def ket_noi_db():
    conn = sqlite3.connect(
        DB_PATH.resolve().as_uri() + "?mode=ro",
        uri=True,
    )
    conn.row_factory = sqlite3.Row
    return conn


@app.errorhandler(sqlite3.Error)
def loi_database(error):
    app.logger.error("Lỗi SQLite: %s", error)

    return jsonify(
        status="database_error",
        message=(
            "Không truy cập được database. "
            "Kiểm tra bước khởi tạo database."
        ),
    ), 503


@app.get("/")
def trang_chu():
    return render_template("index.html")


@app.get("/api/health")
def kiem_tra_he_thong():
    conn = ket_noi_db()

    try:
        parcels = conn.execute(
            "SELECT COUNT(*) FROM parcels"
        ).fetchone()[0]

        rules = conn.execute(
            "SELECT COUNT(*) FROM routing_rules"
        ).fetchone()[0]

        sessions = conn.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]

        history = conn.execute(
            "SELECT COUNT(*) FROM history"
        ).fetchone()[0]

        return jsonify(
            status="ok",
            database="connected",
            parcels=parcels,
            routing_rules=rules,
            sessions=sessions,
            history=history,
        )

    finally:
        conn.close()


@app.get("/api/parcels")
def danh_sach_kien():
    subset = request.args.get("subset")

    if subset is not None and subset not in ("demo", "final_test"):
        return jsonify(
            status="invalid_input",
            message="subset chỉ nhận demo hoặc final_test.",
        ), 400

    conn = ket_noi_db()

    try:
        sql = "SELECT code, destination, state, subset FROM parcels"
        params = []

        if subset is not None:
            sql += " WHERE subset = ?"
            params.append(subset)

        sql += " ORDER BY code ASC"

        rows = conn.execute(sql, params).fetchall()

    finally:
        conn.close()

    return jsonify(
        parcels=[dict(row) for row in rows],
        total=len(rows),
        subset=subset,
    )


@app.get("/api/parcels/<code>")
def tra_cuu_kien(code):
    if re.fullmatch(r"KH[0-9]{3}", code) is None:
        return jsonify(
            status="invalid_code",
            code=code,
            message="Mã kiện phải có dạng KH001.",
        ), 400

    conn = ket_noi_db()

    try:
        parcel = conn.execute(
            "SELECT * FROM parcels WHERE code = ?",
            (code,),
        ).fetchone()

        if parcel is None:
            return jsonify(
                status="not_found",
                code=code,
                message="Mã kiện không tồn tại.",
            ), 404

        if any(
            not (parcel[field] or "").strip()
            for field in [
                "destination",
                "destination_key",
                "state",
            ]
        ):
            return jsonify(
                status="missing_destination",
                code=code,
                message="Kiện thiếu thông tin điểm đến.",
            ), 422

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

        if rule is None:
            return jsonify(
                status="unconfigured_destination",
                code=code,
                destination=parcel["destination"],
                message="Điểm đến chưa được cấu hình cửa.",
            ), 422

        return jsonify(
            status="ready",
            code=parcel["code"],
            destination=parcel["destination"],
            state=parcel["state"],
            gate=rule["gate"],
            subset=parcel["subset"],
            message=(
                f"Đã xác định cửa {rule['gate']}; "
                "chưa xử lý kiện."
            ),
        )

    finally:
        conn.close()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )