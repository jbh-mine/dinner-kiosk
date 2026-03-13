"""BGM (\ubc30\uacbd\uc74c\uc545) \uad00\ub9ac API"""
import os, uuid
from flask import Blueprint, jsonify, request, send_from_directory
from backend.db_init import get_conn
from backend.helpers import is_admin
from backend.mapper import sql

bp = Blueprint("api_bgm", __name__)

BGM_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "uploads", "bgm"
))
os.makedirs(BGM_DIR, exist_ok=True)

ALLOWED_EXT = {"mp3", "wav", "ogg", "m4a", "aac", "flac"}

def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

@bp.route("/api/bgm/tracks")
def api_bgm_list():
    conn = get_conn()
    try:
        q = request.args.get("q", "").strip()
        if q:
            rows = sql.query(conn, "bgm.selectActiveTracks", (f"%{q}%",))
        else:
            rows = sql.query(conn, "bgm.selectActiveTracksAll")
        return jsonify({"tracks": [dict(r) for r in rows]})
    finally:
        conn.close()

@bp.route("/api/bgm/stream/<int:tid>")
def api_bgm_stream(tid):
    conn = get_conn()
    try:
        row = sql.query_one(conn, "bgm.selectTrackById", (tid,))
        if not row:
            return jsonify({"error": "not found"}), 404
        return send_from_directory(BGM_DIR, row["saved_name"],
                                   mimetype="audio/mpeg",
                                   as_attachment=False,
                                   download_name=row["filename"])
    finally:
        conn.close()

@bp.route("/api/admin/bgm/tracks")
def api_admin_bgm_list():
    if not is_admin():
        return jsonify({"ok": False}), 403
    conn = get_conn()
    try:
        q = request.args.get("q", "").strip()
        if q:
            rows = sql.query(conn, "bgm.selectTracksAdmin", (f"%{q}%",))
        else:
            rows = sql.query(conn, "bgm.selectTracksAdminAll")
        return jsonify({"tracks": [dict(r) for r in rows]})
    finally:
        conn.close()

@bp.route("/api/admin/bgm/upload", methods=["POST"])
def api_admin_bgm_upload():
    if not is_admin():
        return jsonify({"ok": False}), 403
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "msg": "\ud30c\uc77c\uc744 \uc120\ud0dd\ud558\uc138\uc694"}), 400
    if not _allowed(f.filename):
        return jsonify({"ok": False, "msg": "mp3, wav, ogg, m4a, aac, flac \ud30c\uc77c\ub9cc \uc5c5\ub85c\ub4dc \uac00\ub2a5\ud569\ub2c8\ub2e4"}), 400
    title = (request.form.get("title") or "").strip()
    if not title:
        title = os.path.splitext(f.filename)[0]
    ext = f.filename.rsplit(".", 1)[1].lower()
    saved_name = uuid.uuid4().hex + "." + ext
    save_path = os.path.join(BGM_DIR, saved_name)
    f.save(save_path)
    file_size = os.path.getsize(save_path)
    conn = get_conn()
    try:
        so_row = sql.query_one(conn, "bgm.nextTrackSortOrder")
        so = so_row["so"]
        new_id = sql.insert(conn, "bgm.insertTrack",
                            (title, f.filename, saved_name, file_size, so))
        conn.commit()
        return jsonify({"ok": True, "id": new_id, "title": title})
    finally:
        conn.close()
