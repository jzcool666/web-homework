"""应用工厂。

SPEC-000 只负责工程骨架：配置、数据库引擎、迁移入口、健康检查和同源静态文件。
启动过程**不会**建表、清表或写入业务数据；业务表由各模块的迁移追加。
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, send_from_directory

from .api_admin import bp as admin_bp
from .api_assessment import bp as assessment_bp
from .api_attendance import bp as attendance_bp
from .api_auth import bp as auth_bp
from .api_content import bp as content_bp
from .auth import register_session_hooks
from .cli import register_cli
from .config import REPO_ROOT, load_config, sqlite_file_path
from .db import create_db_engine, make_session_factory
from .errors import register_error_handlers
from .health import bp as health_bp
from .seed_content import register_content_cli
from .store import close_db_session

__version__ = "0.1.0"

API_PREFIX = "/api/v1"
DEFAULT_FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


def _ensure_sqlite_parent(database_url: str) -> None:
    """只在文件缺失时补建 SQLite 所在目录，不创建也不修改数据库内容。"""
    path = sqlite_file_path(database_url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)


def _register_frontend(app: Flask) -> None:
    """构建产物存在时由后端同源提供；未构建则保持纯 API 服务。"""
    dist = Path(app.config["FRONTEND_DIST"])
    if not dist.is_dir():
        app.logger.info("未找到前端构建产物 %s，仅提供 API", dist)
        return

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _serve_frontend(path: str):
        if path.startswith("api/"):
            abort(404)
        candidate = dist / path
        if path and candidate.is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")


def create_app(config_name: str | None = None, overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(load_config(config_name, overrides))
    app.config.setdefault("APP_VERSION", __version__)
    app.config.setdefault("FRONTEND_DIST", str(DEFAULT_FRONTEND_DIST))

    _ensure_sqlite_parent(app.config["DATABASE_URL"])

    engine = create_db_engine(app.config["DATABASE_URL"], echo=app.config["SQL_ECHO"])
    app.extensions["db_engine"] = engine
    app.extensions["db_session"] = make_session_factory(engine)

    app.register_blueprint(health_bp, url_prefix=API_PREFIX)
    app.register_blueprint(auth_bp, url_prefix=API_PREFIX)
    app.register_blueprint(admin_bp, url_prefix=API_PREFIX)
    app.register_blueprint(attendance_bp, url_prefix=API_PREFIX)
    app.register_blueprint(assessment_bp, url_prefix=API_PREFIX)
    app.register_blueprint(content_bp, url_prefix=API_PREFIX)

    register_error_handlers(app)
    register_cli(app)
    register_content_cli(app)
    register_session_hooks(app)
    app.teardown_appcontext(close_db_session)
    _register_frontend(app)

    return app
