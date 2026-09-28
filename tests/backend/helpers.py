"""SPEC-000 测试用的公共助手。

隔离原则：每个用例用自己的临时数据库文件，任何用例都不触碰项目内的
instance/ 数据库；需要写记录时使用本文件定义的**最小隔离夹具表**，
不引入业务表——业务表由各模块的迁移追加。
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from alembic import command as alembic_command

from app import create_app
from app.cli import build_alembic_config
from app.config import SQLITE_PREFIX

# 仅测试使用的最小夹具表，不属于应用 schema
PROBE_DDL = (
    "CREATE TABLE IF NOT EXISTS test_probe "
    "(id INTEGER PRIMARY KEY AUTOINCREMENT, note TEXT NOT NULL)"
)


def sqlite_url(path: Path) -> str:
    return f"{SQLITE_PREFIX}{path.as_posix()}"


def make_app(db_path: Path):
    """按 testing 配置建应用，数据库指向给定路径。"""
    return create_app("testing", {"DATABASE_URL": sqlite_url(db_path)})


def upgrade(app, revision: str = "head") -> None:
    alembic_command.upgrade(build_alembic_config(app), revision)


def downgrade(app, revision: str = "-1") -> None:
    alembic_command.downgrade(build_alembic_config(app), revision)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump_database(path: Path) -> dict:
    """导出库内所有表及其行，用于比较操作前后内容是否变化。"""
    connection = sqlite3.connect(path)
    try:
        snapshot: dict[str, list] = {}
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        for name in names:
            cursor = connection.execute(f'SELECT * FROM "{name}"')
            columns = tuple(description[0] for description in cursor.description)
            snapshot[name] = [columns, sorted(repr(row) for row in cursor.fetchall())]
        return snapshot
    finally:
        connection.close()


def write_probe_row(app, note: str) -> None:
    engine = app.extensions["db_engine"]
    with engine.begin() as connection:
        connection.exec_driver_sql(PROBE_DDL)
        connection.exec_driver_sql("INSERT INTO test_probe (note) VALUES (?)", (note,))


def read_probe_rows(app) -> list[str]:
    engine = app.extensions["db_engine"]
    with engine.connect() as connection:
        return [
            row[0]
            for row in connection.exec_driver_sql("SELECT note FROM test_probe ORDER BY id")
        ]
