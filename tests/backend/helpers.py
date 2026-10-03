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


# ---- SPEC-001 接口测试助手 ----

API = "/api/v1"
DEFAULT_PASSWORD = "Passw0rd!23"


def api_call(client, method: str, path: str, *, csrf_token: str | None = None, **kwargs):
    """按 APIC 约定发请求：写方法自动附带 X-CSRF-Token。"""
    headers = dict(kwargs.pop("headers", {}) or {})
    if csrf_token is not None:
        headers["X-CSRF-Token"] = csrf_token
    return getattr(client, method)(path, headers=headers, **kwargs)


def get_csrf(client) -> str:
    response = client.get(f"{API}/auth/csrf")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]["csrf_token"]


def register(
    client,
    csrf_token,
    *,
    login_name: str,
    student_no: str,
    display_name: str = "学生",
    password: str = DEFAULT_PASSWORD,
):
    return api_call(
        client,
        "post",
        f"{API}/auth/register",
        csrf_token=csrf_token,
        json={
            "login_name": login_name,
            "student_no": student_no,
            "display_name": display_name,
            "password": password,
        },
    )


def login(client, csrf_token, *, login_name: str, password: str = DEFAULT_PASSWORD):
    return api_call(
        client,
        "post",
        f"{API}/auth/login",
        csrf_token=csrf_token,
        json={"login_name": login_name, "password": password},
    )


def scalar(app, sql: str, params: tuple = ()):
    """直接在库上取标量，用于核对口令散列/角色等 ORM 之外的证据。"""
    engine = app.extensions["db_engine"]
    with engine.connect() as connection:
        return connection.exec_driver_sql(sql, params).scalar()


def create_admin(app, *, login_name: str = "admin_root", password: str = "Adm1nPass!23"):
    """用 CLI 命令建立管理员（与真实初始化路径一致）。"""
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["init-admin", "--login-name", login_name, "--password", password]
    )
    assert result.exit_code == 0, result.output
    return login_name, password
