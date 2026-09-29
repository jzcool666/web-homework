"""SPEC-002 考勤与请假：T-002-01 至 T-002-04 及配套边界。

时间用 `clock` 夹具冻结在 `api_attendance.now_utc_dt`，因为签到窗口、迟到判定和
结算都必须以服务器时间为准；冻结后可以精确命中 opens_at/late_at/closes_at 这些
边界时刻，而不是靠真实时钟碰运气。每个用例使用自己的临时数据库。
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from app import api_attendance
from helpers import (
    API,
    DEFAULT_PASSWORD,
    api_call,
    create_admin,
    get_csrf,
    login,
    register,
    scalar,
)

ADMIN_PASSWORD = "Adm1nPass!23"
BASE = datetime(2026, 9, 29, 2, 0, 0, tzinfo=timezone.utc)


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def at(state: dict, offset_minutes: float, *, seconds: int = 0) -> None:
    """把冻结时钟设为 BASE + 偏移；负数表示 opens_at 之前。"""
    state["now"] = BASE + timedelta(minutes=offset_minutes, seconds=seconds)


@pytest.fixture(autouse=True)
def _clear_code_rate_limits():
    api_attendance._code_failures.clear()
    yield
    api_attendance._code_failures.clear()


@pytest.fixture
def clock(monkeypatch):
    """冻结服务器时间；state["now"] 由用例调整。"""
    state = {"now": BASE}
    monkeypatch.setattr(api_attendance, "now_utc_dt", lambda: state["now"])
    return state


# ---- 夹具 ----

def login_as(app, login_name: str, password: str = DEFAULT_PASSWORD):
    client = app.test_client()
    csrf = get_csrf(client)
    response = login(client, csrf, login_name=login_name, password=password)
    assert response.status_code == 200, response.get_data(as_text=True)
    return client, response.get_json()["data"]["csrf_token"]


def create_teacher(app, admin_client, admin_csrf, login_name: str) -> dict:
    response = api_call(
        admin_client,
        "post",
        f"{API}/users",
        csrf_token=admin_csrf,
        json={
            "login_name": login_name,
            "display_name": login_name,
            "password": DEFAULT_PASSWORD,
            "role": "teacher",
        },
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def register_student(app, login_name: str, student_no: str) -> dict:
    client = app.test_client()
    csrf = get_csrf(client)
    response = register(client, csrf, login_name=login_name, student_no=student_no)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def create_class(app, admin_client, admin_csrf, name: str, teacher_id: int) -> dict:
    response = api_call(
        admin_client,
        "post",
        f"{API}/classes",
        csrf_token=admin_csrf,
        json={"name": name, "teacher_id": teacher_id},
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def enroll(app, admin_client, admin_csrf, class_id: int, student_id: int) -> None:
    response = api_call(
        admin_client,
        "put",
        f"{API}/classes/{class_id}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student_id, "active": True},
    )
    assert response.status_code == 200, response.get_data(as_text=True)


@pytest.fixture
def school(upgraded_app, clock):
    """一管理员、两教师、两班；甲班两学生、乙班一学生。"""
    app = upgraded_app
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", ADMIN_PASSWORD)
    teacher_a = create_teacher(app, admin, admin_csrf, "teacher_aaa")
    teacher_b = create_teacher(app, admin, admin_csrf, "teacher_bbb")
    class_a = create_class(app, admin, admin_csrf, "时序逻辑甲班", teacher_a["id"])
    class_b = create_class(app, admin, admin_csrf, "时序逻辑乙班", teacher_b["id"])

    students = {
        "stu_a1": register_student(app, "stu_a1", "20240101"),
        "stu_a2": register_student(app, "stu_a2", "20240102"),
        "stu_b1": register_student(app, "stu_b1", "20240201"),
    }
    enroll(app, admin, admin_csrf, class_a["id"], students["stu_a1"]["id"])
    enroll(app, admin, admin_csrf, class_a["id"], students["stu_a2"]["id"])
    enroll(app, admin, admin_csrf, class_b["id"], students["stu_b1"]["id"])

    teacher_a_client, teacher_a_csrf = login_as(app, "teacher_aaa")
    teacher_b_client, teacher_b_csrf = login_as(app, "teacher_bbb")
    student_a1_client, student_a1_csrf = login_as(app, "stu_a1")
    student_a2_client, student_a2_csrf = login_as(app, "stu_a2")
    student_b1_client, student_b1_csrf = login_as(app, "stu_b1")

    return {
        "app": app,
        "clock": clock,
        "admin_client": admin,
        "admin_csrf": admin_csrf,
        "teacher_a": teacher_a,
        "teacher_b": teacher_b,
        "class_a": class_a,
        "class_b": class_b,
        "students": students,
        "ta": teacher_a_client,
        "ta_csrf": teacher_a_csrf,
        "tb": teacher_b_client,
        "tb_csrf": teacher_b_csrf,
        "sa1": student_a1_client,
        "sa1_csrf": student_a1_csrf,
        "sa2": student_a2_client,
        "sa2_csrf": student_a2_csrf,
        "sb1": student_b1_client,
        "sb1_csrf": student_b1_csrf,
    }


def open_task(school, *, opens=0, late=5, closes=30, class_key="class_a", title="第3次课签到"):
    """以 BASE 为基准创建签到任务，返回含明文 code 的创建响应。"""
    response = api_call(
        school["ta"],
        "post",
        f"{API}/attendance-tasks",
        csrf_token=school["ta_csrf"],
        json={
            "class_id": school[class_key]["id"],
            "title": title,
            "opens_at": stamp(BASE + timedelta(minutes=opens)),
            "late_at": stamp(BASE + timedelta(minutes=late)),
            "closes_at": stamp(BASE + timedelta(minutes=closes)),
        },
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def sign_in(school, client_key="sa1", task_id=None, code=None):
    return api_call(
        school[client_key],
        "post",
        f"{API}/attendance-tasks/{task_id}/sign-ins",
        csrf_token=school[f"{client_key}_csrf"],
        json={"code": code},
    )


def records_of(school, task_id, client_key="ta"):
    response = api_call(
        school[client_key], "get", f"{API}/attendance-tasks/{task_id}/records?page_size=100"
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def record_for(school, task_id, student_id):
    return next(r for r in records_of(school, task_id) if r["student_id"] == student_id)


# ---- T-002-01 窗口与服务器时间 ----

def test_T002_01_sign_in_at_opens_at_is_present(school):
    task = open_task(school)
    at(school["clock"], 0)
    response = sign_in(school, task_id=task["id"], code=task["code"])
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()["data"]
    assert body["status"] == "present"
    assert body["signed_at"] == stamp(BASE)


def test_T002_01_sign_in_before_late_at_is_present(school):
    task = open_task(school)
    at(school["clock"], 4, seconds=59)
    body = sign_in(school, task_id=task["id"], code=task["code"]).get_json()["data"]
    assert body["status"] == "present"


def test_T002_01_sign_in_at_late_at_is_late(school):
    task = open_task(school)
    at(school["clock"], 5)
    body = sign_in(school, task_id=task["id"], code=task["code"]).get_json()["data"]
    assert body["status"] == "late"
    assert body["signed_at"] == stamp(BASE + timedelta(minutes=5))


def test_T002_01_sign_in_at_closes_at_is_rejected(school):
    task = open_task(school)
    at(school["clock"], 30)
    response = sign_in(school, task_id=task["id"], code=task["code"])
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DEADLINE_PASSED"
    # 直接查库：读取接口会触发结算，这里要确认的是「没有产生签到」而不是结算后的状态
    assert scalar(
        school["app"],
        "SELECT status FROM attendance_records WHERE task_id=? AND student_id=?",
        (task["id"], school["students"]["stu_a1"]["id"]),
    ) == "pending"
    assert scalar(
        school["app"],
        "SELECT COUNT(*) FROM attendance_records WHERE task_id=? AND signed_at IS NOT NULL",
        (task["id"],),
    ) == 0


def test_T002_01_sign_in_before_opens_at_is_rejected(school):
    task = open_task(school)
    at(school["clock"], -1)
    response = sign_in(school, task_id=task["id"], code=task["code"])
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DEADLINE_PASSED"


def test_T002_01_client_cannot_submit_time(school):
    """签到请求不接受时间字段，判定只取服务器时间。"""
    task = open_task(school)
    at(school["clock"], 1)
    response = api_call(
        school["sa1"],
        "post",
        f"{API}/attendance-tasks/{task['id']}/sign-ins",
        csrf_token=school["sa1_csrf"],
        json={"code": task["code"], "signed_at": stamp(BASE)},
    )
    assert response.status_code == 422
    assert "signed_at" in response.get_json()["error"]["details"]["unknown_fields"]


# ---- T-002-02 并发签到与名单 ----

def test_T002_02_repeat_sign_in_returns_original_record(school):
    task = open_task(school)
    at(school["clock"], 1)
    first = sign_in(school, task_id=task["id"], code=task["code"]).get_json()["data"]
    at(school["clock"], 20)
    second = sign_in(school, task_id=task["id"], code=task["code"]).get_json()["data"]
    assert second["id"] == first["id"]
    assert second["status"] == "present"
    assert second["signed_at"] == first["signed_at"] == stamp(BASE + timedelta(minutes=1))


def test_T002_02_concurrent_sign_ins_keep_single_record(school):
    task = open_task(school)
    at(school["clock"], 1)
    app = school["app"]
    sid = school["sa1"].get_cookie("sid").value
    barrier = threading.Barrier(2)
    responses = []

    def attempt():
        client = app.test_client()
        client.set_cookie("sid", sid)
        barrier.wait(timeout=10)
        responses.append(
            client.post(
                f"{API}/attendance-tasks/{task['id']}/sign-ins",
                headers={"X-CSRF-Token": school["sa1_csrf"]},
                json={"code": task["code"]},
            )
        )

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert [r.status_code for r in responses] == [200, 200], [
        r.get_data(as_text=True) for r in responses
    ]
    record_ids = {r.get_json()["data"]["id"] for r in responses}
    assert len(record_ids) == 1

    stu_a1 = school["students"]["stu_a1"]["id"]
    assert (
        scalar(
            app,
            "SELECT COUNT(*) FROM attendance_records WHERE task_id=? AND student_id=?",
            (task["id"], stu_a1),
        )
        == 1
    )
    assert scalar(app, "SELECT status FROM attendance_records WHERE task_id=? AND student_id=?",
                  (task["id"], stu_a1)) == "present"


def test_T002_02_student_outside_roster_gets_404(school):
    task = open_task(school)
    at(school["clock"], 1)
    response = sign_in(school, "sb1", task_id=task["id"], code=task["code"])
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_T002_02_roster_copied_as_pending_on_publish(school):
    task = open_task(school)
    student_ids = {
        school["students"]["stu_a1"]["id"],
        school["students"]["stu_a2"]["id"],
    }
    rows = records_of(school, task["id"])
    assert {r["student_id"] for r in rows} == student_ids
    assert all(r["status"] == "pending" and r["signed_at"] is None for r in rows)
    # 甲班的名单不含乙班学生
    assert school["students"]["stu_b1"]["id"] not in {r["student_id"] for r in rows}


# ---- T-002-03 结算 ----

def test_T002_03_settlement_is_idempotent(school):
    task = open_task(school)
    at(school["clock"], 1)
    sign_in(school, "sa1", task_id=task["id"], code=task["code"])
    at(school["clock"], 31)

    first = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/settlements",
        csrf_token=school["ta_csrf"], json={},
    )
    assert first.status_code == 200, first.get_data(as_text=True)
    at(school["clock"], 40)
    second = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/settlements",
        csrf_token=school["ta_csrf"], json={},
    )
    assert second.status_code == 200
    assert first.get_json()["data"] == second.get_json()["data"]
    assert first.get_json()["data"]["counts"] == {"present": 1, "late": 0, "leave": 0, "absent": 1}


def test_T002_03_settlement_before_close_is_rejected(school):
    task = open_task(school)
    at(school["clock"], 10)
    response = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/settlements",
        csrf_token=school["ta_csrf"], json={},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DEADLINE_PASSED"
    assert scalar(school["app"], "SELECT settled_at FROM attendance_tasks WHERE id=?", (task["id"],)) is None


def test_T002_03_read_settles_ended_task_and_keeps_signed_and_leave(school):
    """已签到与已请假不被覆盖；读取触发的结算与显式结算结果一致。"""
    task = open_task(school)
    at(school["clock"], 1)
    sign_in(school, "sa1", task_id=task["id"], code=task["code"])

    # 学生乙提前请假，教师在其后（任务已结束）批准
    at(school["clock"], 2)
    apply_response = api_call(
        school["sa2"], "post", f"{API}/leave-requests",
        csrf_token=school["sa2_csrf"], json={"task_id": task["id"], "reason": "发热就医"},
    )
    assert apply_response.status_code == 201, apply_response.get_data(as_text=True)
    leave = apply_response.get_json()["data"]

    at(school["clock"], 31)
    approve = api_call(
        school["ta"], "patch", f"{API}/leave-requests/{leave['id']}",
        csrf_token=school["ta_csrf"], json={"version": leave["version"], "status": "approved"},
    )
    assert approve.status_code == 200, approve.get_data(as_text=True)

    # 先查询一次：读取触发结束任务结算
    rows = {r["student_id"]: r["status"] for r in records_of(school, task["id"])}
    assert rows[school["students"]["stu_a1"]["id"]] == "present"
    assert rows[school["students"]["stu_a2"]["id"]] == "leave"

    settle = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/settlements",
        csrf_token=school["ta_csrf"], json={},
    )
    assert settle.get_json()["data"]["counts"] == {
        "present": 1, "late": 0, "leave": 1, "absent": 0,
    }
    assert {r["student_id"]: r["status"] for r in records_of(school, task["id"])} == rows


def test_T002_03_unsettled_ended_task_still_shows_pending(school):
    """无访问时不结算：未结算的 pending 不显示为缺勤（直接查库核对原始状态）。"""
    task = open_task(school)
    at(school["clock"], 31)
    assert scalar(
        school["app"],
        "SELECT COUNT(*) FROM attendance_records WHERE task_id=? AND status='pending'",
        (task["id"],),
    ) == 2
    assert scalar(
        school["app"], "SELECT settled_at FROM attendance_tasks WHERE id=?", (task["id"],)
    ) is None


def test_T002_03_late_sign_in_counted_as_late(school):
    task = open_task(school)
    at(school["clock"], 6)
    sign_in(school, "sa1", task_id=task["id"], code=task["code"])
    at(school["clock"], 31)
    settle = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/settlements",
        csrf_token=school["ta_csrf"], json={},
    )
    assert settle.get_json()["data"]["counts"]["late"] == 1


# ---- T-002-04 请假审批 ----

def test_T002_04_approve_after_deadline_turns_absent_into_leave(school):
    task = open_task(school)
    at(school["clock"], 2)
    leave = api_call(
        school["sa1"], "post", f"{API}/leave-requests",
        csrf_token=school["sa1_csrf"], json={"task_id": task["id"], "reason": "校外竞赛"},
    ).get_json()["data"]

    at(school["clock"], 31)
    # 先结算：该学生从 pending 变 absent
    settle = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/settlements",
        csrf_token=school["ta_csrf"], json={},
    )
    assert settle.get_json()["data"]["counts"]["absent"] == 2

    approve = api_call(
        school["ta"], "patch", f"{API}/leave-requests/{leave['id']}",
        csrf_token=school["ta_csrf"],
        json={"version": leave["version"], "status": "approved", "review_note": "已核实"},
    )
    assert approve.status_code == 200, approve.get_data(as_text=True)
    body = approve.get_json()["data"]
    assert body["status"] == "approved"
    assert body["review_note"] == "已核实"
    assert body["reviewed_at"] is not None
    assert body["version"] == leave["version"] + 1

    assert record_for(school, task["id"], school["students"]["stu_a1"]["id"])["status"] == "leave"
    after = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/settlements",
        csrf_token=school["ta_csrf"], json={},
    )
    assert after.get_json()["data"]["counts"] == {"present": 0, "late": 0, "leave": 1, "absent": 1}


def test_T002_04_approve_signed_in_student_is_409(school):
    task = open_task(school)
    at(school["clock"], 1)
    leave = api_call(
        school["sa1"], "post", f"{API}/leave-requests",
        csrf_token=school["sa1_csrf"], json={"task_id": task["id"], "reason": "先请后到"},
    ).get_json()["data"]
    # 申请之后又完成了签到
    sign_in(school, "sa1", task_id=task["id"], code=task["code"])

    at(school["clock"], 31)
    approve = api_call(
        school["ta"], "patch", f"{API}/leave-requests/{leave['id']}",
        csrf_token=school["ta_csrf"], json={"version": leave["version"], "status": "approved"},
    )
    assert approve.status_code == 409
    assert approve.get_json()["error"]["code"] == "STATE_CONFLICT"
    assert record_for(school, task["id"], school["students"]["stu_a1"]["id"])["status"] == "present"


def test_T002_04_approved_leave_blocks_sign_in(school):
    task = open_task(school)
    at(school["clock"], 1)
    leave = api_call(
        school["sa1"], "post", f"{API}/leave-requests",
        csrf_token=school["sa1_csrf"], json={"task_id": task["id"], "reason": "病假"},
    ).get_json()["data"]
    api_call(
        school["ta"], "patch", f"{API}/leave-requests/{leave['id']}",
        csrf_token=school["ta_csrf"], json={"version": leave["version"], "status": "approved"},
    )
    at(school["clock"], 2)
    response = sign_in(school, "sa1", task_id=task["id"], code=task["code"])
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "STATE_CONFLICT"


def test_T002_04_leave_request_after_close_is_rejected(school):
    task = open_task(school)
    at(school["clock"], 30)
    response = api_call(
        school["sa1"], "post", f"{API}/leave-requests",
        csrf_token=school["sa1_csrf"], json={"task_id": task["id"], "reason": "迟到申请"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DEADLINE_PASSED"


def test_T002_04_duplicate_leave_request_is_409(school):
    task = open_task(school)
    at(school["clock"], 1)
    payload = {"task_id": task["id"], "reason": "第一次申请"}
    first = api_call(
        school["sa1"], "post", f"{API}/leave-requests",
        csrf_token=school["sa1_csrf"], json=payload,
    )
    assert first.status_code == 201
    again = api_call(
        school["sa1"], "post", f"{API}/leave-requests",
        csrf_token=school["sa1_csrf"], json=payload,
    )
    assert again.status_code == 409
    assert again.get_json()["error"]["code"] == "DUPLICATE"


def test_T002_04_review_twice_and_reject_keeps_record(school):
    task = open_task(school)
    at(school["clock"], 1)
    leave = api_call(
        school["sa1"], "post", f"{API}/leave-requests",
        csrf_token=school["sa1_csrf"], json={"task_id": task["id"], "reason": "事假"},
    ).get_json()["data"]
    rejected = api_call(
        school["ta"], "patch", f"{API}/leave-requests/{leave['id']}",
        csrf_token=school["ta_csrf"], json={"version": leave["version"], "status": "rejected"},
    )
    assert rejected.status_code == 200
    assert record_for(school, task["id"], school["students"]["stu_a1"]["id"])["status"] == "pending"

    again = api_call(
        school["ta"], "patch", f"{API}/leave-requests/{leave['id']}",
        csrf_token=school["ta_csrf"],
        json={"version": rejected.get_json()["data"]["version"], "status": "approved"},
    )
    assert again.status_code == 409
    assert again.get_json()["error"]["code"] == "STATE_CONFLICT"


def test_T002_04_stale_version_is_409(school):
    task = open_task(school)
    at(school["clock"], 1)
    leave = api_call(
        school["sa1"], "post", f"{API}/leave-requests",
        csrf_token=school["sa1_csrf"], json={"task_id": task["id"], "reason": "事假"},
    ).get_json()["data"]
    response = api_call(
        school["ta"], "patch", f"{API}/leave-requests/{leave['id']}",
        csrf_token=school["ta_csrf"],
        json={"version": leave["version"] + 5, "status": "approved"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "VERSION_CONFLICT"


# ---- 签到码：散列、重置与限流 ----

def test_code_is_hashed_and_never_returned_by_listing(school):
    task = open_task(school)
    assert len(task["code"]) == 6 and task["code"].isdigit()

    stored = scalar(
        school["app"], "SELECT code_hash FROM attendance_tasks WHERE id=?", (task["id"],)
    )
    assert stored != task["code"] and task["code"] not in stored
    assert stored == api_attendance.hash_code(task["id"], task["code"])

    listed = api_call(
        school["ta"], "get", f"{API}/attendance-tasks?class_id={school['class_a']['id']}"
    ).get_json()["data"]
    assert all("code" not in item and "code_hash" not in item for item in listed)


def test_reset_invalidates_old_code(school):
    task = open_task(school)
    at(school["clock"], 1)
    response = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/code-resets",
        csrf_token=school["ta_csrf"], json={"version": task["version"]},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    reset = response.get_json()["data"]
    assert reset["code"] != task["code"]
    assert reset["version"] == task["version"] + 1

    old = sign_in(school, "sa1", task_id=task["id"], code=task["code"])
    assert old.status_code == 422
    assert old.get_json()["error"]["code"] == "VALIDATION_ERROR"

    fresh = sign_in(school, "sa2", task_id=task["id"], code=reset["code"])
    assert fresh.status_code == 200
    assert fresh.get_json()["data"]["status"] == "present"


def test_reset_uses_version_and_rejects_stale(school):
    task = open_task(school)
    at(school["clock"], 1)
    stale = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/code-resets",
        csrf_token=school["ta_csrf"], json={"version": task["version"] + 1},
    )
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "VERSION_CONFLICT"


def test_reset_after_close_is_409(school):
    task = open_task(school)
    at(school["clock"], 30)
    response = api_call(
        school["ta"], "post", f"{API}/attendance-tasks/{task['id']}/code-resets",
        csrf_token=school["ta_csrf"], json={"version": task["version"]},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "DEADLINE_PASSED"


def test_wrong_code_five_times_then_rate_limited(school):
    task = open_task(school)
    at(school["clock"], 1)
    for _ in range(api_attendance.CODE_FAIL_LIMIT):
        response = sign_in(school, "sa1", task_id=task["id"], code="000000")
        assert response.status_code == 422, response.get_data(as_text=True)

    limited = sign_in(school, "sa1", task_id=task["id"], code=task["code"])
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    # 限流按「同人同任务」，不影响同班另一名学生
    assert sign_in(school, "sa2", task_id=task["id"], code=task["code"]).status_code == 200


def test_successful_sign_in_clears_failure_counter(school):
    task = open_task(school)
    at(school["clock"], 1)
    for _ in range(api_attendance.CODE_FAIL_LIMIT - 1):
        sign_in(school, "sa1", task_id=task["id"], code="000000")
    assert sign_in(school, "sa1", task_id=task["id"], code=task["code"]).status_code == 200
    for _ in range(api_attendance.CODE_FAIL_LIMIT - 1):
        assert sign_in(school, "sa1", task_id=task["id"], code="000000").status_code == 422


# ---- 权限、校验与隔离 ----

def test_teacher_cannot_reach_other_teachers_task(school):
    task = open_task(school)
    at(school["clock"], 31)
    for method, path, payload in (
        ("get", f"{API}/attendance-tasks/{task['id']}/records", None),
        ("post", f"{API}/attendance-tasks/{task['id']}/settlements", {}),
        ("post", f"{API}/attendance-tasks/{task['id']}/code-resets", {"version": 1}),
    ):
        kwargs = {"json": payload} if payload is not None else {}
        response = api_call(
            school["tb"], method, path, csrf_token=school["tb_csrf"], **kwargs
        )
        assert response.status_code == 404, f"{path} -> {response.status_code}"
        assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_student_and_teacher_see_own_scope_only(school):
    task = open_task(school)
    at(school["clock"], 1)
    sign_in(school, "sa1", task_id=task["id"], code=task["code"])

    mine = records_of(school, task["id"], "sa1")
    assert [r["student_id"] for r in mine] == [school["students"]["stu_a1"]["id"]]

    assert len(records_of(school, task["id"], "ta")) == 2
    # 教师能认出学生（联表读取字段），否则名单无法核对
    assert all(r["student_display_name"] for r in records_of(school, task["id"], "ta"))

    # 乙班学生读不到甲班任务
    other = api_call(
        school["sb1"], "get", f"{API}/attendance-tasks/{task['id']}/records"
    )
    assert other.status_code == 404
    tasks = api_call(
        school["sb1"], "get", f"{API}/attendance-tasks?class_id={school['class_a']['id']}"
    )
    assert tasks.status_code == 404


def test_admin_is_refused_classroom_endpoints(school):
    response = api_call(
        school["admin_client"], "get", f"{API}/attendance-tasks?class_id={school['class_a']['id']}"
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "FORBIDDEN"


def test_anonymous_is_401_and_missing_csrf_is_403(school):
    task = open_task(school)
    anonymous = school["app"].test_client()
    assert anonymous.get(f"{API}/attendance-tasks?class_id={school['class_a']['id']}").status_code == 401

    at(school["clock"], 1)
    no_csrf = school["sa1"].post(
        f"{API}/attendance-tasks/{task['id']}/sign-ins", json={"code": task["code"]}
    )
    assert no_csrf.status_code == 403
    assert no_csrf.get_json()["error"]["code"] == "CSRF_FAILED"


def test_create_task_validates_window_and_fields(school):
    bad_window = api_call(
        school["ta"], "post", f"{API}/attendance-tasks",
        csrf_token=school["ta_csrf"],
        json={
            "class_id": school["class_a"]["id"],
            "title": "窗口倒置",
            "opens_at": stamp(BASE + timedelta(minutes=10)),
            "late_at": stamp(BASE + timedelta(minutes=5)),
            "closes_at": stamp(BASE + timedelta(minutes=30)),
        },
    )
    assert bad_window.status_code == 422
    assert "late_at" in bad_window.get_json()["error"]["details"]["fields"]

    bad_time = api_call(
        school["ta"], "post", f"{API}/attendance-tasks",
        csrf_token=school["ta_csrf"],
        json={
            "class_id": school["class_a"]["id"],
            "title": "时间格式",
            "opens_at": "2026-09-29 02:00:00",
            "late_at": stamp(BASE + timedelta(minutes=5)),
            "closes_at": stamp(BASE + timedelta(minutes=30)),
        },
    )
    assert bad_time.status_code == 422

    unknown = api_call(
        school["ta"], "post", f"{API}/attendance-tasks",
        csrf_token=school["ta_csrf"],
        json={
            "class_id": school["class_a"]["id"],
            "title": "多余字段",
            "opens_at": stamp(BASE),
            "late_at": stamp(BASE + timedelta(minutes=5)),
            "closes_at": stamp(BASE + timedelta(minutes=30)),
            "code": "123456",
        },
    )
    assert unknown.status_code == 422
    assert "code" in unknown.get_json()["error"]["details"]["unknown_fields"]


def test_teacher_cannot_open_task_for_other_teachers_class(school):
    response = api_call(
        school["ta"], "post", f"{API}/attendance-tasks",
        csrf_token=school["ta_csrf"],
        json={
            "class_id": school["class_b"]["id"],
            "title": "越权任务",
            "opens_at": stamp(BASE),
            "late_at": stamp(BASE + timedelta(minutes=5)),
            "closes_at": stamp(BASE + timedelta(minutes=30)),
        },
    )
    assert response.status_code == 404


def test_leave_list_is_scoped_and_filterable(school):
    task = open_task(school)
    at(school["clock"], 1)
    api_call(
        school["sa1"], "post", f"{API}/leave-requests",
        csrf_token=school["sa1_csrf"], json={"task_id": task["id"], "reason": "事假"},
    )

    teacher_view = api_call(
        school["ta"], "get",
        f"{API}/leave-requests?task_id={task['id']}&status=pending",
    )
    assert teacher_view.status_code == 200
    rows = teacher_view.get_json()["data"]
    assert len(rows) == 1
    assert rows[0]["student_no"] == "20240101"

    # 乙班教师看不到甲班的请假
    assert api_call(
        school["tb"], "get", f"{API}/leave-requests?task_id={task['id']}"
    ).get_json()["data"] == []

    # 另一名学生看不到别人的申请
    assert api_call(
        school["sa2"], "get", f"{API}/leave-requests?task_id={task['id']}"
    ).get_json()["data"] == []

    bad_status = api_call(school["ta"], "get", f"{API}/leave-requests?status=signed")
    assert bad_status.status_code == 400
