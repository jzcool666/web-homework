"""SPEC-000 测试夹具。"""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import make_app


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
