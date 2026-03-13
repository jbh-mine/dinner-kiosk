"""Order & Cart API routes"""
from flask import Blueprint, jsonify, request, session
import json, threading
from datetime import datetime
from backend.db_init import get_conn
from backend.helpers import is_admin, is_user, current_user, db_deadline
from backend.mapper import sql

bp = Blueprint("api_orders", __name__)
lock = threading.Lock()

@bp.route("/api/member", methods=["POST"])
def api_add_member():
    """\uc0c8 \uc8fc\ubb38\uc790 \uc774\ub984 \uc800\uc7a5 API"""
    b = request.json
    name = (b.get("name") or "").strip()
    if not name or len(name) < 1:
        return jsonify({"ok":False,"msg":"\uc774\ub984\uc774 \ub108\ubb34 \uc9e7\uc2b5\ub2c8\ub2e4"})
    conn = get_conn()
    try:
        existing = sql.query_one(conn, "orders.selectMemberByName", (name,))
        if existing:
            return jsonify({"ok":True,"existing":True})
        row = sql.query_one(conn, "orders.nextMemberSortOrder")
        so = row["cnt"]
        sql.execute(conn, "orders.insertMember", (name, so))
        conn.commit()
        return jsonify({"ok":True,"new":True})
    finally:
        conn.close()

@bp.route("/api/order", methods=["POST"])
def api_place_order():
    with lock:
        dl = db_deadline()
        if dl["active"]:
            if dl["deadline_dt"]:
                try:
                    if datetime.now() >= datetime.fromisoformat(dl["deadline_dt"]): return jsonify({"ok":False,"msg":"\uc8fc\ubb38\uc774 \ub9c8\uac10\ub418\uc5c8\uc2a4\ub2b5\ub2c8\ub2e4."})
                except: pass
            else: return jsonify({"ok":False,"msg":"\uc8fc\ubb38\uc774 \ub9c8\uac10\ub418\uc5c8\uc2a4\ub2b5\ub2c8\ub2e4."})
        b = request.json
        conn = get_conn()
        try:
            oid = sql.insert(conn, "orders.insertOrder",
                (b["restaurant_id"],b["restaurant_name"],b["orderer_name"],b.get("menu_id"),b["menu_name"],
                 b.get("addons_json","[]"),b.get("sides_json","[]"),b["price"],b.get("note",""),b.get("over_limit",0)))
            conn.commit()
            row = sql.query_one(conn, "orders.selectOrderById", (oid,))
        finally:
            conn.close()
    d=dict(row)
    try: d["addons_json"]=json.loads(d.get("addons_json") or "[]")
    except: d["addons_json"]=[]
    try: d["sides_json"]=json.loads(d.get("sides_json") or "[]")
    except: d["sides_json"]=[]
    return jsonify({"ok":True,"order":d})

@bp.route("/api/order/<int:oid>", methods=["DELETE"])
def api_delete_order(oid):
    conn = get_conn()
    try:
        sql.execute(conn, "orders.deleteOrder", (oid,))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

def _cart_row_to_dict(row):
    d = dict(row)
    for f in ("addons_json", "sides_json"):
        try: d[f] = json.loads(d.get(f) or "[]")
        except: d[f] = []
    return d

@bp.route("/api/cart", methods=["GET"])
def api_cart_get():
    """\uc138\uc158\uc758 pending \uc7a5\ubc14\uad6c\ub2c8 \uc544\uc774\ud15c \uc870\ud68c"""
    sk = request.args.get("session_key", "")
    if not sk:
        return jsonify({"ok": False, "msg": "session_key required"})
    conn = get_conn()
    try:
        rows = sql.query(conn, "orders.selectCartItems", (sk,))
        return jsonify({"ok": True, "items": [_cart_row_to_dict(r) for r in rows]})
    finally:
        conn.close()

@bp.route("/api/cart", methods=["POST"])
def api_cart_add():
    """\uc7a5\ubc14\uad6c\ub2c8\uc5d0 \uc544\uc774\ud15c \ucd94\uac00 or \uc218\ub7c8 \ubcc0\uacbd"""
    b = request.json
    sk = b.get("session_key", "")
    if not sk:
        return jsonify({"ok": False, "msg": "session_key required"})
    conn = get_conn()
    try:
        existing = sql.query_one(conn, "orders.selectCartItemForUpsert",
            (sk, b.get("menu_id"), b.get("restaurant_id"),
             b.get("addons_json","[]"), b.get("sides_json","[]"), b.get("note","")))
        if existing:
            new_qty = existing["qty"] + b.get("qty", 1)
            sql.execute(conn, "orders.updateCartItemQty", (new_qty, existing["id"]))
            item_id = existing["id"]
        else:
            item_id = sql.insert(conn, "orders.insertCartItem",
                (sk, b.get("orderer_name",""), b["restaurant_id"], b.get("restaurant_name",""),
                 b.get("menu_id"), b["menu_name"], b.get("menu_emoji","\ud83c\udf7d"),
                 b.get("price",0), b.get("qty",1),
                 b.get("addons_json","[]"), b.get("sides_json","[]"), b.get("note","")))
        conn.commit()
        row = sql.query_one(conn, "orders.selectCartItemById", (item_id,))
        return jsonify({"ok": True, "item": _cart_row_to_dict(row)})
    finally:
        conn.close()

@bp.route("/api/cart/<int:cid>", methods=["DELETE"])
def api_cart_delete(cid):
    """\uc7a5\ubc14\uad6c\ub2c8 \uc544\uc774\ud15c \uc0ad\uc81c"""
    conn = get_conn()
    try:
        sql.execute(conn, "orders.removeCartItem", (cid,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()

@bp.route("/api/cart/clear", methods=["POST"])
def api_cart_clear():
    """\uc138\uc158 \uc7a5\ubc14\uad6c\ub2c8 \uc804\uccb4 \ube44\uc6b0\uae30"""
    sk = request.json.get("session_key","")
    conn = get_conn()
    try:
        sql.execute(conn, "orders.clearCartSession", (sk,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()

@bp.route("/api/cart/checkout", methods=["POST"])
def api_cart_checkout():
    """\uc7a5\ubc14\uad6c\ub2c8 \uc120\ud0dd \ud56d\ubaa9 \u2192 \uc8fc\ubb38 \ud655\uc815 (orders \ud14c\uc774\ube14\uc5d0 insert)"""
    with lock:
        dl = db_deadline()
        if dl["active"]:
            if dl["deadline_dt"]:
                try:
                    if datetime.now() >= datetime.fromisoformat(dl["deadline_dt"]):
                        return jsonify({"ok": False, "msg": "\uc8fc\ubb38\uc774 \ub9c8\uac10\ub418\uc5c8\uc2a4\ub2b5\ub2c8\ub2e4."})
                except: pass
            else:
                return jsonify({"ok": False, "msg": "\uc8fc\ubb38\uc774 \ub9c8\uac10\ub418\uc5c8\uc2a4\ub2b5\ub2c8\ub2e4."})

        b = request.json
        sk   = b.get("session_key", "")
        ids  = b.get("item_ids", [])
        if not sk:
            return jsonify({"ok": False, "msg": "session_key required"})

        conn = get_conn()
        try:
            if ids:
                placeholders = ",".join(["%s"] * len(ids))
                items = sql.query_raw(conn,
                    f"SELECT * FROM cart_items WHERE id IN ({placeholders}) AND session_key=%s AND status='pending'",
                    ids + [sk])
            else:
                items = sql.query(conn, "orders.selectAllCartForCheckout", (sk,))

            if not items:
                return jsonify({"ok": False, "msg": "\ub2f4\uae34 \uba54\ub274\uac00 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4."})

            placed = []
            for item in items:
                it = dict(item)
                orderer = it.get("orderer_name") or b.get("orderer_name","")
                for _ in range(max(1, it["qty"])):
                    oid = sql.insert(conn, "orders.insertOrderFromCart",
                        (it["restaurant_id"], it["restaurant_name"], orderer,
                         it.get("menu_id"), it["menu_name"],
                         it.get("addons_json","[]"), it.get("sides_json","[]"),
                         it["price"], it.get("note","")))
                    placed.append(oid)
                sql.execute(conn, "orders.updateCartToOrdered", (it["id"],))

            conn.commit()
            return jsonify({"ok": True, "order_ids": placed, "count": len(placed)})
        finally:
            conn.close()

@bp.route("/api/reset", methods=["POST"])
def api_reset_orders():
    if not is_admin(): return jsonify({"ok":False,"msg":"\uad8c\ud55c \uc5c6\uc74c"}), 403
    conn = get_conn()
    try:
        sql.execute(conn, "orders.resetTodayOrders")
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/deadline", methods=["POST"])
def api_deadline():
    with lock:
        b=request.json; action=b.get("action")
        conn = get_conn()
        try:
            if action=="set":
                sql.execute(conn, "orders.updateDeadlineSet",
                    (b.get("time"),b.get("schedule_type","once"),b.get("schedule_val",""),b.get("set_by","\uad00\ub9ac\uc790")))
            elif action=="release":
                sql.execute(conn, "orders.updateDeadlineRelease")
            conn.commit()
            row = sql.query_one(conn, "orders.selectDeadlineAfterUpdate")
            return jsonify({"ok":True,"deadline":dict(row)})
        finally:
            conn.close()

@bp.route("/api/deadline/unlock-request", methods=["POST"])
def deadline_unlock_request():
    cu = current_user()
    if not cu:
        return jsonify({"error": "\ub85c\uadf8\uc778\uc774 \uc811\uc5ec\ub418\uc5b4 \uc788\uc2a4\ub2b5\ub2c8\ub2e4"}), 401
    conn = get_conn()
    try:
        existing = sql.query_one(conn, "orders.selectUnlockRequest", (cu["id"],))
        if existing:
            return jsonify({"ok": False, "error": "\uc624\ub298 \uc774\ubbf8 \ud574\uc81c\uc694\uccad\uc744 \ud558\uc168\uc2a4\ub2b5\ub2c8\ub2e4"}), 409
        sql.execute(conn, "orders.insertUnlockRequest", (cu["id"], cu["name"]))
        conn.commit()
        return jsonify({"ok": True, "message": "\ud574\uc81c\uc694\uccad\uc774 \uc804\ub2ec\ub418\uc5c8\uc2a4\ub2b5\ub2c8\ub2e4"})
    finally:
        conn.close()

@bp.route("/api/admin/deadline/unlock-requests")
def admin_unlock_requests():
    if not is_admin():
        return jsonify({"error": "\uad8c\ud55c \uc5c6\uc74c"}), 403
    conn = get_conn()
    try:
        rows = sql.query(conn, "orders.selectUnlockRequests")
        unread_row = sql.query_one(conn, "orders.countUnreadRequests")
        unread = unread_row["cnt"]
        return jsonify({"requests": [dict(r) for r in rows], "unread": unread})
    finally:
        conn.close()

@bp.route("/api/admin/deadline/unlock-requests/mark-read", methods=["POST"])
def admin_unlock_requests_mark_read():
    if not is_admin():
        return jsonify({"error": "\uad8c\ud55c \uc5c6\uc74c"}), 403
    conn = get_conn()
    try:
        sql.execute(conn, "orders.markRequestsRead")
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()
