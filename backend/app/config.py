"""应用配置。

配置项与 README「环境和配置约定」一致：DATABASE_URL、UPLOAD_DIR、SECRET_KEY、
APP_ENV、COOKIE_SECURE。仓库只保存模板，真实密钥不进入版本库。

SQLite 文件路径在这里解析为绝对路径，避免工作目录变化导致连接到意外数据库。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# backend/ 目录（本文件位于 backend/app/config.py）
BACKEND_DIR = Path(__file__).resolve().parent.parent
# 仓库根目录
REPO_ROOT = BACKEND_DIR.parent

SQLITE_PREFIX = "sqlite:///"


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_sqlite_url(url: str) -> str:
    """把 SQLite 相对路径解析成绝对路径；非 SQLite URL 原样返回。"""
    if not url or not url.startswith(SQLITE_PREFIX):
        return url
    raw = url[len(SQLITE_PREFIX):]
    if raw in {"", ":memory:"} or raw.startswith("file:"):
        return url
    path = Path(raw)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    return SQLITE_PREFIX + path.as_posix()


def sqlite_file_path(url: str) -> Path | None:
    """返回 SQLite URL 对应的文件路径；内存库或非 SQLite 返回 None。"""
    if not url or not url.startswith(SQLITE_PREFIX):
        return None
    raw = url[len(SQLITE_PREFIX):]
    if raw in {"", ":memory:"} or raw.startswith("file:"):
        return None
    return Path(raw)


class BaseConfig:
    """公共默认值。SECRET_KEY 默认为空，由各环境显式给出。"""

    APP_ENV = "development"
    SECRET_KEY = None
    DATABASE_URL = f"{SQLITE_PREFIX}instance/app.sqlite"
    UPLOAD_DIR = "instance/uploads"
    COOKIE_SECURE = False
    SQL_ECHO = False

    @classmethod
    def from_env(cls) -> dict:
        """读取 README 约定的环境变量，缺省项不覆盖类默认值。"""
        values: dict[str, object] = {}
        if (v := os.environ.get("DATABASE_URL")) is not None:
            values["DATABASE_URL"] = v
        if (v := os.environ.get("UPLOAD_DIR")) is not None:
            values["UPLOAD_DIR"] = v
        if (v := os.environ.get("SECRET_KEY")) is not None:
            values["SECRET_KEY"] = v
        if (v := os.environ.get("COOKIE_SECURE")) is not None:
            values["COOKIE_SECURE"] = _as_bool(v)
        if (v := os.environ.get("SQL_ECHO")) is not None:
            values["SQL_ECHO"] = _as_bool(v)
        return values


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"
    SECRET_KEY = "dev-only-not-for-production"


class TestingConfig(BaseConfig):
    """测试配置：数据库落在系统临时目录，正式数据库不受影响。"""

    APP_ENV = "testing"
    SECRET_KEY = "testing-only"
    COOKIE_SECURE = False

    @classmethod
    def default_database_url(cls) -> str:
        tmp_dir = Path(tempfile.gettempdir()) / "digital-logic-testing"
        return f"{SQLITE_PREFIX}{tmp_dir.as_posix()}/testing.sqlite"


class ProductionConfig(BaseConfig):
    """生产配置：SECRET_KEY 与 DATABASE_URL 必须来自环境变量（见 .env.example）。"""

    APP_ENV = "production"
    SECRET_KEY = None
    DATABASE_URL = None
    COOKIE_SECURE = True


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def load_config(config_name: str | None = None, overrides: dict | None = None) -> dict:
    """合并「类默认值 → 环境变量 → 显式覆盖」，返回 Flask 配置字典。

    环境变量只在本模块解析，健康接口不会回显它们。
    """
    name = (config_name or os.environ.get("APP_ENV") or "development").strip().lower()
    if name not in CONFIG_BY_NAME:
        raise ValueError(f"未知的 APP_ENV: {name!r}，可选 {sorted(CONFIG_BY_NAME)}")
    config_cls = CONFIG_BY_NAME[name]

    settings: dict[str, object] = {}
    for key in ("APP_ENV", "SECRET_KEY", "DATABASE_URL", "UPLOAD_DIR", "COOKIE_SECURE", "SQL_ECHO"):
        settings[key] = getattr(config_cls, key)
    if name == "testing":
        settings["DATABASE_URL"] = TestingConfig.default_database_url()
    env_settings = config_cls.from_env()
    if name == "testing":
        # 测试不能继承开发/生产进程中的数据库地址；需要独立测试库时显式传 overrides。
        env_settings.pop("DATABASE_URL", None)
    settings.update(env_settings)
    if overrides:
        settings.update(overrides)

    settings["APP_ENV"] = name
    if name == "production":
        missing = [k for k in ("SECRET_KEY", "DATABASE_URL") if not settings.get(k)]
        if missing:
            raise RuntimeError(
                "生产环境必须通过环境变量提供 " + "、".join(missing) + "，仓库内不保存真实密钥"
            )
    if not settings.get("UPLOAD_DIR"):
        settings["UPLOAD_DIR"] = BaseConfig.UPLOAD_DIR
    settings["DATABASE_URL"] = resolve_sqlite_url(str(settings["DATABASE_URL"]))
    settings["UPLOAD_DIR"] = str(settings["UPLOAD_DIR"])
    settings["COOKIE_SECURE"] = _as_bool(settings["COOKIE_SECURE"])
    settings["SQL_ECHO"] = _as_bool(settings["SQL_ECHO"])
    return settings
