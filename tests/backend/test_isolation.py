"""T-000-02：testing 模式写入记录后，正式数据库哈希和内容不变。"""

from __future__ import annotations

from pathlib import Path

from helpers import (
    dump_database,
    make_app,
    read_probe_rows,
    sha256_file,
    upgrade,
    write_probe_row,
)


def test_testing_writes_leave_the_other_database_untouched(tmp_path: Path) -> None:
    # 先准备一个「正式」库：迁移并留存基线哈希
    prod_path = tmp_path / "production.sqlite"
    prod_app = make_app(prod_path)
    upgrade(prod_app)
    prod_app.extensions["db_engine"].dispose()
    prod_hash = sha256_file(prod_path)
    prod_snapshot = dump_database(prod_path)

    # testing 模式下写入记录
    testing_path = tmp_path / "testing.sqlite"
    testing_app = make_app(testing_path)
    upgrade(testing_app)
    write_probe_row(testing_app, "在测试库写入的记录")

    assert read_probe_rows(testing_app) == ["在测试库写入的记录"]

    # 正式库的哈希与内容都不受影响
    assert sha256_file(prod_path) == prod_hash
    assert dump_database(prod_path) == prod_snapshot
    assert "test_probe" not in prod_snapshot, "夹具表不应出现在正式库中"

    testing_app.extensions["db_engine"].dispose()


def test_testing_config_defaults_to_a_temp_path() -> None:
    """未显式指定时，testing 配置的数据库落在系统临时目录，而非项目目录。"""
    from app import create_app

    app = create_app("testing")
    url = app.config["DATABASE_URL"]
    assert url.startswith("sqlite:///")
    assert "instance" not in url.replace("\\", "/").split("sqlite:///")[1].split("/")
    app.extensions["db_engine"].dispose()
