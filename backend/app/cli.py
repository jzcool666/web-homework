"""`flask db` 命令组。

README 约定的命令是 `python -m flask --app app:create_app db upgrade`（工作目录 backend）。
这里直接调用 Alembic 的 API，迁移脚本本身仍是标准 Alembic，没有额外封装层。
"""

from __future__ import annotations

import click
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from flask import Flask

from .config import BACKEND_DIR

ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
MIGRATIONS_DIR = BACKEND_DIR / "migrations"


def build_alembic_config(app: Flask) -> AlembicConfig:
    """把应用解析出的 DATABASE_URL 交给 Alembic，避免两处配置漂移。"""
    config = AlembicConfig(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", app.config["DATABASE_URL"])
    return config


def register_cli(app: Flask) -> None:
    @app.cli.group("db")
    def db_group() -> None:
        """数据库迁移（Alembic）。"""

    @db_group.command("upgrade")
    @click.argument("revision", default="head")
    def upgrade(revision: str) -> None:
        """升级到指定版本，默认 head。"""
        alembic_command.upgrade(build_alembic_config(app), revision)

    @db_group.command("downgrade")
    @click.argument("revision", default="-1")
    def downgrade(revision: str) -> None:
        """回退到指定版本，默认回退一步。"""
        alembic_command.downgrade(build_alembic_config(app), revision)

    @db_group.command("current")
    def current() -> None:
        """显示当前数据库版本。"""
        alembic_command.current(build_alembic_config(app), verbose=True)
