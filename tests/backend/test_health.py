"""T-000-03：/health 正常返回 200 且无密钥；数据库断开返回 503 及可读原因。"""

from __future__ import annotations

from pathlib import Path

from app import create_app
from helpers import make_app

HEALTH_PATH = "/api/v1/health"


def test_health_returns_ok_without_leaking_secrets(client, tmp_path: Path) -> None:
    response = client.get(HEALTH_PATH)

    assert response.status_code == 200
    body = response.get_json()
    assert body["data"]["status"] == "ok"
    assert isinstance(body["data"]["version"], str) and body["data"]["version"]
    assert "server_time" in body["meta"]

    raw = response.get_data(as_text=True)
    for leak in (
        "SECRET_KEY",
        "dev-only-not-for-production",
        "testing-only",
        "DATABASE_URL",
        "sqlite:///",
        str(tmp_path),
        "instance",
    ):
        assert leak not in raw, f"健康响应不应包含 {leak!r}"


def test_health_returns_503_with_readable_reason_when_database_is_unavailable(tmp_path: Path) -> None:
    # 指向一个目录：SQLite 无法把它当作数据库打开
    unusable = tmp_path / "not-a-database"
    unusable.mkdir()
    app = make_app(unusable)

    response = app.test_client().get(HEALTH_PATH)

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "DB_BUSY"
    reason = body["error"]["details"]["reason"]
    assert reason and isinstance(reason, str), "503 必须给出可读原因"
    # 原因可读，但不得回显文件系统路径
    assert str(unusable) not in response.get_data(as_text=True)
    assert str(tmp_path) not in response.get_data(as_text=True)

    app.extensions["db_engine"].dispose()


def test_health_is_reachable_without_authentication(client) -> None:
    """E000 为匿名接口，未登录也应返回 200。"""
    assert client.get(HEALTH_PATH).status_code == 200


def test_unknown_api_path_uses_the_common_error_envelope(client) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert "server_time" in body["meta"]


def test_sqlite_url_is_resolved_to_an_absolute_path(tmp_path: Path) -> None:
    target = tmp_path / "relative.sqlite"
    app = create_app("testing", {"DATABASE_URL": f"sqlite:///{target.as_posix()}"})

    resolved = app.config["DATABASE_URL"].split("sqlite:///", 1)[1]
    assert Path(resolved).is_absolute()
    app.extensions["db_engine"].dispose()
