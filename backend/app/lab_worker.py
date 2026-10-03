"""Independent durable queue worker; importing Flask never starts a thread."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import uuid
import click
from flask import current_app
from sqlalchemy import select, update, inspect
from .models import now_utc
from .models_lab import LabAttempt
from .lab_circ import validate_circ
from .lab_engine import LabError
from .lab_logisim import ENGINE_VERSION, JAR_SHA256, runtime, grade_circ
from .config import BACKEND_DIR


def upload_root(config):
    path = Path(config["UPLOAD_DIR"])
    return (path if path.is_absolute() else BACKEND_DIR / path).resolve()


def storage_root(config):
    return upload_root(config) / "lab-circuits"


def runtime_root(config):
    return upload_root(config) / "lab-runtime"


def identity(config):
    return hashlib.sha256(str(config["DATABASE_URL"]).encode()).hexdigest()


def worker_available(config):
    try:
        row = json.loads(
            (runtime_root(config) / "heartbeat.json").read_text(encoding="utf-8")
        )
        return (
            row["database"] == identity(config)
            and row["engine"] == ENGINE_VERSION
            and row["jar_sha256"] == JAR_SHA256
            and 0 <= time.time() - row["timestamp"] <= 15
            and Path(config.get("LAB_JAVA", "")).is_file()
            and Path(config.get("LAB_JAR", "")).is_file()
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def heartbeat(config, token):
    root = runtime_root(config)
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / (token + ".tmp")
    tmp.write_text(
        json.dumps(
            dict(
                token=token,
                timestamp=time.time(),
                database=identity(config),
                engine=ENGINE_VERSION,
                jar_sha256=JAR_SHA256,
            )
        ),
        encoding="utf-8",
    )
    tmp.replace(root / "heartbeat.json")


@contextmanager
def worker_lock(config):
    root = runtime_root(config)
    root.mkdir(parents=True, exist_ok=True)
    file = (root / "worker.lock").open("a+b")
    try:
        if file.tell() == 0:
            file.write(b"0")
            file.flush()
        file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LabError(
                "此上传目录已有worker运行", "WORKER_ALREADY_RUNNING"
            ) from exc
        yield
    finally:
        file.close()


def recover_expired(factory):
    with factory() as s:
        result = s.execute(
            update(LabAttempt)
            .where(LabAttempt.status == "running", LabAttempt.lease_until < now_utc())
            .values(
                status="error",
                score=None,
                passed=None,
                finished_at=now_utc(),
                lease_until=None,
                error_json=json.dumps(
                    dict(
                        code="WORKER_INTERRUPTED",
                        message="测评中断或租约已过期，请使用新请求重试",
                    ),
                    ensure_ascii=False,
                ),
            )
        )
        s.commit()
        return result.rowcount


def claim(factory, token):
    with factory() as s:
        row = s.scalar(
            select(LabAttempt)
            .where(LabAttempt.status == "queued", LabAttempt.mode == "circ")
            .order_by(LabAttempt.id)
            .limit(1)
        )
        if row is None:
            return None
        id = row.id
        lease = (datetime.now(timezone.utc) + timedelta(seconds=60)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        count = s.execute(
            update(LabAttempt)
            .where(LabAttempt.id == id, LabAttempt.status == "queued")
            .values(
                status="running",
                started_at=now_utc(),
                lease_until=lease,
                worker_token=token,
            )
        ).rowcount
        s.commit()
        return id if count == 1 else None


def process_job(factory, id, token, config):
    with factory() as s:
        row = s.get(LabAttempt, id)
        if row is None or row.worker_token != token or row.status != "running":
            return False
        task = json.loads(row.task_snapshot_json)
        suite = json.loads(row.suite_snapshot_json)
        storage_key = row.storage_key
        expected_hash = row.sha256
    result = error = None
    try:
        if not storage_key or not __import__("re").fullmatch(
            r"[a-f0-9]{32}\.circ", storage_key
        ):
            raise LabError("附件记录无效", "ARTIFACT_UNAVAILABLE")
        content = (storage_root(config) / storage_key).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise LabError("附件校验失败，请恢复原文件", "ARTIFACT_UNAVAILABLE")
        canonical = validate_circ(content, task)
        result = grade_circ(task, suite, canonical, config)
    except LabError as exc:
        error = dict(code=exc.code, message=str(exc))
    except OSError:
        error = dict(
            code="ARTIFACT_UNAVAILABLE", message="电路附件不可读取，请恢复备份"
        )
    except Exception:
        # Raw XML/Java/SQL diagnostics never become a student response.
        error = dict(
            code="GRADING_PROCESS_FAILED", message="测评服务发生错误，请使用新请求重试"
        )
    values = dict(
        status="error" if error else "done",
        finished_at=now_utc(),
        lease_until=None,
        error_json=json.dumps(error, ensure_ascii=False) if error else None,
        result_json=json.dumps(result, ensure_ascii=False) if result else None,
        score=result["score"] if result else None,
        passed=int(result["passed"]) if result else None,
    )
    with factory() as s:
        count = s.execute(
            update(LabAttempt)
            .where(
                LabAttempt.id == id,
                LabAttempt.worker_token == token,
                LabAttempt.status == "running",
            )
            .values(**values)
        ).rowcount
        s.commit()
    return count == 1


def self_test(config):
    checked = runtime(config)
    project = b'<project source="5.0.0" version="1.0"><lib desc="#Wiring" name="0"/><main name="main"/><circuit name="main"><comp lib="0" loc="(100,100)" name="Pin"><a name="label" val="D"/></comp><comp lib="0" loc="(200,100)" name="Pin"><a name="label" val="Q"/><a name="output" val="true"/><a name="facing" val="west"/></comp><wire from="(100,100)" to="(200,100)"/></circuit></project>'
    task = dict(
        ports=[
            dict(label="D", direction="input", width=1),
            dict(label="Q", direction="output", width=1),
        ]
    )
    suite = dict(
        cases=[
            dict(
                set_id=1,
                steps=[
                    dict(inputs=dict(D="0"), expected=dict(Q="0"), scored=True),
                    dict(inputs=dict(D="1"), expected=dict(Q="1"), scored=True),
                ],
            )
        ]
    )
    if not grade_circ(task, suite, project, config, checked)["passed"]:
        raise LabError("真实引擎自检未通过", "LAB_ENGINE_UNAVAILABLE")


def register_worker_cli(app):
    @app.cli.command("lab-worker")
    @click.option("--once", is_flag=True, help="自检后处理一个任务并退出，用于部署检查")
    def worker(once):
        config = dict(current_app.config)
        factory = app.extensions["db_session"]
        token = uuid.uuid4().hex
        stop = threading.Event()
        thread = None
        try:
            with worker_lock(config):
                if not inspect(app.extensions["db_engine"]).has_table("lab_attempts"):
                    raise LabError(
                        "实验数据表尚未升级，请先执行flask db upgrade",
                        "LAB_ENGINE_UNAVAILABLE",
                    )
                self_test(config)

                def pulse():
                    while not stop.is_set():
                        heartbeat(config, token)
                        stop.wait(5)

                thread = threading.Thread(target=pulse, daemon=True)
                thread.start()
                click.echo("Logisim 5.0.0 自检通过；worker已就绪（并发1）。")
                while True:
                    recover_expired(factory)
                    id = claim(factory, token)
                    if id is not None:
                        process_job(factory, id, token, config)
                        click.echo(f"已处理任务 {id}")
                    if once:
                        break
                    time.sleep(0.5 if id is None else 0.01)
        except LabError as exc:
            raise click.ClickException(str(exc)) from exc
        except KeyboardInterrupt:
            click.echo("worker停止；未完成任务由租约恢复。")
        finally:
            stop.set()
            if thread:
                thread.join(timeout=6)
            path = runtime_root(config) / "heartbeat.json"
            try:
                if json.loads(path.read_text(encoding="utf-8")).get("token") == token:
                    path.unlink()
            except (OSError, ValueError):
                pass
