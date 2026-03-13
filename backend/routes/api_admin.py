"""Admin CRUD API routes: restaurants, menus, addons, sides, members, orgs"""
from flask import Blueprint, jsonify, request, session
import json
from backend.db_init import get_conn, _hash_pw
from backend.helpers import is_admin, db_restaurants
from backend.mapper import sql

bp = Blueprint("api_admin", __name__)

def _build_org_tree(rows, parent_id=None):
    """rows: list of dicts with id/name/parent_id/sort_order"""
    children = [r for r in rows if r["parent_id"] == parent_id]
    children.sort(key=lambda x: x["sort_order"])
    result = []
    for c in children:
        node = dict(c)
        node["children"] = _build_org_tree(rows, c["id"])
        result.append(node)
    return result

@bp.route("/api/admin/orgs")
def api_admin_orgs():
    if not is_admin(): return jsonify({"ok":False}), 403
    conn = get_conn()
    try:
        rows = sql.query(conn, "admin.selectOrgs")
        members = sql.query(conn, "admin.selectOrgMembers")
        tree = _build_org_tree(rows, None)
        return jsonify({"tree": tree, "members": members})
    finally:
        conn.close()

@bp.route("/api/admin/org", methods=["POST"])
def api_add_org():
    if not is_admin(): return jsonify({"ok":False}), 403
    b = request.json
    name = (b.get("name") or "").strip()
    if not name: return jsonify({"ok":False,"msg":"\uc774\ub984\uc744 \uc785\ub825\ud558\uc138\uc694"})
    parent_id = b.get("parent_id") or None
    conn = get_conn()
    try:
        row = sql.query_one(conn, "admin.nextOrgSortOrder", (parent_id,))
        so = row["next_so"]
        new_id = sql.insert(conn, "admin.insertOrg", (name, parent_id, so))
        conn.commit()
        return jsonify({"ok":True, "id": new_id})
    finally:
        conn.close()

@bp.route("/api/admin/org/<int:oid>", methods=["PUT"])
def api_update_org(oid):
    if not is_admin(): return jsonify({"ok":False}), 403
    b = request.json
    conn = get_conn()
    try:
        sql.execute(conn, "admin.updateOrgName", (b.get("name","").strip(), oid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/org/<int:oid>", methods=["DELETE"])
def api_del_org(oid):
    if not is_admin(): return jsonify({"ok":False}), 403
    conn = get_conn()
    try:
        sql.execute(conn, "admin.clearOrgMembers", (oid,))
        sql.execute(conn, "admin.deleteOrg", (oid,))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/org/reorder", methods=["POST"])
def api_reorder_orgs():
    if not is_admin(): return jsonify({"ok":False}), 403
    items = request.json.get("items", [])
    conn = get_conn()
    try:
        for item in items:
            sql.execute(conn, "admin.reorderOrg", (item["sort_order"], item["id"]))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/member/<int:mid>/org", methods=["PUT"])
def api_set_member_org(mid):
    if not is_admin(): return jsonify({"ok":False}), 403
    b = request.json
    org_id = b.get("org_id") or None
    conn = get_conn()
    try:
        sql.execute(conn, "admin.setMemberOrg", (org_id, mid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/members")
def api_admin_members():
    conn = get_conn()
    try:
        rows = sql.query(conn, "admin.selectMembersWithOrg")
        result = []
        for r in rows:
            m = dict(r)
            today_orders = sql.query(conn, "admin.selectMemberTodayOrders", (m["name"],))
            m["today_orders"] = today_orders
            m["today_count"]  = len(today_orders)
            total_row = sql.query_one(conn, "admin.countMemberTotalOrders", (m["name"],))
            m["total_count"]  = total_row["cnt"]
            result.append(m)
        return jsonify({"members": result})
    finally:
        conn.close()

@bp.route("/api/admin/member", methods=["POST"])
def api_admin_add_member():
    b = request.json
    name = (b.get("name") or "").strip()
    if not name: return jsonify({"ok":False,"msg":"\uc774\ub984\uc744 \uc785\ub825\ud558\uc138\uc694"})
    conn = get_conn()
    try:
        existing = sql.query_one(conn, "admin.selectMemberByName", (name,))
        if existing:
            return jsonify({"ok":True,"existing":True})
        row = sql.query_one(conn, "admin.nextMemberSortOrder")
        so = row["next_so"]
        work_location = (b.get("work_location") or "").strip()
        sql.execute(conn, "admin.insertMember", (name, so, work_location))
        conn.commit()
        return jsonify({"ok":True,"new":True})
    finally:
        conn.close()

@bp.route("/api/admin/member/<int:mid>", methods=["PUT"])
def api_admin_update_member(mid):
    if not is_admin(): return jsonify({"ok":False,"msg":"\uad8c\ud55c \uc5c6\uc74c"}), 403
    b = request.json
    conn = get_conn()
    try:
        row = sql.query_one(conn, "admin.selectMemberForUpdate", (mid,))
        if not row:
            return jsonify({"ok":False,"msg":"\uc5c6\ub294 \uc8fc\ubb38\uc790"})
        old_name = row["name"]
        new_name = (b.get("name") or old_name).strip()
        active   = b.get("active", row["active"])
        if list(b.keys()) == ["active"]:
            sql.execute(conn, "admin.updateMemberActive", (active, mid))
            conn.commit()
            return jsonify({"ok":True})
        work_location = b.get("work_location", row["work_location"] if "work_location" in row else "")
        if new_name != old_name:
            dup = sql.query_one(conn, "admin.selectDuplicateMemberName", (new_name, mid))
            if dup:
                return jsonify({"ok":False,"msg":"\uc774\ubbf8 \uc874\uc7ac\ud558\ub294 \uc774\ub984\uc785\ub2c8\ub2e4"})
            sql.execute(conn, "admin.updateOrdererName", (new_name, old_name))
        sql.execute(conn, "admin.updateMember", (new_name, active, work_location, mid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/member/<int:mid>", methods=["DELETE"])
def api_admin_delete_member(mid):
    if not is_admin(): return jsonify({"ok":False,"msg":"\uad8c\ud55c \uc5c6\uc74c"}), 403
    conn = get_conn()
    try:
        sql.execute(conn, "admin.deleteMember", (mid,))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/members/reorder", methods=["POST"])
def api_admin_members_reorder():
    if not is_admin(): return jsonify({"ok":False,"msg":"\uad8c\ud55c \uc5c6\uc74c"}), 403
    ids = request.json.get("ids", [])
    conn = get_conn()
    try:
        for i, mid in enumerate(ids):
            sql.execute(conn, "admin.reorderMember", (i, mid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/restaurants")
def api_admin_rests():
    conn = get_conn()
    try:
        rests = sql.query(conn, "admin.selectActiveRestaurants")
        result = []
        for r in rests:
            d = dict(r)
            try: d["holiday_days"] = json.loads(d.get("holiday_days") or "[]")
            except: d["holiday_days"] = []
            menu_cats = sql.query(conn, "admin.selectMenuCategoriesForRest", (r["id"],))
            d["menu_categories"] = []
            for c in menu_cats:
                cat_dict = {**dict(c)}
                cat_dict["menus"] = sql.query(conn, "admin.selectMenusForCategory", (r["id"], c["id"]))
                d["menu_categories"].append(cat_dict)
            d["addons"] = sql.query(conn, "admin.selectAddonsForRest", (r["id"],))
            d["sides"] = sql.query(conn, "admin.selectSidesForRest", (r["id"],))
            result.append(d)
        return jsonify({"restaurants": result})
    finally:
        conn.close()

@bp.route("/api/admin/restaurant", methods=["POST"])
def api_add_rest():
    b = request.json
    conn = get_conn()
    try:
        new_id = sql.insert(conn, "admin.insertRestaurant",
                            (b["name"], b.get("emoji","\ud83c\udf7d"), b.get("type","\ub9e4\uc7a5\uc2dd\uc0ac"), b.get("color","#F5A623")))
        conn.commit()
        return jsonify({"ok":True, "id": new_id})
    finally:
        conn.close()

@bp.route("/api/admin/restaurant/<int:rid>", methods=["PUT"])
def api_update_rest(rid):
    b = request.json
    hdays = json.dumps(b.get("holiday_days",[]))
    conn = get_conn()
    try:
        sql.execute(conn, "admin.updateRestaurant",
                    (b["name"], b.get("emoji","\ud83c\udf7d"), b.get("type","\ub9e4\uc7a5\uc2dd\uc0ac"),
                     b.get("phone",""), b.get("hours",""), b.get("price_limit",0),
                     b.get("address",""), b.get("note",""), b.get("color","#F5A623"),
                     b.get("order_disabled",0), hdays, rid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/restaurant/<int:rid>", methods=["DELETE"])
def api_del_rest(rid):
    conn = get_conn()
    try:
        sql.execute(conn, "admin.deactivateRestaurant", (rid,))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/restaurant/<int:rid>/holiday_days", methods=["PUT"])
def api_update_hdays(rid):
    b = request.json
    hdays = json.dumps(b.get("holiday_days",[]))
    conn = get_conn()
    try:
        sql.execute(conn, "admin.updateHolidayDays", (hdays, rid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/menu", methods=["POST"])
def api_add_menu():
    b = request.json
    conn = get_conn()
    try:
        row = sql.query_one(conn, "admin.nextMenuSortOrder", (b["restaurant_id"],))
        so = row["next_so"]
        new_id = sql.insert(conn, "admin.insertMenu",
                            (b["restaurant_id"], b.get("category_id"), b["name"],
                             b.get("price",0), b.get("emoji","\ud83c\udf7d"),
                             b.get("description",""), b.get("tag",""), so))
        conn.commit()
        return jsonify({"ok":True, "id": new_id})
    finally:
        conn.close()

@bp.route("/api/admin/menu/<int:mid>", methods=["PUT"])
def api_update_menu(mid):
    b = request.json
    conn = get_conn()
    try:
        if list(b.keys()) == ["available"]:
            sql.execute(conn, "admin.updateMenuAvailable", (b["available"], mid))
        else:
            sql.execute(conn, "admin.updateMenuFull",
                        (b["name"], b.get("price",0), b.get("emoji","\ud83c\udf7d"),
                         b.get("description",""), b.get("tag",""),
                         b.get("available",1), mid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/menu/<int:mid>", methods=["DELETE"])
def api_del_menu(mid):
    conn = get_conn()
    try:
        sql.execute(conn, "admin.deleteMenu", (mid,))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/menu/reorder", methods=["POST"])
def api_menu_reorder():
    ids = request.json.get("ids",[])
    conn = get_conn()
    try:
        for i, mid in enumerate(ids):
            sql.execute(conn, "admin.reorderMenu", (i, mid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/addon", methods=["POST"])
def api_add_addon():
    b = request.json
    conn = get_conn()
    cat_name = b.get("category_name","\ucd94\uac00 \uc635\uc158")
    rid = b["restaurant_id"]
    try:
        cid_row = sql.query_one(conn, "admin.selectAddonCategory", (rid, cat_name))
        if not cid_row:
            so_row = sql.query_one(conn, "admin.nextAddonCategorySortOrder", (rid,))
            so = so_row["next_so"]
            cid = sql.insert(conn, "admin.insertAddonCategory", (rid, cat_name, so))
        else:
            cid = cid_row["id"]
        so_row = sql.query_one(conn, "admin.nextAddonSortOrder", (rid,))
        so = so_row["next_so"]
        sql.execute(conn, "admin.insertAddon", (rid, cid, b["name"], b.get("extra_price",0), so))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/addon/<int:aid>", methods=["PUT"])
def api_update_addon(aid):
    b = request.json
    conn = get_conn()
    try:
        sql.execute(conn, "admin.updateAddon", (b["name"], b.get("extra_price",0), aid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/addon/<int:aid>", methods=["DELETE"])
def api_del_addon(aid):
    conn = get_conn()
    try:
        sql.execute(conn, "admin.deleteAddon", (aid,))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/side", methods=["POST"])
def api_add_side():
    b = request.json
    conn = get_conn()
    cat_name = b.get("category_name","\uc0ac\uc774\ub4dc")
    rid = b["restaurant_id"]
    try:
        cid_row = sql.query_one(conn, "admin.selectSideCategory", (rid, cat_name))
        if not cid_row:
            so_row = sql.query_one(conn, "admin.nextSideCategorySortOrder", (rid,))
            so = so_row["next_so"]
            cid = sql.insert(conn, "admin.insertSideCategory", (rid, cat_name, so))
        else:
            cid = cid_row["id"]
        so_row = sql.query_one(conn, "admin.nextSideSortOrder", (rid,))
        so = so_row["next_so"]
        sql.execute(conn, "admin.insertSide", (rid, cid, b["name"], b.get("extra_price",0), so))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/side/<int:sid>", methods=["PUT"])
def api_update_side(sid):
    b = request.json
    conn = get_conn()
    try:
        sql.execute(conn, "admin.updateSide", (b["name"], b.get("extra_price",0), sid))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()

@bp.route("/api/admin/side/<int:sid>", methods=["DELETE"])
def api_del_side(sid):
    conn = get_conn()
    try:
        sql.execute(conn, "admin.deleteSide", (sid,))
        conn.commit()
        return jsonify({"ok":True})
    finally:
        conn.close()
