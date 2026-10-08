"""启动器的配置隔离、缓存更新和文件/进程边界；不启动业务测试库。"""

import importlib.util
import json
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("local_launcher", Path(__file__).resolve().parents[2] / "scripts/start_local.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_settings_persist_credentials_and_do_not_depend_on_directory(tmp_path):
    first = launcher.settings(tmp_path)
    assert first == launcher.settings(tmp_path)
    assert len(first["secret_key"]) >= 32
    assert 10 <= len(first["demo_password"]) <= 128
    assert "C:" not in json.dumps(first)
    other = tmp_path / "second"
    other.mkdir()
    assert launcher.settings(other)["secret_key"] != first["secret_key"]


def test_invalid_existing_settings_never_overwrite(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(launcher.LaunchError):
        launcher.settings(tmp_path)
    assert path.read_text(encoding="utf-8") == "{broken"
    launcher.write_json(path, dict(port=True, secret_key="abc", demo_password="DemoLongPassword"))
    with pytest.raises(launcher.LaunchError, match="port"):
        launcher.settings(tmp_path)


def test_child_environment_isolates_existing_env(tmp_path, monkeypatch):
    for key, value in dict(DATABASE_URL="sqlite:///real.sqlite", UPLOAD_DIR="real-uploads", APP_ENV="testing",
                           PYTHONPATH="other-backend", PYTHONHOME="other-python", LAB_JAVA="bad-java",
                           LAB_JAR="bad-jar", COOKIE_SECURE="1").items():
        monkeypatch.setenv(key, value)
    config = launcher.settings(tmp_path)
    env = launcher.child_environment(tmp_path, config, "chosen-java", "chosen-jar")
    assert env["DATABASE_URL"] == "sqlite:///" + (tmp_path / "demo.sqlite").as_posix()
    assert env["UPLOAD_DIR"] == str(tmp_path / "uploads")
    assert env["LAB_JAVA"] == "chosen-java" and env["LAB_JAR"] == "chosen-jar"
    assert env["FLASK_SKIP_DOTENV"] == "1" and env["APP_ENV"] == "production"
    assert env["COOKIE_SECURE"] == "0"
    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env


def test_corrupt_jar_preserved_and_not_downloaded(tmp_path, monkeypatch):
    monkeypatch.delenv("LAB_JAR", raising=False)
    path = tmp_path / "tools" / launcher.JAR_NAME
    path.parent.mkdir()
    path.write_bytes(b"wrong downloaded artifact")
    monkeypatch.setattr(launcher.urllib.request, "urlopen", lambda *a, **k: pytest.fail("must not download over existing file"))
    with pytest.raises(launcher.LaunchError, match="SHA-256"):
        launcher.ensure_jar(tmp_path, {})
    assert path.read_bytes() == b"wrong downloaded artifact"


def test_java17_does_not_mask_java21(tmp_path, monkeypatch):
    home = tmp_path / "home"
    first = tmp_path / "old-java.exe"
    second = home / ".jdks/jdk21/bin/java.exe"
    second.parent.mkdir(parents=True)
    first.touch()
    second.touch()
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.delenv("LAB_JAVA", raising=False)
    monkeypatch.setattr(launcher.Path, "home", lambda: home)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: str(first))
    monkeypatch.setattr(launcher, "check_command", lambda cmd: (0, 'openjdk version "17.0.1"' if cmd[0] == str(first) else 'openjdk version "21.0.7"'))
    assert launcher.find_java({}) == second.resolve()
    with pytest.raises(launcher.LaunchError):
        launcher.find_java(dict(java_path=str(first)))


def test_occupied_port_fails_before_install_or_database(tmp_path, monkeypatch):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    monkeypatch.setattr(launcher, "find_node", lambda: pytest.fail("must not install on occupied port"))
    try:
        with pytest.raises(launcher.LaunchError, match="占用"):
            launcher.launch(tmp_path, SimpleNamespace(port=port, no_browser=True, without_grader=True))
        assert not (tmp_path / "demo.sqlite").exists()
        assert not (tmp_path / "venv").exists()
        assert launcher.stop(tmp_path) == 0
        assert sock.getsockname()[1] == port
    finally:
        sock.close()


def test_frontend_changes_invalidate_build(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    for name in ("package.json", "package-lock.json", "index.html", "vite.config.js"):
        (frontend / name).write_text("initial", encoding="utf-8")
    monkeypatch.setattr(launcher, "REPO", tmp_path)
    before = launcher.frontend_fingerprint()
    (frontend / "src/page.vue").write_text("changed UI", encoding="utf-8")
    assert launcher.frontend_fingerprint() != before


def test_stop_token_not_shared_across_launches(tmp_path):
    launcher.write_json(tmp_path / "stop-request.json", dict(token="old-launch"))
    assert launcher.stop_requested(tmp_path, "old-launch")
    assert not launcher.stop_requested(tmp_path, "new-launch")
    launcher.write_json(tmp_path / "stop-request.json", ["invalid state"])
    assert not launcher.stop_requested(tmp_path, "new-launch")


def test_portable_assets_are_checked_without_node(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "REPO", tmp_path)
    asset = tmp_path / "frontend/dist/index.html"
    asset.parent.mkdir(parents=True)
    asset.write_text("built page", encoding="utf-8")
    manifest = {"schema": 1, "frontend_fingerprint": "source", "frontend_files":
                {"frontend/dist/index.html": launcher.sha256(asset)}}
    launcher.write_json(tmp_path / "portable.json", manifest)
    monkeypatch.setattr(launcher, "frontend_fingerprint", lambda: "source")
    monkeypatch.setattr(launcher, "run_step", lambda *a: pytest.fail("offline package must not install or build"))
    launcher.ensure_frontend(None, tmp_path, {}, tmp_path / "log", "token")
    asset.write_text("corrupt", encoding="utf-8")
    with pytest.raises(launcher.LaunchError, match="校验"):
        launcher.ensure_frontend(None, tmp_path, {}, tmp_path / "log", "token")


def test_portable_manifest_rejects_escape_and_changed_source(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "REPO", tmp_path)
    monkeypatch.setattr(launcher, "frontend_fingerprint", lambda: "changed")
    launcher.write_json(tmp_path / "portable.json", {"schema": 1, "frontend_fingerprint": "old",
                                                    "frontend_files": {"../outside": "hash"}})
    with pytest.raises(launcher.LaunchError):
        launcher.ensure_frontend(None, tmp_path, {}, tmp_path / "log", "token")
    monkeypatch.setattr(launcher, "frontend_fingerprint", lambda: "old")
    with pytest.raises(launcher.LaunchError):
        launcher.ensure_frontend(None, tmp_path, {}, tmp_path / "log", "token")


def test_portable_java_is_preferred_to_host_java(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "REPO", tmp_path)
    monkeypatch.delenv("LAB_JAVA", raising=False)
    bundled = tmp_path / "runtime/java/bin/java.exe"
    bundled.parent.mkdir(parents=True)
    bundled.touch()
    monkeypatch.setattr(launcher, "check_command", lambda cmd: (0, 'openjdk version "21.0.7"'))
    assert launcher.find_java({}) == bundled.resolve()
