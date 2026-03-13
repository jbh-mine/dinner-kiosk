"""
board API - backend/routes/api_board.py
POST/GET/PUT/DELETE  /api/board/...
POST/GET/PUT/DELETE  /api/admin/board/...
"""
import os, uuid
from flask import Blueprint, request, jsonify, session, send_from_directory
from backend.db_init import get_conn
from backend.helpers import is_admin, current_user
from backend.mapper import sql

bp = Blueprint("api_board", __name__)

UPLOAD_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "board")
os.makedirs(UPLOAD_BASE, exist_ok=True)

ALLOWED_EXT = {".jpg",".jpeg",".png",".gif",".pdf",".zip",".txt",".docx",".xlsx",".hwp",".mp4",".mov"}

def _ext_ok(filename):
    return os.path.splitext(filename.lower())[1] in ALLOWED_EXT

@bp.route("/api/board/categories")
def board_categories():
    conn = get_conn()
    try:
        rows = sql.query(conn, "board.selectCategories")
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@bp.route("/api/board/<slug>/posts")
def board_posts(slug):
    conn = get_conn()
    try:
        cat = sql.query_one(conn, "board.selectCategoryBySlug", (slug,))
        if not cat:
            return jsonify({"error": "\uce74\ud14c\uace0\ub9ac\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 404

        page  = max(1, int(request.args.get("page", 1)))
        limit = min(50, int(request.args.get("limit", 20)))
        offset = (page - 1) * limit

        rows = sql.query(conn, "board.selectPostsWithCounts", (cat["id"], limit, offset))
        total_row = sql.query_one(conn, "board.countPostsByCategory", (cat["id"],))
        total = total_row["cnt"]
        return jsonify({
            "category": dict(cat),
            "posts": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit,
        })
    finally:
        conn.close()

@bp.route("/api/board/posts/<int:pid>")
def board_post_detail(pid):
    conn = get_conn()
    try:
        post = sql.query_one(conn, "board.selectPostById", (pid,))
        if not post:
            return jsonify({"error": "\uac8c\uc2dc\uae00\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 404

        sql.execute(conn, "board.incrementViewCount", (pid,))
        conn.commit()

        attachments = sql.query(conn, "board.selectPostAttachments", (pid,))
        result = dict(post)
        result["attachments"] = [dict(a) for a in attachments]
        return jsonify(result)
    finally:
        conn.close()

@bp.route("/api/board/<slug>/posts", methods=["POST"])
def board_create_post(slug):
    cu      = current_user()
    is_adm  = is_admin()
    if not cu and not is_adm:
        return jsonify({"error": "\ub85c\uadf8\uc778\uc774 \uc811\uc5ec\ub418\uc5b4 \uc788\uc2a4\ub2b5\ub2c8\ub2e4"}), 401

    conn = get_conn()
    try:
        cat = sql.query_one(conn, "board.selectCategoryBySlug", (slug,))
        if not cat:
            return jsonify({"error": "\uce74\ud14c\uace0\ub9ac\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 404
        if not cat["allow_write"] and not is_adm:
            return jsonify({"error": "\uc774 \uce74\ud14c\uace0\ub9ac\uc5d0\ub294 \uae00\uc744 \uc4f8 \uc218 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 403

        title   = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not title:
            return jsonify({"error": "\uc81c\ubaa9\uc744 \uc785\ub825\ud574\uc8fc\uc138\uc694"}), 400

        author_id   = cu["id"] if cu else None
        author_name = cu["name"] if cu else "\uad00\ub9ac\uc790"
        flag_admin  = 1 if is_adm else 0
        is_pinned   = 1 if (is_adm and request.form.get("is_pinned") == "1") else 0

        post_id = sql.insert(conn, "board.insertPost",
                             (cat["id"], author_id, author_name, flag_admin, title, content, is_pinned))

        files = request.files.getlist("attachments")
        for f in files:
            if not f or not f.filename:
                continue
            if not _ext_ok(f.filename):
                continue
            ext   = os.path.splitext(f.filename)[1].lower()
            saved = uuid.uuid4().hex + ext
            path  = os.path.join(UPLOAD_BASE, saved)
            f.save(path)
            size  = os.path.getsize(path)
            sql.execute(conn, "board.insertAttachment",
                        (post_id, f.filename, saved, size, f.content_type or ""))

        conn.commit()
        return jsonify({"id": post_id, "message": "\ub4f1\ub85d\ub418\uc5c8\uc2a4\ub2b5\ub2c8\ub2e4"}), 201
    finally:
        conn.close()

@bp.route("/api/board/posts/<int:pid>", methods=["PUT"])
def board_update_post(pid):
    cu     = current_user()
    is_adm = is_admin()
    if not cu and not is_adm:
        return jsonify({"error": "\ub85c\uadf8\uc778\uc774 \uc811\uc5ec\ub418\uc5b4 \uc788\uc2a4\ub2b5\ub2c8\ub2e4"}), 401

    conn = get_conn()
    try:
        post = sql.query_one(conn, "board.selectPostForUpdate", (pid,))
        if not post:
            return jsonify({"error": "\uac8c\uc2dc\uae00\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 404
        if not is_adm and (not cu or post["author_id"] != cu["id"]):
            return jsonify({"error": "\uc218\uc815 \uad8c\ud55c\uc774 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 403

        title   = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if not title:
            return jsonify({"error": "\uc81c\ubaa9\uc744 \uc785\ub825\ud574\uc8fc\uc138\uc694"}), 400

        is_pinned = 1 if (is_adm and request.form.get("is_pinned") == "1") else post["is_pinned"]
        sql.execute(conn, "board.updatePost", (title, content, is_pinned, pid))

        files = request.files.getlist("attachments")
        for f in files:
            if not f or not f.filename:
                continue
            if not _ext_ok(f.filename):
                continue
            ext   = os.path.splitext(f.filename)[1].lower()
            saved = uuid.uuid4().hex + ext
            path  = os.path.join(UPLOAD_BASE, saved)
            f.save(path)
            size  = os.path.getsize(path)
            sql.execute(conn, "board.insertAttachment",
                        (pid, f.filename, saved, size, f.content_type or ""))

        del_ids = request.form.getlist("delete_attachments")
        for aid in del_ids:
            row = sql.query_one(conn, "board.selectAttachmentForDelete", (aid, pid))
            if row:
                try: os.remove(os.path.join(UPLOAD_BASE, row["saved_name"]))
                except: pass
                sql.execute(conn, "board.deleteAttachment", (aid,))

        conn.commit()
        return jsonify({"message": "\uc218\uc815\ub418\uc5c8\uc2a4\ub2b5\ub2c8\ub2e4"})
    finally:
        conn.close()

@bp.route("/api/board/posts/<int:pid>", methods=["DELETE"])
def board_delete_post(pid):
    cu     = current_user()
    is_adm = is_admin()
    if not cu and not is_adm:
        return jsonify({"error": "\ub85c\uadf8\uc778\uc774 \uc811\uc5ec\ub418\uc5b4 \uc788\uc2a4\ub2b5\ub2c8\ub2e4"}), 401

    conn = get_conn()
    try:
        post = sql.query_one(conn, "board.selectPostById", (pid,))
        if not post:
            return jsonify({"error": "\uac8c\uc2dc\uae00\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 404
        if not is_adm and (not cu or post["author_id"] != cu["id"]):
            return jsonify({"error": "\uc0ad\uc81c \uad8c\ud55c\uc774 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 403

        sql.execute(conn, "board.softDeletePost", (pid,))
        conn.commit()
        return jsonify({"message": "\uc0ad\uc81c\ub418\uc5c8\uc2a4\ub2b5\ub2c8\ub2e4"})
    finally:
        conn.close()

@bp.route("/api/board/posts/<int:pid>/attachments/<int:aid>/download")
def board_download(pid, aid):
    conn = get_conn()
    try:
        row = sql.query_one(conn, "board.selectAttachmentForDownload", (aid, pid))
        if not row:
            return jsonify({"error": "\ud30c\uc77c\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 404
        return send_from_directory(UPLOAD_BASE, row["saved_name"], as_attachment=True, download_name=row["filename"])
    finally:
        conn.close()

@bp.route("/api/admin/board/categories")
def admin_board_categories():
    if not is_admin():
        return jsonify({"error": "\uad8c\ud55c \uc5c6\uc74c"}), 403
    conn = get_conn()
    try:
        rows = sql.query(conn, "board.selectAllCategories")
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@bp.route("/api/board/posts/<int:pid>/comments")
def board_comments_list(pid):
    conn = get_conn()
    try:
        rows = sql.query(conn, "board.selectComments", (pid,))
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@bp.route("/api/board/posts/<int:pid>/comments", methods=["POST"])
def board_comment_create(pid):
    cu     = current_user()
    is_adm = is_admin()
    if not cu and not is_adm:
        return jsonify({"error": "\ub85c\uadf8\uc778\uc774 \uc811\uc5ec\ub418\uc5b4 \uc788\uc2a4\ub2b5\ub2c8\ub2e4"}), 401

    conn = get_conn()
    try:
        post = sql.query_one(conn, "board.selectPostExists", (pid,))
        if not post:
            return jsonify({"error": "\uac8c\uc2dc\uae00\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2a4\ub2b5\ub2c8\ub2e4"}), 404

        if request.is_json:
            data    = request.get_json() or {}
            content = (data.get("content") or "").strip()
        else:
            content = (request.form.get("content") or "").strip()

        if not content:
            return jsonify({"error": "\ub0b4\uc6a9\uc744 \uc785\ub825\ud574\uc8fc\uc138\uc694"}), 400

        author_id   = cu["id"]   if cu     else None
        author_name = cu["name"] if cu     else "\uad00\ub9ac\uc790"
        flag_admin  = 1          if is_adm else 0

        new_id = sql.insert(conn, "board.insertComment",
                            (pid, author_id, author_name, flag_admin, content))
        conn.commit()
        row = sql.query_one(conn, "board.selectCommentById", (new_id,))
        return jsonify(dict(row)), 201
    finally:
        conn.close()
