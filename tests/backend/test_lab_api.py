from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.models import User, SchoolClass, Enrollment, AuthSession
from app.models_lab import LabTask, LabAttempt
from app.models_content import Chapter, KnowledgePoint
from app.security import hash_token
from app.seed_labs import seed_labs
from app.api_lab import dump
from lab_fixtures import reference_board

PREFIX = "/api/v1"
CSRF = "lab-csrf-valid"


@pytest.fixture
def lab(upgraded_app):
    app = upgraded_app
    factory = app.extensions["db_session"]
    with factory() as s:
        users = []
        for i, role in enumerate(
            ["teacher", "student", "student", "teacher", "student", "admin"], 1
        ):
            u = User(
                login_name=f"lab_user_{i}",
                student_no=f"2420000{i}" if role == "student" else None,
                display_name=f"实验用户{i}",
                password_hash="unused",
                role=role,
                active=1,
            )
            s.add(u)
            s.flush()
            users.append(u)
        a = SchoolClass(name="实验甲班", teacher_id=users[0].id, active=1)
        b = SchoolClass(name="实验乙班", teacher_id=users[3].id, active=1)
        s.add_all([a, b])
        s.flush()
        for u, c in [(users[1], a), (users[2], a), (users[4], b)]:
            s.add(Enrollment(class_id=c.id, student_id=u.id, active=1))
        chapter = Chapter(title="接线课程", owner_id=users[0].id, published=1)
        s.add(chapter)
        s.flush()
        s.add(
            KnowledgePoint(
                chapter_id=chapter.id,
                title="D触发器计数器寄存器状态",
                body_md="用于隔离测试",
                owner_id=users[0].id,
                published=1,
            )
        )
        s.flush()
        seed_labs(s)
        for i, u in enumerate(users):
            s.add(
                AuthSession(
                    user_id=u.id,
                    token_hash=hash_token(f"lab-token-{i}"),
                    csrf_hash=hash_token(CSRF),
                    expires_at=(
                        datetime.now(timezone.utc) + timedelta(hours=1)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
            )
        s.commit()
        ids = [u.id for u in users]
        classes = [a.id, b.id]

    def client(i):
        c = app.test_client()
        c.set_cookie("sid", f"lab-token-{i}")
        return c

    return dict(app=app, factory=factory, client=client, users=ids, classes=classes)


def post(c, path, body):
    return c.post(PREFIX + path, json=body, headers={"X-CSRF-Token": CSRF})


def data(response, status=200):
    assert response.status_code == status, response.get_data(as_text=True)
    return response.get_json()["data"]


def task(c, code="LAB-D"):
    return next(t for t in data(c.get(PREFIX + "/lab-tasks")) if t["code"] == code)


def create(c, t, class_id, key="session-key-01"):
    return data(
        post(
            c,
            "/lab-sessions",
            dict(
                task_id=t["id"],
                task_version=t["version"],
                class_id=class_id,
                request_key=key,
            ),
        ),
        201,
    )


def connect_all(c, row, code):
    for index, w in enumerate(reference_board(code)["wires"]):
        row = data(
            post(
                c,
                f"/lab-sessions/{row['id']}/actions",
                dict(
                    version=row["version"],
                    action_key=f"wire-key-{index:03}",
                    op="connect",
                    payload={"from": w["from"], "to": w["to"]},
                ),
            )
        )
    return row


def test_seed_four_tasks_is_idempotent_and_private(lab):
    c = lab["client"](1)
    rows = data(c.get(PREFIX + "/lab-tasks"))
    assert len(rows) == 4
    assert not any(
        word in dump(rows)
        for word in ("private_suite", "expected", "wires", "request_hash")
    )
    with lab["factory"]() as s:
        assert seed_labs(s) == 0
    r = c.get(PREFIX + f"/lab-tasks/{rows[0]['id']}/template")
    assert (
        r.status_code == 200
        and b'<main name="main"' in r.data
        and b"<wire " not in r.data
    )


@pytest.mark.parametrize("code", ["LAB-D", "LAB-C6", "LAB-S4", "LAB-FSM"])
def test_real_server_actions_grade_snapshot_and_history(lab, code):
    c = lab["client"](1)
    t = task(c, code)
    row = connect_all(c, create(c, t, lab["classes"][0]), code)
    body = dict(
        session_id=row["id"],
        session_version=row["version"],
        task_version=t["version"],
        request_key="grade-key-01",
    )
    result = data(post(c, "/lab-attempts/wiring", body), 201)
    assert result["score"] == 100 and result["passed"] and result["status"] == "done"
    assert result["session_snapshot"]["board"]["wires"] == row["board"]["wires"]
    assert len(result["session_snapshot"]["events"]) == len(row["events"])
    assert data(post(c, "/lab-attempts/wiring", body))["id"] == result["id"]
    data(
        post(
            c,
            f"/lab-sessions/{row['id']}/actions",
            dict(
                version=row["version"],
                action_key="reset-key-01",
                op="reset",
                payload={},
            ),
        )
    )
    historic = data(c.get(PREFIX + f"/lab-attempts/{result['id']}"))
    assert historic["session_snapshot"]["board"]["wires"] == row["board"]["wires"]
    assert historic["score"] == 100
    start = data(c.get(PREFIX + f"/lab-attempts/{result['id']}?at_seq=0"))
    assert start["session_snapshot"]["board"]["wires"] == [] and start["score"] == 100
    assert c.get(PREFIX + f"/lab-attempts/{result['id']}?at_seq=999").status_code == 422


def test_action_retries_original_version_and_cross_class_permissions(lab):
    c = lab["client"](1)
    t = task(c)
    row = create(c, t, lab["classes"][0])
    body = dict(
        version=1,
        action_key="switch-key-01",
        op="set_switch",
        payload=dict(terminal_id="D", value=1),
    )
    first = data(post(c, f"/lab-sessions/{row['id']}/actions", body))
    assert first["version"] == 2
    data(
        post(
            c,
            f"/lab-sessions/{row['id']}/actions",
            dict(
                version=2,
                action_key="switch-key-02",
                op="set_switch",
                payload=dict(terminal_id="D", value=0),
            ),
        )
    )
    old = data(post(c, f"/lab-sessions/{row['id']}/actions", body))
    assert old["version"] == 2 and old["board"]["switches"]["D"] == 1
    assert "request_hash" not in dump(old)
    assert (
        post(
            c,
            f"/lab-sessions/{row['id']}/actions",
            dict(body, action_key="switch-key-03"),
        ).status_code
        == 409
    )
    assert (
        post(
            c,
            f"/lab-sessions/{row['id']}/actions",
            dict(body, payload=dict(terminal_id="D", value=0)),
        ).status_code
        == 409
    )
    for other in (2, 3, 4):
        assert (
            lab["client"](other).get(PREFIX + f"/lab-sessions/{row['id']}").status_code
            == 404
        )
    assert (
        lab["client"](0).get(PREFIX + f"/lab-sessions/{row['id']}").status_code == 200
    )
    assert (
        post(lab["client"](0), f"/lab-sessions/{row['id']}/actions", body).status_code
        == 404
    )
    assert lab["client"](5).get(PREFIX + "/lab-tasks").status_code == 403
    assert lab["app"].test_client().get(PREFIX + "/lab-tasks").status_code == 401


def test_invalid_board_spoofed_scores_and_stale_task(lab):
    c = lab["client"](1)
    t = task(c)
    row = create(c, t, lab["classes"][0])
    body = dict(
        session_id=row["id"],
        session_version=row["version"],
        task_version=t["version"],
        request_key="grade-key-01",
    )
    assert post(c, "/lab-attempts/wiring", body).status_code == 422
    for field in ("q", "passed", "score", "expected"):
        assert (
            post(c, "/lab-attempts/wiring", dict(body, **{field: True})).status_code
            == 422
        )
    with lab["factory"]() as s:
        assert s.query(LabAttempt).count() == 0
        trow = s.get(LabTask, t["id"])
        trow.version += 1
        s.commit()
    assert (
        post(
            c,
            f"/lab-sessions/{row['id']}/actions",
            dict(
                version=1,
                action_key="switch-key-01",
                op="set_switch",
                payload=dict(terminal_id="D", value=1),
            ),
        ).status_code
        == 409
    )


def test_retirement_preserves_history_but_prevents_writes(lab):
    c = lab["client"](1)
    t = task(c)
    row = create(c, t, lab["classes"][0])
    with lab["factory"]() as s:
        enrollment = s.get(Enrollment, (lab["classes"][0], lab["users"][1]))
        enrollment.active = 0
        s.commit()
    assert c.get(PREFIX + f"/lab-sessions/{row['id']}").status_code == 200
    assert (
        post(
            c,
            f"/lab-sessions/{row['id']}/actions",
            dict(
                version=1,
                action_key="switch-key-01",
                op="set_switch",
                payload=dict(terminal_id="D", value=1),
            ),
        ).status_code
        == 404
    )


def test_two_requests_one_version_cannot_both_write(lab):
    c = lab["client"](1)
    row = create(c, task(c), lab["classes"][0])

    def send(index):
        return post(
            lab["client"](1),
            f"/lab-sessions/{row['id']}/actions",
            dict(
                version=1,
                action_key=f"switch-key-{index:02}",
                op="set_switch",
                payload=dict(terminal_id="D", value=index),
            ),
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(send, [0, 1]))
    assert sorted(codes) == [200, 409]
    assert data(c.get(PREFIX + f"/lab-sessions/{row['id']}"))["version"] == 2


def test_summary_null_no_participation_and_role_guards(lab):
    path = PREFIX + f"/analytics/labs?class_id={lab['classes'][0]}"
    rows = data(lab["client"](0).get(path))["tasks"]
    assert len(rows) == 8 and all(r["pass_rate"] is None for r in rows)
    assert lab["client"](1).get(path).status_code == 403
    assert lab["client"](3).get(path).status_code == 404
