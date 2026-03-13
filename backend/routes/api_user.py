"""User auth & likes API routes"""
from flask import Blueprint, jsonify, request, session
from backend.db_init import get_conn, _hash_pw
from backend.helpers import is_admin
from backend.mapper import sql

bp = Blueprint("api_user", __name__)

@bp.route("/api/user/login", methods=["POST"])
def api_user_login():
    b = request.json
    conn = get_conn()
    try:
        row = sql.query_one(conn, "user.selectMemberByUsername",
                            ((b.get("username") or "").strip(),))
        if not row:
            return jsonify({"ok":False,"msg":"\uc544\uc774\ub514\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4."})
        stored_pw = (row["password"] or "") if "password" in row.keys() else ""
        if not stored_pw:
            default_pw = _hash_pw("1234")
            if _hash_pw(b.get("password","")) != default_pw:
                return jsonify({"ok":False,"msg":"\ube44\ubc00\ubc88\ud638\uac00 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."})
        else:
            if _hash_pw(b.get("password","")) != stored_pw:
                return jsonify({"ok":False,"msg":"\ube44\ubc00\ubc88\ud638\uac00 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."})
        session["user_id"] = row["id"]
        keys = row.keys()
        first     = row["first_login"] if "first_login" in keys else 0
        theme     = row["theme"]     if "theme"     in keys else "bk"
        font_size = row["font_size"] if "font_size" in keys else 16
        return jsonify({"ok":True,"user":{
            "id":          row["id"],
            "name":        row["name"],
            "username":    row["username"] if "username" in keys else "",
            "first_login": first,
            "theme":       theme or "bk",
            "font_size":   font_size or 16,
        }})
    finally:
        conn.close()

@bp.route("/api/user/logout", methods=["POST"])
def api_user_logout():
    session.pop("user_id", None); return jsonify({"ok":True})

@bp.route("/api/like/toggle", methods=["POST"])
def api_like_toggle():
    uid = session.get("user_id")
    if not uid: return jsonify({"ok":False,"msg":"\ub85c\uadf8\uc778\uc774 \uc811\uc5ec\ub418\uc5b4 \uc788\uc2a4\ub2b5\ub2c8\ub2e4"})
    b = request.json; mid = b.get("menu_id")
    if not mid: return jsonify({"ok":False,"msg":"menu_id \uc544\ue4f8\ub978"})
    conn = get_conn()
    try:
        existing = sql.query_one(conn, "user.selectMenuLikeExists", (mid, uid))
        if existing:
            sql.execute(conn, "user.deleteMenuLike", (mid, uid)); liked=False
        else:
            sql.execute(conn, "user.insertMenuLike", (mid, uid)); liked=True
        conn.commit()
        count_row = sql.query_one(conn, "user.selectMenuLikeCount", (mid,))
        count = count_row["cnt"]
        try:
            sql.execute(conn, "user.updateMenuLikeCount", (count, mid))
            conn.commit()
        except Exception:
            pass
        return jsonify({"ok":True,"liked":liked,"count":count})
    finally:
        conn.close()
