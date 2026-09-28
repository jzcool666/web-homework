"""SPEC-000 测试夹具。"""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import make_app, upgrade


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "app.sqlite"


@pytest.fixture
def app(db_path: Path):
    application = make_app(db_path)
    yield application
    application.extensions["db_engine"].dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def upgraded_app(db_path: Path):
    """已升级到 head 的应用（SPEC-001 及后续模块需要业务表）。"""
    application = make_app(db_path)
    upgrade(application)
    yield application
    application.extensions["db_engine"].dispose()


@pytest.fixture
def api(upgraded_app):
    """一个已迁移应用的测试客户端；同一 app 可再 new_client() 模拟他人。"""
    return upgraded_app.test_client()
