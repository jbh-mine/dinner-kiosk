"""Page routes: main kiosk, admin dashboard"""
from flask import Blueprint, redirect, request, session, jsonify
from datetime import datetime
import json
from backend.helpers import is_admin, current_user
from backend.db_init import get_conn, _hash_pw
from backend.mapper import sql
from frontend.renderer import render_index, render_admin, render_result, render_admin_login

bp = Blueprint("pages", __name__)

@bp.route("/")
def index(): return render_index()

@bp.route("/api/login", methods=["POST"])
def api_login():
    b = request.json
    conn = get_conn()
    try:
        row = sql.query_one(conn, "pages.selectAdminByCredentials",
                            (b.get("username"), _hash_pw(b.get("password",""))))
        if row and row["username"] == "admin": session["is_admin"] = True; return jsonify({"ok":True})
        if row: return jsonify({"ok":False,"msg":"\uad00\ub9ac\uc790 \uad8c\ud55c\uc774 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4."})
        return jsonify({"ok":False,"msg":"\uc544\uc774\ub514 \ub610\ub294 \ube44\ubc00\ubc88\ud638\uac00 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."})
    finally:
        conn.close()

@bp.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("is_admin",None)
    return jsonify({"ok":True,"redirect":"/adminLogin"})

@bp.route("/admin")
def admin_dashboard():
    if not is_admin():
        return redirect("/adminLogin?next=/admin")
    return render_admin()

@bp.route("/api/admin/dashboard")
def api_admin_dashboard():
    if not is_admin():
        return jsonify({"error":"\uad8c\ud55c \uc5c6\uc74c"}), 403
    conn = get_conn()
    try:
        this_month = datetime.now().strftime("%Y-%m")
        this_year = datetime.now().strftime("%Y")
        today_orders = sql.query(conn, "pages.selectTodayOrders")
        today_total = sum(o["price"] for o in today_orders)
        today_count = len(today_orders)
        return jsonify({
            "today": {"count": today_count, "total": today_total},
        })
    finally:
        conn.close()

@bp.route("/result")
def result_page():
    return render_result()

@bp.route("/adminLogin")
def admin_login_page():
    """\uad00\ub9ac\uc790 \uc804\uc6a9 \ub3c5\ub9bd \ub85c\uadf8\uc778 \ud398\uc774\uc9c0"""
    if is_admin():
        return redirect(request.args.get("next", "/admin"))
    next_url = request.args.get("next", "/admin")
    return render_admin_login(next_url)
