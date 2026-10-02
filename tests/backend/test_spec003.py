"""SPEC-003 出勤与风险因素统计：T-003-01 至 T-003-04 及配套边界。

固定种子数据 + 独立测试库：账号/班级/入班关系走真实接口，考勤任务、考勤记录、
测评与提交按场景直接写入固定值，使出勤率与相关系数可以精确断言；另有一条用例
专门验证「先结算已结束任务」走的是真实结算路径。
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import create_app
from app.models import Enrollment, SchoolClass, User
from app.models_assessment import Assessment, Submission
from app.models_attendance import AttendanceRecord, AttendanceTask
from helpers import (
    API,
    DEFAULT_PASSWORD,
    api_call,
    create_admin,
    get_csrf,
    login,
    register,
    sqlite_url,
    upgrade,
)

WINDOW_FROM = "2026-09-01T00:00:00Z"
WINDOW_TO = "2026-10-01T00:00:00Z"
WINDOW = {"from": WINDOW_FROM, "to": WINDOW_TO}
SUBMITTED_AT = "2026-09-20T02:00:00Z"

STATUSES = ("present", "late", "leave", "absent")


# ---- 账号与班级（走真实接口）----

def login_as(app, login_name: str, password: str = DEFAULT_PASSWORD):
    client = app.test_client()
    csrf = get_csrf(client)
    response = login(client, csrf, login_name=login_name, password=password)
    assert response.status_code == 200, response.get_data(as_text=True)
    return client, response.get_json()["data"]["csrf_token"]


def _create_teacher(app, admin, admin_csrf, login_name: str):
    response = api_call(
        admin,
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


def _create_class(app, admin, admin_csrf, name: str, teacher_id: int):
    response = api_call(
        admin,
        "post",
        f"{API}/classes",
        csrf_token=admin_csrf,
        json={"name": name, "teacher_id": teacher_id},
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def _register_student(app, login_name: str, student_no: str, display_name: str | None = None):
    client = app.test_client()
    csrf = get_csrf(client)
    payload = {"login_name": login_name, "student_no": student_no}
    if display_name is not None:
        payload["display_name"] = display_name
    response = register(client, csrf, **payload)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def _enroll(admin, admin_csrf, class_id: int, student_id: int):
    response = api_call(
        admin,
        "put",
        f"{API}/classes/{class_id}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student_id, "active": True},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


# ---- 固定种子（考勤与测评）----

def session_of(app):
    return app.extensions["db_session"]()


def seed_task(
    app,
    *,
    class_id: int,
    owner_id: int,
    opens_at: str,
    statuses: dict[int, str],
    settled: bool = True,
    closes_at: str | None = None,
):
    """按 student_id → status 写入一条考勤任务及其记录。

    默认 closes_at 取 opens_at + 10 分钟：表约束要求 late_at < closes_at。
    """
    session = session_of(app)
    if closes_at is None:
        opened = datetime.strptime(opens_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        closes_at = (opened + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    task = AttendanceTask(
        class_id=class_id,
        title=f"考勤 {opens_at}",
        opens_at=opens_at,
        late_at=opens_at,
        closes_at=closes_at,
        code_hash="seed-only",
        settled_at=closes_at if settled else None,
        owner_id=owner_id,
    )
    session.add(task)
    session.flush()
    for student_id, status in statuses.items():
        session.add(
            AttendanceRecord(task_id=task.id, student_id=student_id, status=status)
        )
    session.commit()
    return task.id


def seed_scores(app, *, class_id: int, owner_id: int, scores: dict[int, int], total: int = 100):
    """一次已结束的非 practice 测评，按 student_id → 得分写入已提交记录。"""
    session = session_of(app)
    assessment = Assessment(
        class_id=class_id,
        owner_id=owner_id,
        kind="quiz",
        title="随堂测（固定样本）",
        state="closed",
        starts_at="2026-09-20T01:00:00Z",
        ends_at="2026-09-20T02:30:00Z",
        total_score=total,
    )
    session.add(assessment)
    session.flush()
    for student_id, score in scores.items():
        session.add(
            Submission(
                assessment_id=assessment.id,
                student_id=student_id,
                status="submitted",
                started_at=SUBMITTED_AT,
                submitted_at=SUBMITTED_AT,
                score=score,
            )
        )
    session.commit()
    return assessment.id


def stats(client, class_id: int, **params):
    query = "".join(f"&{key}={value}" for key, value in {**WINDOW, **params}.items())
    return client.get(f"{API}/analytics/attendance?class_id={class_id}{query}")


def parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))


@pytest.fixture
def lab(tmp_path: Path):
    """教师甲带一个班（5 名在册学生）+ 教师乙带另一个班。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": sqlite_url(tmp_path / "attendance_stats.sqlite"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
        },
    )
    upgrade(app)
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", "Adm1nPass!23")

    teacher_a = _create_teacher(app, admin, admin_csrf, "teacher_aaa")
    teacher_b = _create_teacher(app, admin, admin_csrf, "teacher_bbb")
    class_a = _create_class(app, admin, admin_csrf, "软件工程示例班", teacher_a["id"])
    class_b = _create_class(app, admin, admin_csrf, "网络工程示例班", teacher_b["id"])

    students = []
    for index in range(1, 6):
        students.append(
            _register_student(app, f"stu_{index:04d}", f"20240{index:03d}")
        )
    for student in students:
        _enroll(admin, admin_csrf, class_a["id"], student["id"])
    outsider = _register_student(app, "stu_9000", "20249900")

    try:
        yield {
            "app": app,
            "admin": (admin, admin_csrf),
            "teacher_a": login_as(app, "teacher_aaa"),
            "teacher_b": login_as(app, "teacher_bbb"),
            "class_a": class_a,
            "class_b": class_b,
            "students": students,
            "ids": [student["id"] for student in students],
            "teacher_id": teacher_a["id"],
            "outsider_id": outsider["id"],
        }
    finally:
        app.extensions["db_engine"].dispose()


# ---- T-003-01 出勤率 ----

def test_T003_01_attendance_rate_excludes_leave(lab):
    app, ids = lab["app"], lab["ids"]
    seed_task(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        opens_at="2026-09-10T01:00:00Z",
        statuses={
            ids[0]: "present",
            ids[1]: "present",
            ids[2]: "late",
            ids[3]: "leave",
            ids[4]: "absent",
        },
    )

    response = stats(lab["teacher_a"][0], lab["class_a"]["id"])
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()["data"]

    assert data["settled_tasks"] == 1
    assert data["counts"] == {"present": 2, "late": 1, "leave": 1, "absent": 1}
    assert data["attendance_rate"] == 0.75, "请假从分母排除：(2+1)/(2+1+1)"

    per_student = {row["student_id"]: row for row in data["students"]}
    assert per_student[ids[3]]["attendance_rate"] is None, "只有请假的学生没有可算出勤率"
    assert per_student[ids[4]]["attendance_rate"] == 0.0
    assert per_student[ids[0]]["attendance_rate"] == 1.0
    # 教师需要能认出学生（SPEC-002 已有先例）
    assert per_student[ids[0]]["student_no"] == "20240001"
    assert per_student[ids[0]]["display_name"] == "学生"


# ---- T-003-02 空数据 ----

def test_T003_02_all_leave_returns_null(lab):
    app, ids = lab["app"], lab["ids"]
    seed_task(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        opens_at="2026-09-10T01:00:00Z",
        statuses={student_id: "leave" for student_id in ids},
    )

    data = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]
    assert data["counts"] == {"present": 0, "late": 0, "leave": 5, "absent": 0}
    assert data["attendance_rate"] is None, "分母为零必须返回 null，不能显示 0%"
    assert all(row["attendance_rate"] is None for row in data["students"])


def test_T003_02_no_settled_task_in_window_returns_null(lab):
    app, ids = lab["app"], lab["ids"]
    # 窗口内只有一条「进行中」的任务：未结算，不进分母
    seed_task(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        opens_at="2026-09-10T01:00:00Z",
        closes_at="2099-01-01T00:00:00Z",
        statuses={student_id: "present" for student_id in ids},
        settled=False,
    )

    data = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]
    assert data["settled_tasks"] == 0
    assert data["attendance_rate"] is None
    assert data["students"] == []

    # 窗口外（早于 from）的已结算任务同样不计入
    seed_task(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        opens_at="2026-01-05T01:00:00Z",
        statuses={student_id: "present" for student_id in ids},
    )
    outside = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]
    assert outside["settled_tasks"] == 0
    assert outside["attendance_rate"] is None


def test_ended_pending_records_are_settled_before_counting(lab):
    """窗口内已结束但尚未结算的任务：统计前先结算，pending 变 absent 并计入。"""
    app, ids = lab["app"], lab["ids"]
    task_id = seed_task(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        opens_at="2026-09-10T01:00:00Z",
        closes_at="2026-09-10T01:10:00Z",
        statuses={student_id: "pending" for student_id in ids},
        settled=False,
    )

    data = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]
    assert data["settled_tasks"] == 1
    assert data["counts"]["absent"] == 5, "未签到的 pending 在结算后计为缺勤"
    assert data["attendance_rate"] == 0.0

    session = session_of(app)
    task = session.get(AttendanceTask, task_id)
    assert task.settled_at is not None
    statuses = {
        row.status
        for row in session.query(AttendanceRecord)
        .filter(AttendanceRecord.task_id == task_id)
        .all()
    }
    assert statuses == {"absent"}


# ---- T-003-03 相关系数 ----

def test_T003_03_five_aligned_samples_give_one(lab):
    """5 名学生的出勤率与测评均分完全同向 → Pearson ≈ 1。"""
    app, ids = lab["app"], lab["ids"]
    # 第 j 名学生出勤前 j+1 次任务、缺勤其余 → 出勤率 (j+1)/5
    for index, opens in enumerate(
        ["2026-09-10T01:00:00Z", "2026-09-11T01:00:00Z", "2026-09-12T01:00:00Z",
         "2026-09-13T01:00:00Z", "2026-09-14T01:00:00Z"]
    ):
        seed_task(
            app,
            class_id=lab["class_a"]["id"],
            owner_id=lab["teacher_id"],
            opens_at=opens,
            statuses={
                student_id: ("present" if position >= index else "absent")
                for position, student_id in enumerate(ids)
            },
        )
    seed_scores(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        scores={student_id: 40 + 10 * position for position, student_id in enumerate(ids)},
    )

    data = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]
    rates = {row["student_id"]: row["attendance_rate"] for row in data["students"]}
    assert [rates[student_id] for student_id in ids] == [0.2, 0.4, 0.6, 0.8, 1.0]

    correlation = data["correlation"]
    assert correlation["n"] == 5
    assert correlation["reason"] is None
    assert correlation["coefficient"] == 1.0


def test_T003_03_fewer_than_five_samples_returns_null_with_reason(lab):
    app, ids = lab["app"], lab["ids"]
    for index, opens in enumerate(["2026-09-10T01:00:00Z", "2026-09-11T01:00:00Z"]):
        seed_task(
            app,
            class_id=lab["class_a"]["id"],
            owner_id=lab["teacher_id"],
            opens_at=opens,
            statuses={
                student_id: ("present" if position >= index else "absent")
                for position, student_id in enumerate(ids)
            },
        )
    # 只有 4 名学生有成绩 → 共同样本 n = 4
    seed_scores(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        scores={student_id: 50 + 10 * position for position, student_id in enumerate(ids[:4])},
    )

    correlation = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]["correlation"]
    assert correlation["coefficient"] is None
    assert correlation["n"] == 4
    assert "4" in correlation["reason"]


def test_T003_03_constant_column_returns_null_with_reason(lab):
    app, ids = lab["app"], lab["ids"]
    # 所有人每次都出勤 → 出勤率恒为 1，至少一列恒定
    for opens in ["2026-09-10T01:00:00Z", "2026-09-11T01:00:00Z"]:
        seed_task(
            app,
            class_id=lab["class_a"]["id"],
            owner_id=lab["teacher_id"],
            opens_at=opens,
            statuses={student_id: "present" for student_id in ids},
        )
    seed_scores(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        scores={student_id: 40 + 10 * position for position, student_id in enumerate(ids)},
    )

    correlation = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]["correlation"]
    assert correlation["coefficient"] is None
    assert correlation["n"] == 5
    assert "恒定" in correlation["reason"]


def test_practice_assessments_are_excluded_from_scores(lab):
    """practice 不计入成绩列：混入会破坏完全同向的 1.0 相关。"""
    app, ids = lab["app"], lab["ids"]
    for index, opens in enumerate(
        ["2026-09-10T01:00:00Z", "2026-09-11T01:00:00Z", "2026-09-12T01:00:00Z",
         "2026-09-13T01:00:00Z", "2026-09-14T01:00:00Z"]
    ):
        seed_task(
            app,
            class_id=lab["class_a"]["id"],
            owner_id=lab["teacher_id"],
            opens_at=opens,
            statuses={
                student_id: ("present" if position >= index else "absent")
                for position, student_id in enumerate(ids)
            },
        )
    seed_scores(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        scores={student_id: 40 + 10 * position for position, student_id in enumerate(ids)},
    )
    # 一条 class_id 为空的自练：若被算进成绩，第 1 名学生的均分会从 40 变成 20，
    # 相关系数就不再是 1.0
    session = session_of(app)
    practice = Assessment(
        class_id=None,
        owner_id=ids[0],
        kind="practice",
        title="自练",
        state="closed",
        total_score=100,
    )
    session.add(practice)
    session.flush()
    session.add(
        Submission(
            assessment_id=practice.id,
            student_id=ids[0],
            status="submitted",
            started_at=SUBMITTED_AT,
            submitted_at=SUBMITTED_AT,
            score=0,
        )
    )
    session.commit()

    correlation = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]["correlation"]
    assert correlation["n"] == 5
    assert correlation["coefficient"] == 1.0, "practice 不应进入成绩均值"


# ---- T-003-04 权限与 CSV ----

def test_T003_04_cross_class_access_is_rejected(lab):
    app = lab["app"]
    class_a_id = lab["class_a"]["id"]

    assert stats(lab["teacher_b"][0], class_a_id).status_code == 404
    assert (
        lab["teacher_b"][0]
        .get(f"{API}/analytics/attendance?class_id={class_a_id}&format=csv")
        .status_code
        == 404
    )
    assert stats(lab["teacher_a"][0], lab["class_b"]["id"]).status_code == 404
    assert stats(lab["teacher_a"][0], class_a_id).status_code == 200
    # 班级确实存在：404 表示无权而不是不存在
    assert (
        app.extensions["db_engine"]
        .connect()
        .exec_driver_sql("SELECT COUNT(*) FROM classes WHERE id = ?", (class_a_id,))
        .scalar()
        == 1
    )

    student_client, _ = login_as(app, "stu_0001")
    assert stats(student_client, class_a_id).status_code == 403
    assert stats(lab["admin"][0], class_a_id).status_code == 403
    assert stats(app.test_client(), class_a_id).status_code == 401


def test_T003_04_csv_matches_json_and_escapes_formulas(lab):
    app = lab["app"]
    # 用带公式前缀的姓名注册一名学生，验证导出转义
    risky = _register_student(app, "stu_formula", "20240999", display_name="=SUM(A1:A9)")
    _enroll(lab["admin"][0], lab["admin"][1], lab["class_a"]["id"], risky["id"])
    ids = [*lab["ids"], risky["id"]]
    seed_task(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        opens_at="2026-09-10T01:00:00Z",
        statuses={
            ids[0]: "present",
            ids[1]: "present",
            ids[2]: "late",
            ids[3]: "leave",
            ids[4]: "absent",
            ids[5]: "absent",
        },
    )

    client = lab["teacher_a"][0]
    class_id = lab["class_a"]["id"]
    payload = stats(client, class_id).get_json()["data"]

    response = client.get(
        f"{API}/analytics/attendance?class_id={class_id}"
        f"&from={WINDOW_FROM}&to={WINDOW_TO}&format=csv"
    )
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in response.headers["Content-Disposition"]

    rows = parse_csv(response.get_data(as_text=True))
    summary = next(row for row in rows if row["section"] == "summary")
    for status in STATUSES:
        assert int(summary[status]) == payload["counts"][status]
        assert int(summary[status]) == sum(
            row["counts"][status] for row in payload["students"]
        )
    assert int(summary["settled_tasks"]) == payload["settled_tasks"]
    assert float(summary["attendance_rate"]) == payload["attendance_rate"]
    assert summary["window_from"] == WINDOW_FROM
    assert summary["window_to"] == WINDOW_TO

    student_rows = {int(row["student_id"]): row for row in rows if row["section"] == "student"}
    assert len(student_rows) == len(payload["students"])
    for block in payload["students"]:
        row = student_rows[block["student_id"]]
        for status in STATUSES:
            assert int(row[status]) == block["counts"][status]
        if block["attendance_rate"] is None:
            assert row["attendance_rate"] == ""
        else:
            assert float(row["attendance_rate"]) == block["attendance_rate"]

    # 公式注入防护：以 = 开头的姓名在 CSV 里被加上安全前缀
    assert student_rows[risky["id"]]["display_name"] == "'=SUM(A1:A9)"
    assert "=SUM(A1:A9)" not in response.get_data(as_text=True).replace(
        "'=SUM(A1:A9)", ""
    )

    correlation_row = next(row for row in rows if row["section"] == "correlation")
    assert correlation_row["coefficient"] == "" or float(
        correlation_row["coefficient"]
    ) == payload["correlation"]["coefficient"]
    assert int(correlation_row["n"]) == payload["correlation"]["n"]


def test_invalid_parameters_are_rejected(lab):
    client = lab["teacher_a"][0]
    class_id = lab["class_a"]["id"]

    assert client.get(f"{API}/analytics/attendance").status_code == 400
    assert (
        client.get(f"{API}/analytics/attendance?class_id={class_id}&from={WINDOW_FROM}").status_code
        == 400
    ), "from 与 to 必须同时给出"
    assert (
        client.get(
            f"{API}/analytics/attendance?class_id={class_id}"
            "&from=2026-10-01T00:00:00Z&to=2026-09-01T00:00:00Z"
        ).status_code
        == 400
    )
    assert (
        client.get(
            f"{API}/analytics/attendance?class_id={class_id}"
            "&from=2024-01-01T00:00:00Z&to=2026-01-01T00:00:00Z"
        ).status_code
        == 400
    ), "窗口最长 366 天"
    assert (
        client.get(
            f"{API}/analytics/attendance?class_id={class_id}&from=2026-09-01&to={WINDOW_TO}"
        ).status_code
        == 422
    ), "时间必须带 Z"
    assert (
        client.get(f"{API}/analytics/attendance?class_id={class_id}&format=xlsx").status_code
        == 400
    )
