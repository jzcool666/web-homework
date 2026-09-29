"""SPEC-014 实验学习统计：T-014-01 至 T-014-04 及配套边界。

固定数据 + 独立数据库：夹具用 `tmp_path` 显式指定 DATABASE_URL 与 UPLOAD_DIR。
尝试记录通过 E050 真实提交产生（判分在服务端重算），统计只读这些记录；
窗口外的记录用 SQL 直接改写 created_at 制造，避免依赖等待时间。
"""

from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path

import pytest

from app import create_app
from helpers import (
    API,
    DEFAULT_PASSWORD,
    api_call,
    create_admin,
    get_csrf,
    login,
    register,
    scalar,
    sqlite_url,
    upgrade,
)

COUNTER_M6_FROM_4 = {"initial_q": 4, "modulus": 6}
COUNTER_M6_FROM_0 = {"initial_q": 0, "modulus": 6}


def cycles(count: int) -> list[dict]:
    return [{"op": op} for _ in range(count) for op in ("toggle_clock", "toggle_clock")]


# ---- 夹具助手 ----

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


def _register_student(app, login_name: str, student_no: str):
    client = app.test_client()
    csrf = get_csrf(client)
    response = register(client, csrf, login_name=login_name, student_no=student_no)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def _enroll(admin, admin_csrf, class_id: int, student_id: int, active: bool = True):
    return api_call(
        admin,
        "put",
        f"{API}/classes/{class_id}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student_id, "active": active},
    )


def create_knowledge(client, csrf) -> dict:
    chapter = api_call(
        client,
        "post",
        f"{API}/chapters",
        csrf_token=csrf,
        json={"title": "第五单元 计数器", "sort_order": 5, "published": True},
    ).get_json()["data"]
    return api_call(
        client,
        "post",
        f"{API}/knowledge-points",
        csrf_token=csrf,
        json={
            "chapter_id": chapter["id"],
            "title": "模 6 计数器与 5→0 回卷",
            "body_md": "模 6 计数器状态为 0000—0101。",
            "sort_order": 1,
            "published": True,
        },
    ).get_json()["data"]


def create_experiment(client, csrf, knowledge_id: int, *, title: str, config: dict, steps: int):
    response = api_call(
        client,
        "post",
        f"{API}/experiments",
        csrf_token=csrf,
        json={
            "title": title,
            "knowledge_id": knowledge_id,
            "simulator_type": "counter",
            "config": dict(config),
            "steps_md": "按提示逐拍切换时钟。",
            "input_sequence": cycles(steps),
            "published": True,
        },
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def attempt(student, experiment, predictions):
    """提交一次实验预测（每次用新的 request_key，即一次真实尝试）。"""
    client, csrf = student
    return api_call(
        client,
        "post",
        f"{API}/experiments/{experiment['id']}/attempts",
        csrf_token=csrf,
        json={
            "experiment_version": experiment["version"],
            "predictions": predictions,
            "request_key": str(uuid.uuid4()),
        },
    )


def stats(client, class_id: int, **params):
    query = "&".join(f"{key}={value}" for key, value in params.items())
    suffix = f"&{query}" if query else ""
    return client.get(f"{API}/analytics/experiment?class_id={class_id}{suffix}")


def parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))


@pytest.fixture
def lab(tmp_path: Path):
    """两教师两班：班甲(a,b) 班乙(c)，另有未入班学生 x；班甲有 2 个已发布实验。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": sqlite_url(tmp_path / "experiment_stats.sqlite"),
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

    student_a = _register_student(app, "stu_a0001", "20240001")
    student_b = _register_student(app, "stu_b0001", "20240002")
    student_c = _register_student(app, "stu_c0001", "20240003")
    outsider = _register_student(app, "stu_x0001", "20240004")
    for student in (student_a, student_b):
        assert _enroll(admin, admin_csrf, class_a["id"], student["id"]).status_code == 200
    assert _enroll(admin, admin_csrf, class_b["id"], student_c["id"]).status_code == 200

    teacher_client, teacher_csrf = login_as(app, "teacher_aaa")
    knowledge = create_knowledge(teacher_client, teacher_csrf)
    experiment_one = create_experiment(
        teacher_client,
        teacher_csrf,
        knowledge["id"],
        title="模 6 计数器：从 4 开始的四拍",
        config=COUNTER_M6_FROM_4,
        steps=4,
    )
    experiment_two = create_experiment(
        teacher_client,
        teacher_csrf,
        knowledge["id"],
        title="模 6 计数器：从 0 开始的两拍",
        config=COUNTER_M6_FROM_0,
        steps=2,
    )

    try:
        yield {
            "app": app,
            "admin": (admin, admin_csrf),
            "teacher_a": (teacher_client, teacher_csrf),
            "teacher_b": login_as(app, "teacher_bbb"),
            "student_a": login_as(app, "stu_a0001"),
            "student_b": login_as(app, "stu_b0001"),
            "student_c": login_as(app, "stu_c0001"),
            "outsider": login_as(app, "stu_x0001"),
            "class_a": class_a,
            "class_b": class_b,
            "experiment_one": experiment_one,
            "experiment_two": experiment_two,
            "ids": {
                "a": student_a["id"],
                "b": student_b["id"],
                "c": student_c["id"],
                "x": outsider["id"],
            },
        }
    finally:
        app.extensions["db_engine"].dispose()


# ---- 纯计算边界 ----

def test_summarize_experiment_stats_handles_empty_input():
    from app.stats_experiment import summarize_experiment_stats

    payload = summarize_experiment_stats(experiments=[(7, "无尝试实验")], attempt_rows=[])
    assert payload["participants"] == 0
    assert payload["passed_students"] == 0
    assert payload["attempt_count"] == 0
    assert payload["pass_rate"] is None, "无参与必须返回 null，而不是 0"
    assert payload["experiments"][0]["pass_rate"] is None


# ---- T-014-01 同一学生失败两次后通过 ----

def test_T014_01_repeated_attempts_count_once_as_participant(lab):
    experiment = lab["experiment_one"]
    student = lab["student_a"]

    assert attempt(student, experiment, [5, 6, 1, 2]).get_json()["data"]["passed"] is False
    assert attempt(student, experiment, [9, 0, 1, 2]).get_json()["data"]["passed"] is False
    assert attempt(student, experiment, [5, 0, 1, 2]).get_json()["data"]["passed"] is True

    response = stats(lab["teacher_a"][0], lab["class_a"]["id"])
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()["data"]

    assert data["participants"] == 1, "同一学生多次尝试只算一个参与者"
    assert data["passed_students"] == 1, "任一次通过即算通过者"
    assert data["attempt_count"] == 3, "尝试数不去重"
    assert data["pass_rate"] == 1.0

    row = next(item for item in data["experiments"] if item["experiment_id"] == experiment["id"])
    assert row["participants"] == 1
    assert row["passed_students"] == 1
    assert row["attempt_count"] == 3
    assert row["pass_rate"] == 1.0


# ---- T-014-02 第二名学生只失败一次 ----

def test_T014_02_second_student_changes_pass_rate(lab):
    experiment = lab["experiment_one"]
    attempt(lab["student_a"], experiment, [5, 6, 1, 2])
    attempt(lab["student_a"], experiment, [9, 0, 1, 2])
    attempt(lab["student_a"], experiment, [5, 0, 1, 2])
    attempt(lab["student_b"], experiment, [0, 0, 0, 0])

    data = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]

    assert data["participants"] == 2
    assert data["passed_students"] == 1
    assert data["attempt_count"] == 4
    assert data["pass_rate"] == 0.5

    row = next(item for item in data["experiments"] if item["experiment_id"] == experiment["id"])
    assert (row["participants"], row["passed_students"], row["attempt_count"]) == (2, 1, 4)
    assert row["pass_rate"] == 0.5


# ---- T-014-03 空数据、窗口与实验过滤 ----

def test_T014_03_no_participation_returns_null(lab):
    data = stats(
        lab["teacher_a"][0],
        lab["class_a"]["id"],
        **{"from": "2020-01-01T00:00:00Z", "to": "2020-02-01T00:00:00Z"},
    ).get_json()["data"]

    assert data["participants"] == 0
    assert data["passed_students"] == 0
    assert data["attempt_count"] == 0
    assert data["pass_rate"] is None
    assert all(row["pass_rate"] is None for row in data["experiments"])
    assert data["published_count"] == 2, "已发布实验数不受参与情况影响"


def test_T014_03_attempts_outside_window_are_excluded(lab):
    experiment = lab["experiment_one"]
    attempt(lab["student_a"], experiment, [5, 0, 1, 2])  # 窗口内
    attempt(lab["student_b"], experiment, [0, 0, 0, 0])  # 之后改到窗口外

    # 把第二条改到 2020 年，制造窗口外记录
    with lab["app"].extensions["db_engine"].begin() as connection:
        connection.exec_driver_sql(
            "UPDATE experiment_attempts SET created_at = '2020-06-01T00:00:00Z' "
            "WHERE student_id = ?",
            (lab["ids"]["b"],),
        )

    data = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]
    assert data["participants"] == 1, "窗口外尝试不计入参与人数"
    assert data["attempt_count"] == 1

    row = next(item for item in data["experiments"] if item["experiment_id"] == experiment["id"])
    assert row["participants"] == 1
    assert row["attempt_count"] == 1


def test_T014_03_experiment_filter_narrows_scope(lab):
    one, two = lab["experiment_one"], lab["experiment_two"]
    attempt(lab["student_a"], one, [5, 0, 1, 2])
    attempt(lab["student_b"], two, [1, 2])

    filtered = stats(
        lab["teacher_a"][0], lab["class_a"]["id"], experiment_id=two["id"]
    ).get_json()["data"]

    assert filtered["published_count"] == 1
    assert [row["experiment_id"] for row in filtered["experiments"]] == [two["id"]]
    assert filtered["participants"] == 1
    assert filtered["passed_students"] == 1
    assert filtered["attempt_count"] == 1

    only_one = stats(
        lab["teacher_a"][0], lab["class_a"]["id"], experiment_id=one["id"]
    ).get_json()["data"]
    assert only_one["participants"] == 1
    assert only_one["attempt_count"] == 1


def test_T014_03_window_parameters_are_validated(lab):
    client = lab["teacher_a"][0]
    class_id = lab["class_a"]["id"]

    half = client.get(
        f"{API}/analytics/experiment?class_id={class_id}&from=2026-09-01T00:00:00Z"
    )
    assert half.status_code == 400, "from 与 to 必须同时给出"

    inverted = client.get(
        f"{API}/analytics/experiment?class_id={class_id}"
        "&from=2026-09-02T00:00:00Z&to=2026-09-01T00:00:00Z"
    )
    assert inverted.status_code == 400

    too_long = client.get(
        f"{API}/analytics/experiment?class_id={class_id}"
        "&from=2024-01-01T00:00:00Z&to=2026-01-01T00:00:00Z"
    )
    assert too_long.status_code == 400, "窗口最长 366 天"

    missing_class = client.get(f"{API}/analytics/experiment")
    assert missing_class.status_code == 400

    bad_format = client.get(f"{API}/analytics/experiment?class_id={class_id}&format=xlsx")
    assert bad_format.status_code == 400


# ---- T-014-04 CSV 对账与跨班拒绝 ----

def test_T014_04_csv_matches_json(lab):
    experiment = lab["experiment_one"]
    attempt(lab["student_a"], experiment, [5, 6, 1, 2])
    attempt(lab["student_a"], experiment, [5, 0, 1, 2])
    attempt(lab["student_b"], experiment, [0, 0, 0, 0])

    client = lab["teacher_a"][0]
    class_id = lab["class_a"]["id"]
    payload = stats(client, class_id).get_json()["data"]

    response = client.get(f"{API}/analytics/experiment?class_id={class_id}&format=csv")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in response.headers["Content-Disposition"]

    rows = parse_csv(response.get_data(as_text=True))
    summary = next(row for row in rows if row["section"] == "summary")
    assert int(summary["participants"]) == payload["participants"]
    assert int(summary["passed_students"]) == payload["passed_students"]
    assert int(summary["attempt_count"]) == payload["attempt_count"]
    assert int(summary["published_count"]) == payload["published_count"]
    assert float(summary["pass_rate"]) == payload["pass_rate"]

    detail = {int(row["experiment_id"]): row for row in rows if row["section"] == "experiment"}
    for block in payload["experiments"]:
        row = detail[block["experiment_id"]]
        assert int(row["participants"]) == block["participants"]
        assert int(row["passed_students"]) == block["passed_students"]
        assert int(row["attempt_count"]) == block["attempt_count"]
        assert row["experiment_title"] == block["title"]
        if block["pass_rate"] is None:
            assert row["pass_rate"] == ""
        else:
            assert float(row["pass_rate"]) == block["pass_rate"]


def test_T014_04_other_teacher_cannot_read_or_export(lab):
    teacher_b = lab["teacher_b"][0]
    class_a_id = lab["class_a"]["id"]

    assert stats(teacher_b, class_a_id).status_code == 404
    assert (
        teacher_b.get(f"{API}/analytics/experiment?class_id={class_a_id}&format=csv").status_code
        == 404
    )
    assert scalar(lab["app"], "SELECT COUNT(*) FROM classes WHERE id = ?", (class_a_id,)) == 1, (
        "班级确实存在，404 表示无权而非不存在"
    )

    # 本人班级可以读取
    assert stats(teacher_b, lab["class_b"]["id"]).status_code == 200


def test_T014_04_non_teacher_roles_are_rejected(lab):
    class_a_id = lab["class_a"]["id"]
    assert stats(lab["student_a"][0], class_a_id).status_code == 403
    assert stats(lab["admin"][0], class_a_id).status_code == 403
    anonymous = lab["app"].test_client()
    assert stats(anonymous, class_a_id).status_code == 401


# ---- 名单口径 ----

def test_only_current_roster_is_counted(lab):
    """班乙学生的尝试不进入班甲统计；退班后其历史尝试也不再计入。"""
    experiment = lab["experiment_one"]
    attempt(lab["student_a"], experiment, [5, 0, 1, 2])
    attempt(lab["student_c"], experiment, [5, 0, 1, 2])  # 班乙学生

    teacher_a = lab["teacher_a"][0]
    class_a_id = lab["class_a"]["id"]

    data = stats(teacher_a, class_a_id).get_json()["data"]
    assert data["participants"] == 1, "班乙学生的尝试不计入班甲"

    data_b = stats(lab["teacher_b"][0], lab["class_b"]["id"]).get_json()["data"]
    assert data_b["participants"] == 1, "同一实验在班乙单独统计"

    # 学生 a 退班后，其历史尝试不再计入班甲当前名单
    admin, admin_csrf = lab["admin"]
    assert _enroll(admin, admin_csrf, class_a_id, lab["ids"]["a"], False).status_code == 200
    after = stats(teacher_a, class_a_id).get_json()["data"]
    assert after["participants"] == 0
    assert after["pass_rate"] is None


def test_total_passed_counts_students_passing_any_experiment(lab):
    """顶层通过人数是「至少通过一个实验」，不能写成全部实验都通过。"""
    one, two = lab["experiment_one"], lab["experiment_two"]
    attempt(lab["student_a"], one, [5, 0, 1, 2])  # 通过实验一
    attempt(lab["student_b"], one, [0, 0, 0, 0])  # 实验一失败
    attempt(lab["student_b"], two, [1, 2])  # 实验二通过

    data = stats(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()["data"]

    assert data["participants"] == 2
    assert data["passed_students"] == 2, "两人各通过了至少一个实验"
    assert data["attempt_count"] == 3
    rows = {row["experiment_id"]: row for row in data["experiments"]}
    assert rows[one["id"]]["passed_students"] == 1
    assert rows[two["id"]]["passed_students"] == 1
    # 实验一有两人参与、一人通过；实验二只有一人参与且通过
    assert rows[one["id"]]["participants"] == 2
    assert rows[one["id"]]["pass_rate"] == 0.5
    assert rows[two["id"]]["participants"] == 1
    assert rows[two["id"]]["pass_rate"] == 1.0
