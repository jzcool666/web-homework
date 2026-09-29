"""T-000-01：新空数据库执行 upgrade 后外键开启；再次 upgrade 不改变数据。"""

from __future__ import annotations

from pathlib import Path

from alembic.script import ScriptDirectory

from app.cli import build_alembic_config
from app.db import read_sqlite_setting
from helpers import downgrade, dump_database, make_app, upgrade


def _head_revision(app) -> str:
    """当前迁移链 head，随各模块新增迁移而前移。"""
    return ScriptDirectory.from_config(build_alembic_config(app)).get_current_head()


def test_upgrade_on_empty_database_enables_foreign_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.sqlite"
    assert not db_path.exists(), "前置条件：数据库文件尚不存在"

    app = make_app(db_path)
    upgrade(app)

    assert db_path.exists(), "upgrade 应建立数据库文件"
    engine = app.extensions["db_engine"]
    # 连接级设置：新开的连接同样生效
    assert read_sqlite_setting(engine, "foreign_keys") == 1
    assert read_sqlite_setting(engine, "busy_timeout") == 5000
    app.extensions["db_engine"].dispose()

    # 迁移链起点已落库，且停在当前 head
    snapshot = dump_database(db_path)
    assert "alembic_version" in snapshot
    assert snapshot["alembic_version"][1] == [f"('{_head_revision(app)}',)"]


def test_second_upgrade_does_not_change_data(tmp_path: Path) -> None:
    db_path = tmp_path / "twice.sqlite"
    app = make_app(db_path)

    upgrade(app)
    first = dump_database(db_path)

    upgrade(app)  # 再次 upgrade 应为空操作
    second = dump_database(db_path)

    assert first == second
    app.extensions["db_engine"].dispose()


def test_startup_does_not_create_or_clear_tables(tmp_path: Path) -> None:
    """建应用（启动路径）本身不得建表或清表。"""
    db_path = tmp_path / "startup.sqlite"
    app = make_app(db_path)
    # create_app 不连接数据库，故此时文件仍不存在
    assert not db_path.exists()
    app.extensions["db_engine"].dispose()


def test_spec001_downgrade_and_upgrade_on_disposable_database(tmp_path: Path) -> None:
    """在一次性库验证 0002 可回退并可重新升级，不触碰应用数据。"""
    app = make_app(tmp_path / "migration-roundtrip.sqlite")
    try:
        upgrade(app)
        engine = app.extensions["db_engine"]
        with engine.connect() as connection:
            names = set(connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).scalars())
        assert {"users", "sessions", "classes", "enrollments"} <= names

        downgrade(app)
        with engine.connect() as connection:
            names = set(connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).scalars())
        assert not {"users", "sessions", "classes", "enrollments"} & names

        upgrade(app)
        with engine.connect() as connection:
            names = set(connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).scalars())
        assert {"users", "sessions", "classes", "enrollments"} <= names
    finally:
        app.extensions["db_engine"].dispose()
