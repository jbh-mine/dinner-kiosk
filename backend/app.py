"""
퓨전 석식 주문 시스템 v7.0 (PostgreSQL)
Flask Application Factory
"""
import os, secrets, datetime
from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from backend.db_init import init_db


class CustomJSONProvider(DefaultJSONProvider):
    """datetime, date 객체를 자동 직렬화"""
    def default(self, o):
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        return super().default(o)


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.json_provider_class = CustomJSONProvider
    app.json = CustomJSONProvider(app)

    app.secret_key = os.environ.get("SECRET_KEY", "fusion_order_proj_a_secret_7f3k9p2x")
    app.config["SESSION_COOKIE_NAME"] = "session_proj_a"

    app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024

    init_db()

    from backend.mapper import sql
    sql.load()

    from backend.routes.pages       import bp as pages_bp
    from backend.routes.api_public  import bp as public_bp
    from backend.routes.api_orders  import bp as orders_bp
    from backend.routes.api_admin   import bp as admin_bp
    from backend.routes.api_export  import bp as export_bp
    from backend.routes.api_user    import bp as user_bp
    from backend.routes.api_board   import bp as board_api_bp
    from backend.routes.pages_board import bp as board_pages_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(board_api_bp)
    app.register_blueprint(board_pages_bp)

    try:
        from backend.routes.api_bgm import bp as bgm_bp
        app.register_blueprint(bgm_bp)
    except ImportError:
        pass

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "파일 크기가 30MB를 초과합니다"}), 413

    return app
