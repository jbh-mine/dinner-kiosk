"""Public API routes: stats, popular, menus"""
from flask import Blueprint, jsonify, request
from backend.helpers import db_menus_full, db_menus_admin, db_addons_full, db_sides_full, is_admin
from backend.db_init import get_conn
from backend.mapper import sql as mapper

bp = Blueprint("api_public", __name__)

@bp.route("/api/stats/orders")
def api_stats_orders():
    if not is_admin():
        return jsonify({"error":"\uad8c\ud55c \uc5c6\uc74c"}), 403
    start = request.args.get("start", "")
    end   = request.args.get("end", "")
    conn  = get_conn()
    try:
        where = []
        params = []
        if start:
            where.append("order_date >= %s")
            params.append(start)
        if end:
            where.append("order_date <= %s")
            params.append(end)
        q = "SELECT * FROM orders"
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY order_date DESC, ordered_at DESC"
        rows = mapper.query_raw(conn, q, params)
        result = []
        for r in rows:
            d = dict(r)
            try: d["addons_json"] = json.dumps(json.loads(d.get("addons_json") or "[]"), ensure_ascii=False)
            except: d["addons_json"] = "[]"
            try: d["sides_json"] = json.dumps(json.loads(d.get("sides_json") or "[]"), ensure_ascii=False)
            except: d["sides_json"] = "[]"
            result.append(d)
        return jsonify({"orders": result})
    finally:
        conn.close()

@bp.route("/api/popular")
def api_popular():
    conn = get_conn()
    try:
        rests = mapper.query(conn, "public.selectRestaurantsForPopular")
        popular_by_rest = []
        for r in rests:
            rid = r["id"]
            pop_rows = mapper.query(conn, "public.selectPopularMenus", (rid,))
            if pop_rows:
                popular_by_rest.append({
                    "rid": rid, "rest_name": r["name"],
                    "rest_emoji": r["emoji"] or "\ud83c\udfd0",
                    "rest_color": r["color"] or "#f5a623",
                    "menus": [dict(x) for x in pop_rows]
                })
        return jsonify({"popular_by_rest": popular_by_rest})
    finally:
        conn.close()

@bp.route("/api/menus/<int:rid>")
def api_menus(rid): return jsonify({"categories": db_menus_full(rid)})

@bp.route("/api/admin/menus/<int:rid>")
def api_admin_menus(rid):
    if not is_admin(): return jsonify({"ok":False,"msg":"\uad8c\ud55c \uc5c6\uc74c"}), 403
    return jsonify({"categories": db_menus_admin(rid)})

@bp.route("/api/addons/<int:rid>")
def api_addons(rid): return jsonify({"categories": db_addons_full(rid)})

@bp.route("/api/sides/<int:rid>")
def api_sides(rid): return jsonify({"categories": db_sides_full(rid)})
