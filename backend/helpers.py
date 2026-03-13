"""DB Helper functions for dinner order system (PostgreSQL + SQL Mapper)"""
import json
from flask import session
from backend.db_init import get_conn
from backend.mapper import sql


def db_restaurants():
    conn = get_conn()
    try:
        rows = sql.query(conn, "helpers.selectRestaurants")
        result = []
        for r in rows:
            d = dict(r)
            try:    d["holiday_days"] = json.loads(d.get("holiday_days") or "[]")
            except: d["holiday_days"] = []
            row = sql.query_one(conn, "helpers.countRestaurantTodayOrders", (r["id"],))
            d["today_orders"] = row["cnt"]
            result.append(d)
        return result
    finally:
        conn.close()


def db_menus_full(rid):
    conn = get_conn()
    try:
        cats = sql.query(conn, "helpers.selectMenuCategories", (rid,))
        result = []
        for c in cats:
            menus = [dict(m) for m in sql.query(conn, "helpers.selectMenusByCategory", (rid, c["id"]))]
            result.append({"id": c["id"], "name": c["name"], "emoji": c["emoji"], "menus": menus})
        uncategorized = [dict(m) for m in sql.query(conn, "helpers.selectUncategorizedMenus", (rid,))]
        if uncategorized:
            result.append({"id": None, "name": "기타", "emoji": "🍽", "menus": uncategorized})
        return result
    finally:
        conn.close()


def db_menus_admin(rid):
    conn = get_conn()
    try:
        cats = sql.query(conn, "helpers.selectMenuCategories", (rid,))
        result = []
        for c in cats:
            menus = [dict(m) for m in sql.query(conn, "helpers.selectMenusByCategoryAdmin", (rid, c["id"]))]
            result.append({"id": c["id"], "name": c["name"], "emoji": c["emoji"], "menus": menus})
        return result
    finally:
        conn.close()


def db_addons_full(rid):
    conn = get_conn()
    try:
        cats = sql.query(conn, "helpers.selectAddonCategories", (rid,))
        result = []
        for c in cats:
            items = [dict(a) for a in sql.query(conn, "helpers.selectAddonsByCategory", (rid, c["id"]))]
            result.append({"id": c["id"], "name": c["name"], "items": items})
        uncategorized = [dict(a) for a in sql.query(conn, "helpers.selectUncategorizedAddons", (rid,))]
        if uncategorized:
            result.append({"id": None, "name": "추가 옵션", "items": uncategorized})
        return result
    finally:
        conn.close()


def db_sides_full(rid):
    conn = get_conn()
    try:
        cats = sql.query(conn, "helpers.selectSideCategories", (rid,))
        result = []
        for c in cats:
            items = [dict(s) for s in sql.query(conn, "helpers.selectSidesByCategory", (rid, c["id"]))]
            result.append({"id": c["id"], "name": c["name"], "items": items})
        return result
    finally:
        conn.close()


def db_members():
    conn = get_conn()
    try:
        try:
            rows = sql.query(conn, "helpers.selectActiveMembers")
            return [x["name"] for x in rows]
        except Exception:
            conn.rollback()
            rows = sql.query(conn, "helpers.selectAllMembers")
            return [x["name"] for x in rows]
    finally:
        conn.close()


def db_orders_today():
    conn = get_conn()
    try:
        rows = sql.query(conn, "helpers.selectTodayOrders")
        result = []
        for r in rows:
            d = dict(r)
            try:    d["addons_json"] = json.loads(d.get("addons_json") or "[]")
            except: d["addons_json"] = []
            try:    d["sides_json"]  = json.loads(d.get("sides_json") or "[]")
            except: d["sides_json"]  = []
            result.append(d)
        return result
    finally:
        conn.close()


def db_deadline():
    conn = get_conn()
    try:
        r = sql.query_one(conn, "helpers.selectDeadlineSettings")
        return dict(r)
    finally:
        conn.close()


def is_admin():    return session.get("is_admin", False)
def is_user():     return session.get("user_id") is not None


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_conn()
    try:
        row = sql.query_one(conn, "helpers.selectMemberById", (uid,))
        return dict(row) if row else None
    finally:
        conn.close()
