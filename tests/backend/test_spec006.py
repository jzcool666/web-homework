"""SPEC-006 学习进度与资源统计：T-006-01 至 T-006-04 及配套边界。

数据构造分两类：
- 走真实接口的部分：学生用 E017 标记完成、用 E022 记录资源访问，覆盖权限与去重路径。
- 需要指定日期的部分：直接写 `resource_events` / `learning_progress`，因为接口按服务器
  当天写 `event_day`、按服务器当前时间写 `completed_at`，无法构造历史窗口。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import api_learning
from helpers import (
    API,
    DEFAULT_PASSWORD,
    api_call,
    create_admin,
    get_csrf,
    login,
    register,
)

ADMIN_PASSWORD = "Adm1nPass!23"


def login_as(app, login_name: str, password: str = DEFAULT_PASSWORD):
    client = app.test_client()
    csrf = get_csrf(client)
    response = login(client, csrf, login_name=login_name, password=password)
    assert response.status_code == 200, response.get_data(as_text=True)
    return client, response.get_json()["data"]["csrf_token"]


def post_as(app, actor, method, path, payload=None):
    client, token = actor
    kwargs = {"json": payload} if payload is not None else {}
    return api_call(client, method, path, csrf_token=token, **kwargs)


def execute(app, sql, params=()):
    """直接写库，用于构造指定日期的历史数据。"""
    engine = app.extensions["db_engine"]
    with engine.begin() as connection:
        return connection.exec_driver_sql(sql, params)


def scalar(app, sql, params=()):
    engine = app.extensions["db_engine"]
    with engine.connect() as connection:
        return connection.exec_driver_sql(sql, params).scalar()


def utc_day(offset_days: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def make_point(app, teacher, chapter_id, title, *, published=True):
    response = post_as(app, teacher, "post", f"{API}/knowledge-points", {
        "chapter_id": chapter_id, "title": title, "body_md": f"{title} 的说明",
        "source_url": None, "sort_order": 0, "published": published,
    })
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def make_resource(app, teacher, title, knowledge_id, *, urls=("https://example.com/a.pdf",)):
    resource = post_as(app, teacher, "post", f"{API}/resources", {
        "title": title, "category": "slides", "knowledge_id": knowledge_id, "published": True,
    }).get_json()["data"]
    versions = []
    for url in urls:
        response = post_as(app, teacher, "post", f"{API}/resources/{resource['id']}/versions", {
            "external_url": url, "note": "版本",
        })
        assert response.status_code == 201, response.get_data(as_text=True)
        versions.append(response.get_json()["data"])
    return resource, versions


@pytest.fixture
def school(upgraded_app):
    app = upgraded_app
    create_admin(app)
    admin_ctx = login_as(app, "admin_root", ADMIN_PASSWORD)

    def new_teacher(login_name, display_name):
        return post_as(app, admin_ctx, "post", f"{API}/users", {
            "login_name": login_name, "display_name": display_name,
            "password": DEFAULT_PASSWORD, "role": "teacher",
        }).get_json()["data"]

    teacher_a = new_teacher("teacher_aaa", "教师甲")
    teacher_b = new_teacher("teacher_bbb", "教师乙")
    class_a = post_as(app, admin_ctx, "post", f"{API}/classes", {
        "name": "甲班", "teacher_id": teacher_a["id"],
    }).get_json()["data"]
    class_b = post_as(app, admin_ctx, "post", f"{API}/classes", {
        "name": "乙班", "teacher_id": teacher_b["id"],
    }).get_json()["data"]

    ta = login_as(app, "teacher_aaa")
    tb = login_as(app, "teacher_bbb")

    chapter1 = post_as(app, ta, "post", f"{API}/chapters", {
        "title": "时序逻辑基础", "sort_order": 0, "published": True,
    }).get_json()["data"]
    chapter2 = post_as(app, ta, "post", f"{API}/chapters", {
        "title": "寄存器与计数器", "sort_order": 1, "published": True,
    }).get_json()["data"]

    points = [make_point(app, ta, chapter1["id"], f"知识点{i}") for i in range(1, 5)]
    draft = make_point(app, ta, chapter1["id"], "草稿知识点", published=False)
    other_point = make_point(app, ta, chapter2["id"], "寄存器知识点（草稿）", published=False)

    resource_a, versions_a = make_resource(
        app, ta, "时序课件", points[0]["id"],
        urls=("https://example.com/v1.pdf", "https://example.com/v2.pdf"),
    )
    resource_b, versions_b = make_resource(app, ta, "寄存器课件", other_point["id"])

    students = {}
    for login_name, number in [("stu_a1", "20241201"), ("stu_a2", "20241202"),
                               ("stu_a3", "20241203"), ("stu_b1", "20241211")]:
        client = app.test_client()
        csrf = get_csrf(client)
        response = register(client, csrf, login_name=login_name, student_no=number)
        assert response.status_code == 201, response.get_data(as_text=True)
        students[login_name] = response.get_json()["data"]

    for login_name, class_id in (("stu_a1", class_a["id"]), ("stu_a2", class_a["id"]),
                                 ("stu_a3", class_a["id"]), ("stu_b1", class_b["id"])):
        post_as(app, admin_ctx, "put", f"{API}/classes/{class_id}/enrollments", {
            "student_id": students[login_name]["id"], "active": True,
        })

    return {
        "app": app,
        "admin": admin_ctx,
        "ta": ta,
        "tb": tb,
        "class_a": class_a,
        "class_b": class_b,
        "chapter1": chapter1,
        "chapter2": chapter2,
        "points": points,
        "draft": draft,
        "other_point": other_point,
        "resource_a": resource_a,
        "versions_a": versions_a,
        "resource_b": resource_b,
        "versions_b": versions_b,
        "students": students,
        "sa1": login_as(app, "stu_a1"),
        "sa2": login_as(app, "stu_a2"),
        "sa3": login_as(app, "stu_a3"),
        "sb1": login_as(app, "stu_b1"),
    }


def stats(school, *, who="ta", query=""):
    client = {"ta": school["ta"], "tb": school["tb"], "admin": school["admin"]}.get(who)
    if client is None:
        client = school[who]
    return post_as(school["app"], client, "get", f"{API}/analytics/learning?class_id={school['class_a']['id']}{query}")


def student_row(body, student_id):
    return next(row for row in body["students"] if row["student_id"] == student_id)


def complete(app, actor, knowledge_id, *, completed=True):
    return post_as(app, actor, "put", f"{API}/me/learning-progress", {
        "knowledge_id": knowledge_id, "completed": completed,
    })


def record_event(app, actor, version_id, kind="open"):
    return post_as(app, actor, "post", f"{API}/resource-versions/{version_id}/events", {
        "event_kind": kind,
    })


# ---- T-006-01 完成率与草稿不计分母 ----

def test_T006_01_three_of_four_published_points_is_075(school):
    app = school["app"]
    stu1 = school["students"]["stu_a1"]["id"]

    for point in school["points"][:3]:
        response = complete(app, school["sa1"], point["id"])
        assert response.status_code == 200, response.get_data(as_text=True)

    body = stats(school).get_json()["data"]
    assert body["published_knowledge_count"] == 4, "分母只算已发布知识点，草稿不计"
    assert body["progress_basis"] == "current_completed_before_to"
    row = student_row(body, stu1)
    assert row["completed_count"] == 3
    assert row["completion_rate"] == 0.75

    # 草稿知识点即使被完成也不进入分子/分母（E017 也拒绝未发布知识点）
    rejected = complete(app, school["sa1"], school["draft"]["id"])
    assert rejected.status_code in (403, 404, 422)


def test_T006_01_other_student_counts_are_independent(school):
    app = school["app"]
    for point in school["points"][:4]:
        complete(app, school["sa1"], point["id"])
    complete(app, school["sa2"], school["points"][0]["id"])

    body = stats(school).get_json()["data"]
    assert student_row(body, school["students"]["stu_a1"]["id"])["completion_rate"] == 1.0
    assert student_row(body, school["students"]["stu_a2"]["id"])["completion_rate"] == 0.25
    assert student_row(body, school["students"]["stu_a3"]["id"])["completion_rate"] == 0.0


# ---- T-006-02 零分母与零完成 ----

def test_T006_02_zero_denominator_is_null_and_zero_completion_is_zero(school):
    body = stats(school).get_json()["data"]
    # 没有任何完成记录时，分母为 4 → 0 而不是 null
    assert body["published_knowledge_count"] == 4
    zero = student_row(body, school["students"]["stu_a1"]["id"])
    assert zero["completed_count"] == 0
    assert zero["completion_rate"] == 0.0
    assert zero["completion_rate"] is not None

    # 分母为 0：筛选到只有草稿知识点的章节
    empty = stats(school, query=f"&chapter_id={school['chapter2']['id']}").get_json()["data"]
    assert empty["published_knowledge_count"] == 0
    assert empty["students"]
    assert all(row["completion_rate"] is None for row in empty["students"])
    assert all(row["completed_count"] == 0 for row in empty["students"])


def test_T006_02_completed_after_to_is_excluded(school):
    """completed_at < to 才算：把完成时间写到 to 之后的记录不计入分子。"""
    app = school["app"]
    stu1 = school["students"]["stu_a1"]["id"]
    point = school["points"][0]["id"]
    complete(app, school["sa1"], point)

    body = stats(school).get_json()["data"]
    assert student_row(body, stu1)["completed_count"] == 1

    # 把该记录的 completed_at 改到窗口之后
    future = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    execute(app, "UPDATE learning_progress SET completed_at=? WHERE student_id=? AND knowledge_id=?",
            (future, stu1, point))
    after = stats(school).get_json()["data"]
    assert student_row(after, stu1)["completed_count"] == 0
    assert student_row(after, stu1)["completion_rate"] == 0.0


# ---- T-006-03 资源访问去重 ----

def test_T006_03_two_versions_one_student_then_second_student(school):
    app = school["app"]
    resource_id = school["resource_a"]["id"]
    v1, v2 = school["versions_a"]

    assert record_event(app, school["sa1"], v1["id"]).status_code == 200
    assert record_event(app, school["sa1"], v2["id"]).status_code == 200
    # 同人同版本同类型同日再记一次：不产生新的去重事件
    again = record_event(app, school["sa1"], v1["id"])
    assert again.status_code == 200
    assert again.get_json()["data"]["recorded"] is False

    body = stats(school).get_json()["data"]
    row = next(item for item in body["resources"] if item["resource_id"] == resource_id)
    assert row["dedup_events"] == 2, "同人访问两个版本是两个去重事件"
    assert row["unique_students"] == 1, "人数只计一次"

    assert record_event(app, school["sa2"], v1["id"]).status_code == 200
    after = stats(school).get_json()["data"]
    row2 = next(item for item in after["resources"] if item["resource_id"] == resource_id)
    assert row2["dedup_events"] == 3
    assert row2["unique_students"] == 2


def test_T006_03_download_and_open_count_as_separate_events(school):
    app = school["app"]
    v1 = school["versions_a"][0]
    assert record_event(app, school["sa1"], v1["id"], "open").status_code == 200
    assert record_event(app, school["sa1"], v1["id"], "download").status_code == 200
    body = stats(school).get_json()["data"]
    row = next(item for item in body["resources"] if item["resource_id"] == school["resource_a"]["id"])
    assert row["dedup_events"] == 2
    assert row["unique_students"] == 1


# ---- T-006-04 时间窗、章节筛选与权限 ----

def test_T006_04_utc_day_window_filters_events(school):
    app = school["app"]
    v1 = school["versions_a"][0]
    stu1 = school["students"]["stu_a1"]["id"]
    inside, before = utc_day(-2), utc_day(-10)
    execute(app, "UPDATE enrollments SET joined_at=? WHERE class_id=? AND student_id=?",
            (f"{utc_day(-11)}T00:00:00Z", school["class_a"]["id"], stu1))
    execute(app, "INSERT INTO resource_events (student_id, resource_version_id, event_kind, event_day) VALUES (?,?,?,?)",
            (stu1, v1["id"], "open", inside))
    execute(app, "INSERT INTO resource_events (student_id, resource_version_id, event_kind, event_day) VALUES (?,?,?,?)",
            (stu1, v1["id"], "download", before))

    # 默认窗口（最近 30 天）两者都覆盖
    default_body = stats(school).get_json()["data"]
    assert next(i for i in default_body["resources"] if i["resource_id"] == school["resource_a"]["id"])["dedup_events"] == 2

    # 只覆盖窗口内那一天的窗口
    window = f"&from={utc_day(-3)}T00:00:00Z&to={utc_day(-1)}T00:00:00Z"
    narrowed = stats(school, query=window).get_json()["data"]
    assert narrowed["window"]["from"] == f"{utc_day(-3)}T00:00:00Z"
    assert narrowed["window"]["to"] == f"{utc_day(-1)}T00:00:00Z"
    row = next(i for i in narrowed["resources"] if i["resource_id"] == school["resource_a"]["id"])
    assert row["dedup_events"] == 1, "窗口外的事件被排除"

    # 右开：[from,to) 不含 to 当天
    right_open = f"&from={utc_day(-2)}T00:00:00Z&to={utc_day(-2)}T00:00:00Z"
    assert stats(school, query=right_open).status_code == 400  # to 等于 from 非法

    excludes_to = f"&from={utc_day(-3)}T00:00:00Z&to={utc_day(-2)}T00:00:00Z"
    excluded = stats(school, query=excludes_to).get_json()["data"]
    assert all(row["resource_id"] != school["resource_a"]["id"] for row in excluded["resources"])


def test_T006_04_window_must_be_utc_whole_day(school):
    partial = stats(school, query=f"&from={utc_day(-3)}T05:00:00Z&to={utc_day(-1)}T00:00:00Z")
    assert partial.status_code == 422
    assert partial.get_json()["error"]["code"] == "VALIDATION_ERROR"
    assert "from" in partial.get_json()["error"]["details"]["fields"]

    only_from = stats(school, query=f"&from={utc_day(-3)}T00:00:00Z")
    assert only_from.status_code == 400

    reversed_range = stats(school, query=f"&from={utc_day(-1)}T00:00:00Z&to={utc_day(-3)}T00:00:00Z")
    assert reversed_range.status_code == 400

    too_long = stats(school, query=f"&from={utc_day(-400)}T00:00:00Z&to={utc_day(1)}T00:00:00Z")
    assert too_long.status_code == 400


def test_T006_04_default_window_ends_at_next_utc_day_midnight(school, monkeypatch):
    frozen = datetime(2026, 9, 29, 6, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(api_learning, "_now", lambda: frozen)
    body = stats(school).get_json()["data"]
    assert body["window"]["to"] == "2026-09-30T00:00:00Z", "截止到当前 UTC 日的下一日 00:00"
    assert body["window"]["from"] == "2026-08-31T00:00:00Z", "默认最近 30 个 UTC 自然日"


def test_T006_04_chapter_filter_applies_to_progress_and_resources(school):
    app = school["app"]
    v_b = school["versions_b"][0]
    complete(app, school["sa1"], school["points"][0]["id"])
    recorded = record_event(app, school["sa1"], v_b["id"])
    assert recorded.status_code == 200, recorded.get_data(as_text=True)

    chapter2 = stats(school, query=f"&chapter_id={school['chapter2']['id']}").get_json()["data"]
    assert chapter2["published_knowledge_count"] == 0, "该章节只有草稿知识点"
    assert student_row(chapter2, school["students"]["stu_a1"]["id"])["completion_rate"] is None
    # 资料按「关联知识点所属章节」筛选：资源 B 关联的是 chapter2 的草稿知识点
    assert [item["resource_id"] for item in chapter2["resources"]] == [school["resource_b"]["id"]]

    chapter1 = stats(school, query=f"&chapter_id={school['chapter1']['id']}").get_json()["data"]
    assert chapter1["published_knowledge_count"] == 4
    assert student_row(chapter1, school["students"]["stu_a1"]["id"])["completed_count"] == 1
    assert all(item["resource_id"] != school["resource_b"]["id"] for item in chapter1["resources"])


def test_T006_04_left_student_leaves_progress_but_keeps_history(school):
    app = school["app"]
    v1 = school["versions_a"][0]
    left_student = school["students"]["stu_a3"]["id"]
    complete(app, school["sa3"], school["points"][0]["id"])
    record_event(app, school["sa3"], v1["id"])

    post_as(app, school["admin"], "put", f"{API}/classes/{school['class_a']['id']}/enrollments", {
        "student_id": left_student, "active": False,
    })

    body = stats(school).get_json()["data"]
    assert all(row["student_id"] != left_student for row in body["students"]), "退班学生不计入当前进度名单"
    row = next(item for item in body["resources"] if item["resource_id"] == school["resource_a"]["id"])
    assert row["unique_students"] == 1, "退班学生的历史访问仍然保留"
    assert row["dedup_events"] == 1


def test_T006_04_old_class_excludes_events_after_student_left(school):
    app = school["app"]
    student_id = school["students"]["stu_a3"]["id"]
    version_before, version_after = school["versions_a"]
    class_id = school["class_a"]["id"]
    post_as(app, school["admin"], "put", f"{API}/classes/{class_id}/enrollments", {
        "student_id": student_id, "active": False,
    })
    execute(app, "UPDATE enrollments SET joined_at=?, left_at=? WHERE class_id=? AND student_id=?",
            (f"{utc_day(-3)}T00:00:00Z", f"{utc_day(-1)}T12:00:00Z", class_id, student_id))
    execute(app, "INSERT INTO resource_events (student_id, resource_version_id, event_kind, event_day) VALUES (?,?,?,?)",
            (student_id, version_before["id"], "open", utc_day(-2)))
    execute(app, "INSERT INTO resource_events (student_id, resource_version_id, event_kind, event_day) VALUES (?,?,?,?)",
            (student_id, version_after["id"], "open", utc_day()))

    body = stats(school).get_json()["data"]
    row = next(item for item in body["resources"] if item["resource_id"] == school["resource_a"]["id"])
    assert row["dedup_events"] == 1, "退班后其他班的访问不应计入旧班"
    assert row["unique_students"] == 1


def test_T006_04_permissions_are_class_scoped(school):
    assert stats(school, who="tb").status_code == 404, "跨班读统计按 404"
    assert stats(school, who="sa1").status_code == 403, "学生不得访问班级统计"
    assert stats(school, who="admin").status_code == 403

    anonymous = school["app"].test_client()
    assert anonymous.get(f"{API}/analytics/learning?class_id={school['class_a']['id']}").status_code == 401

    missing_class = post_as(school["app"], school["ta"], "get", f"{API}/analytics/learning")
    assert missing_class.status_code == 400

    # 跨班导出同样 404，学生导出同样 403
    assert post_as(school["app"], school["tb"], "get",
                   f"{API}/analytics/learning?class_id={school['class_a']['id']}&format=csv").status_code == 404
    assert post_as(school["app"], school["sa1"], "get",
                   f"{API}/analytics/learning?class_id={school['class_a']['id']}&format=csv").status_code == 403


# ---- JSON 与 CSV 对账 ----

def test_T006_json_and_csv_share_the_same_numbers(school):
    app = school["app"]
    v1, v2 = school["versions_a"]
    for point in school["points"][:3]:
        complete(app, school["sa1"], point["id"])
    record_event(app, school["sa1"], v1["id"])
    record_event(app, school["sa1"], v2["id"])

    json_body = stats(school).get_json()["data"]
    response = stats(school, query="&format=csv")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    text = response.get_data(as_text=True)
    assert text.startswith("﻿"), "CSV 带 UTF-8 BOM"

    lines = text.lstrip("﻿").splitlines()
    assert lines[0].startswith("section,student_id,completed_count")
    progress_lines = [line for line in lines if line.startswith("progress,")]
    resource_lines = [line for line in lines if line.startswith("resource,")]
    summary_lines = [line for line in lines if line.startswith("summary,")]
    assert len(summary_lines) == 1
    assert len(progress_lines) == len(json_body["students"])
    assert len(resource_lines) == len(json_body["resources"])

    # 逐字段对账：进度行的完成数与百分比、资源行的人数与事件数
    header = lines[0].split(",")
    def row_of(line):
        return dict(zip(header, line.split(",")))

    stu1 = student_row(json_body, school["students"]["stu_a1"]["id"])
    csv_stu1 = row_of(next(line for line in progress_lines if f",{stu1['student_id']}," in line))
    assert csv_stu1["completed_count"] == str(stu1["completed_count"])
    assert csv_stu1["completion_rate"] == str(stu1["completion_rate"])
    assert csv_stu1["published_knowledge_count"] == str(json_body["published_knowledge_count"])
    assert csv_stu1["progress_basis"] == json_body["progress_basis"]
    assert csv_stu1["window_from"] == json_body["window"]["from"]

    resource = json_body["resources"][0]
    csv_resource = row_of(next(line for line in resource_lines if f",{resource['resource_id']}," in line))
    assert csv_resource["unique_students"] == str(resource["unique_students"])
    assert csv_resource["dedup_events"] == str(resource["dedup_events"])


def test_T006_csv_escapes_formula_like_text(school):
    """CSV 只含固定标签与数字 ID；公式注入防护由共享的 csv_safe 保证。"""
    from app.stats_assessment import csv_safe

    assert csv_safe("=cmd|' /C calc'!A0").startswith("'")
    assert csv_safe("-1+1").startswith("'")
    assert csv_safe("progress").startswith("progress")

    response = stats(school, query="&format=csv")
    text = response.get_data(as_text=True).lstrip("﻿")
    assert "progress_basis" in text.splitlines()[0]
    assert "current_completed_before_to" in text


def test_T006_empty_class_csv_keeps_summary_metadata(school):
    app = school["app"]
    class_id = school["class_a"]["id"]
    for student in ("stu_a1", "stu_a2", "stu_a3"):
        post_as(app, school["admin"], "put", f"{API}/classes/{class_id}/enrollments", {
            "student_id": school["students"][student]["id"], "active": False,
        })
    payload = stats(school).get_json()["data"]
    assert payload["students"] == []
    response = stats(school, query="&format=csv")
    lines = response.get_data(as_text=True).lstrip("﻿").splitlines()
    assert len(lines) == 2
    assert lines[1].startswith("summary,")
    assert str(payload["published_knowledge_count"]) in lines[1]
    assert payload["progress_basis"] in lines[1]
