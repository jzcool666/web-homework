import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.models_lab import LabTask, LabAttempt
from app.lab_templates import template
from app.lab_catalog import profile
from app.lab_engine import LabError
from app.lab_worker import (
    claim,
    process_job,
    recover_expired,
    worker_available,
    heartbeat,
    worker_lock,
    storage_root,
)
from test_lab_api import lab as lab_fixture, task, data, PREFIX, CSRF
from lab_circ_fixtures import reference_circ

# Register the shared pytest fixture without confusing it with local state.
lab = lab_fixture


def upload(lab, c, t=None, content=None, key="upload-key-01", **extra):
    t = t or task(c)
    body = dict(
        task_id=str(t["id"]),
        task_version=str(t["version"]),
        class_id=str(lab["classes"][0]),
        request_key=key,
        file=(
            io.BytesIO(content if content is not None else reference_circ(t["code"])),
            "my.circ",
        ),
    )
    body.update(extra)
    return c.post(
        PREFIX + "/lab-attempts/circ", data=body, headers={"X-CSRF-Token": CSRF}
    )


@pytest.fixture
def ready(lab, monkeypatch, tmp_path):
    lab["app"].config["UPLOAD_DIR"] = str(tmp_path / "uploads")
    monkeypatch.setattr("app.api_lab.worker_available", lambda config: True)
    return lab


def test_upload_unavailable_is_503_and_does_not_store_or_queue(lab, tmp_path):
    lab["app"].config["UPLOAD_DIR"] = str(tmp_path / "uploads")
    c = lab["client"](1)
    assert upload(lab, c).status_code == 503
    with lab["factory"]() as s:
        assert s.query(LabAttempt).count() == 0
    assert not storage_root(lab["app"].config).exists()


def test_upload_idempotency_private_download_and_invalid_payloads(ready):
    lab = ready
    c = lab["client"](1)
    t = task(c)
    content = reference_circ(t["code"])
    result = data(upload(lab, c, t, content), 202)
    assert (
        result["status"] == "queued"
        and result["score"] is None
        and result["passed"] is None
    )
    assert data(upload(lab, c, t, content))["id"] == result["id"]
    assert upload(lab, c, t, content + b" ", key="upload-key-01").status_code == 409
    path = PREFIX + f"/lab-attempts/{result['id']}/file"
    for index, status in [(1, 200), (0, 200), (2, 404), (3, 404), (4, 404), (5, 403)]:
        r = lab["client"](index).get(path)
        assert r.status_code == status
        if status == 200:
            assert r.data == content
    assert "storage_key" not in json.dumps(result) and "expected" not in json.dumps(
        result
    )
    for extra, status in [
        ({"score": "100"}, 422),
        ({"file": (io.BytesIO(b"bad"), "file.txt")}, 415),
        ({"file": (io.BytesIO(b"a" * (2 * 1024 * 1024 + 1)), "big.circ")}, 413),
    ]:
        assert upload(lab, c, key="upload-key-02", **extra).status_code == status
    assert (
        upload(
            lab,
            c,
            content=template(profile("LAB-D")).replace(b"5.0.0", b"3.8.0"),
            key="upload-key-03",
        ).status_code
        == 422
    )


def test_rate_capacity_and_atomic_claim(ready):
    lab = ready
    c = lab["client"](1)
    first = data(upload(lab, c), 202)
    assert upload(lab, c, key="upload-key-02").status_code == 429
    with lab["factory"]() as s:
        row = s.get(LabAttempt, first["id"])
        row.created_at = "2020-01-01T00:00:00Z"
        s.commit()
    second = data(upload(lab, c, key="upload-key-02"), 202)
    with lab["factory"]() as s:
        row = s.get(LabAttempt, second["id"])
        row.created_at = "2020-01-02T00:00:00Z"
        s.commit()
    assert upload(lab, c, key="upload-key-03").status_code == 429
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(
            pool.map(
                lambda token: claim(lab["factory"], token), ["worker-a", "worker-b"]
            )
        )
    # Either two different tasks, or one winner and a CAS loser; never same job twice.
    assert len(set(id for id in ids if id is not None)) == len(
        [id for id in ids if id is not None]
    )
    assert any(id is not None for id in ids)


def test_worker_frozen_snapshot_error_null_and_expired_lease(ready, monkeypatch):
    lab = ready
    c = lab["client"](1)
    t = task(c)
    result = data(upload(lab, c, t), 202)
    with lab["factory"]() as s:
        task_row = s.get(LabTask, t["id"])
        task_row.version += 1
        task_row.private_suite_json = "{}"
        s.commit()

    def grade(task, suite, content, config):
        assert task["version"] == 1 and suite["cases"]
        raise LabError("测评超过15秒", "GRADING_TIMEOUT")

    monkeypatch.setattr("app.lab_worker.grade_circ", grade)
    id = claim(lab["factory"], "one")
    assert id == result["id"]
    assert process_job(lab["factory"], id, "other", lab["app"].config) is False
    assert process_job(lab["factory"], id, "one", lab["app"].config)
    row = data(c.get(PREFIX + f"/lab-attempts/{id}"))
    assert (
        row["status"] == "error"
        and row["score"] is None
        and row["passed"] is None
        and row["error"]["code"] == "GRADING_TIMEOUT"
    )
    with lab["factory"]() as s:
        r = s.get(LabAttempt, id)
        r.status = "running"
        r.lease_until = "2020-01-01T00:00:00Z"
        s.commit()
    assert recover_expired(lab["factory"]) == 1
    assert not process_job(lab["factory"], id, "one", lab["app"].config)
    assert (
        data(c.get(PREFIX + f"/lab-attempts/{id}"))["error"]["code"]
        == "WORKER_INTERRUPTED"
    )


def test_worker_heartbeat_database_bound_expiry_and_single_lock(tmp_path):
    java = tmp_path / "java"
    jar = tmp_path / "jar"
    java.write_text("")
    jar.write_text("")
    config = dict(
        UPLOAD_DIR=str(tmp_path),
        DATABASE_URL="sqlite:///one",
        LAB_JAVA=str(java),
        LAB_JAR=str(jar),
    )
    heartbeat(config, "token")
    assert worker_available(config)
    assert not worker_available(dict(config, DATABASE_URL="sqlite:///other"))
    path = tmp_path / "lab-runtime" / "heartbeat.json"
    row = json.loads(path.read_text())
    row["timestamp"] = time.time() - 16
    path.write_text(json.dumps(row))
    assert not worker_available(config)
    with worker_lock(config):
        with pytest.raises(LabError):
            with worker_lock(config):
                pass


@pytest.mark.skipif(
    not os.environ.get("LAB_REAL_ENGINE"), reason="真实worker验收需配置Java/JAR"
)
def test_real_upload_claim_grade_download_and_teacher_summary(ready):
    lab = ready
    config = lab["app"].config
    config.update(LAB_JAVA=os.environ["LAB_JAVA"], LAB_JAR=os.environ["LAB_JAR"])
    c = lab["client"](1)
    t = task(c, "LAB-S4")
    queued = data(upload(lab, c, t), 202)
    id = claim(lab["factory"], "real-worker")
    assert id == queued["id"] and process_job(lab["factory"], id, "real-worker", config)
    result = data(c.get(PREFIX + f"/lab-attempts/{id}"))
    assert result["status"] == "done" and result["score"] == 100 and result["passed"]
    summary = data(
        lab["client"](0).get(PREFIX + f"/analytics/labs?class_id={lab['classes'][0]}")
    )
    row = next(
        r for r in summary["tasks"] if r["task_id"] == t["id"] and r["mode"] == "circ"
    )
    assert (
        row["participant_count"] == 1
        and row["passed_student_count"] == 1
        and row["attempt_count"] == 1
        and row["pass_rate"] == 1
    )
