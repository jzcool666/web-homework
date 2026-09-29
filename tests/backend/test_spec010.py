"""SPEC-010 随堂测与测评统计：T-010-01 至 T-010-04 及配套边界。

时间用 `clock` 夹具冻结在 `api_assessment._now`，因为开始/截止、最终化时间戳与
统计窗口都取服务器时间。存储时间是秒级 RFC3339，因此「截止前 1 毫秒」这档边界
在实现里落到「截止前 1 秒」，报告中如实说明该精度限制。

每个用例使用自己的临时数据库。E057 的口径用例集中在文件后半部分。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import api_assessment
from app.stats_assessment import bucket_label, csv_safe, percent_of
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
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def stamp(moment: datetime) -> str:
    return moment.strftime(STAMP)


def parse(value: str) -> datetime:
    return datetime.strptime(value, STAMP).replace(tzinfo=timezone.utc)


@pytest.fixture
def clock(monkeypatch):
    state = {"now": stamp(datetime.now(timezone.utc))}
    monkeypatch.setattr(api_assessment, "_now", lambda: state["now"])
    return state


def advance(state: dict, seconds: int) -> None:
    state["now"] = stamp(parse(state["now"]) + timedelta(seconds=seconds))


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


def make_question(app, teacher, *, stem="题干", qtype="single", options=None, answer=None, point):
    options = options or [{"key": "A", "label": "正确"}, {"key": "B", "label": "错误"}]
    answer = answer or ["A"]
    response = post_as(app, teacher, "post", f"{API}/questions", {
        "type": qtype, "stem_md": stem, "options": options, "answer": answer,
        "explanation_md": f"{stem} 的解析", "difficulty": 1,
        "knowledge_ids": [point["id"]], "published": True,
    })
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


STUDENTS = [
    ("stu_a1", "20241001", "学生甲"),
    ("stu_a2", "20241002", "学生乙"),
    ("stu_a3", "20241003", "学生丙"),
    ("stu_a4", "20241004", "学生丁"),
]


@pytest.fixture
def school(upgraded_app, clock):
    """教师、两个班、甲班四名学生、章节与知识点。"""
    app = upgraded_app
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", ADMIN_PASSWORD)
    teacher_a = post_as(app, (admin, admin_csrf), "post", f"{API}/users", {
        "login_name": "teacher_aaa", "display_name": "教师甲",
        "password": DEFAULT_PASSWORD, "role": "teacher",
    }).get_json()["data"]
    teacher_b = post_as(app, (admin, admin_csrf), "post", f"{API}/users", {
        "login_name": "teacher_bbb", "display_name": "教师乙",
        "password": DEFAULT_PASSWORD, "role": "teacher",
    }).get_json()["data"]
    class_a = post_as(app, (admin, admin_csrf), "post", f"{API}/classes", {
        "name": "时序逻辑甲班", "teacher_id": teacher_a["id"],
    }).get_json()["data"]
    class_b = post_as(app, (admin, admin_csrf), "post", f"{API}/classes", {
        "name": "时序逻辑乙班", "teacher_id": teacher_b["id"],
    }).get_json()["data"]

    ta = login_as(app, "teacher_aaa")
    tb = login_as(app, "teacher_bbb")
    chapter = post_as(app, ta, "post", f"{API}/chapters", {
        "title": "时序逻辑基础", "sort_order": 0, "published": True,
    }).get_json()["data"]
    point = post_as(app, ta, "post", f"{API}/knowledge-points", {
        "chapter_id": chapter["id"], "title": "同步复位", "body_md": "复位优先",
        "source_url": None, "sort_order": 0, "published": True,
    }).get_json()["data"]

    students = {}
    for login_name, number, display in STUDENTS:
        client = app.test_client()
        csrf = get_csrf(client)
        response = register(client, csrf, login_name=login_name, student_no=number,
                            display_name=display)
        assert response.status_code == 201, response.get_data(as_text=True)
        students[login_name] = response.get_json()["data"]

    for login_name, _number, _display in STUDENTS:
        post_as(app, (admin, admin_csrf), "put", f"{API}/classes/{class_a['id']}/enrollments", {
            "student_id": students[login_name]["id"], "active": True,
        })

    actors = {name: login_as(app, name) for name, _number, _display in STUDENTS}
    return {
        "app": app,
        "clock": clock,
        "admin": (admin, admin_csrf),
        "ta": ta,
        "tb": tb,
        "class_a": class_a,
        "class_b": class_b,
        "point": point,
        "students": students,
        "actors": actors,
    }


def actor(school, name):
    return school["actors"][name]


def publish(school, questions, *, starts_offset=-60, ends_offset=600, title="随堂测", points=10):
    """建草稿并发布，返回发布后的测评。"""
    items = [{"question_id": q["id"], "points": points} for q in questions]
    draft = post_as(school["app"], school["ta"], "post", f"{API}/assessments", {
        "class_id": school["class_a"]["id"], "kind": "quiz", "title": title, "items": items,
    }).get_json()["data"]
    base = parse(school["clock"]["now"])
    response = post_as(school["app"], school["ta"], "post",
                       f"{API}/assessments/{draft['id']}/publication", {
                           "version": draft["version"],
                           "starts_at": stamp(base + timedelta(seconds=starts_offset)),
                           "ends_at": stamp(base + timedelta(seconds=ends_offset)),
                       })
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def items_of(school, assessment_id, who="ta"):
    client = school["ta"] if who == "ta" else actor(school, who)
    response = post_as(school["app"], client, "get", f"{API}/assessments/{assessment_id}")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]["items"]


def start(school, name, assessment_id):
    response = post_as(school["app"], actor(school, name), "post",
                       f"{API}/assessments/{assessment_id}/submissions", {})
    assert response.status_code in (200, 201), response.get_data(as_text=True)
    return response.get_json()["data"]


def save(school, name, submission, pairs):
    return post_as(school["app"], actor(school, name), "put",
                   f"{API}/submissions/{submission['id']}/answers", {
                       "version": submission["version"],
                       "answers": [{"item_id": item_id, "selected": selected} for item_id, selected in pairs],
                   })


def submit(school, name, submission):
    response = post_as(school["app"], actor(school, name), "post",
                       f"{API}/submissions/{submission['id']}/finalization",
                       {"version": submission["version"]})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def stats(school, *, who="ta", query=""):
    client = {"ta": school["ta"], "tb": school["tb"], "admin": school["admin"]}.get(who) or actor(school, who)
    response = post_as(school["app"], client, "get",
                       f"{API}/analytics/assessment?class_id=1{query}")
    return response


# ---- T-010-01 服务器时间截止 ----

def test_T010_01_save_one_second_before_deadline_succeeds_then_409_at_deadline(school):
    """存储时间为秒级，所以「截止前 1 毫秒」落到截止前 1 秒这一档。"""
    question = make_question(school["app"], school["ta"], point=school["point"])
    assessment = publish(school, [question], ends_offset=600)
    item = items_of(school, assessment["id"], "stu_a1")[0]
    submission = start(school, "stu_a1", assessment["id"])

    # 截止前 1 秒：保存成功
    advance(school["clock"], 599)
    ok = save(school, "stu_a1", submission, [(item["id"], ["A"])])
    assert ok.status_code == 200, ok.get_data(as_text=True)

    # 正好到达 ends_at：一律 409，且不再写入
    advance(school["clock"], 1)
    assert school["clock"]["now"] == assessment["ends_at"]
    late = save(school, "stu_a1", ok.get_json()["data"], [(item["id"], ["B"])])
    assert late.status_code == 409
    assert late.get_json()["error"]["code"] == "DEADLINE_PASSED"
    assert scalar(
        school["app"],
        "SELECT selected_json FROM submission_answers WHERE submission_id=?",
        (submission["id"],),
    ) == '["A"]'

    # 最终提交在截止时同样被拒
    final = post_as(school["app"], actor(school, "stu_a1"), "post",
                    f"{API}/submissions/{submission['id']}/finalization",
                    {"version": submission["version"] + 1})
    assert final.status_code == 409


def test_T010_01_client_cannot_forge_time(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    assessment = publish(school, [question], ends_offset=600)
    item = items_of(school, assessment["id"], "stu_a1")[0]
    submission = start(school, "stu_a1", assessment["id"])

    forged = post_as(school["app"], actor(school, "stu_a1"), "put",
                     f"{API}/submissions/{submission['id']}/answers", {
                         "version": submission["version"],
                         "answers": [{"item_id": item["id"], "selected": ["A"]}],
                         "saved_at": assessment["ends_at"],
                         "now": "2000-01-01T00:00:00Z",
                     })
    assert forged.status_code == 422
    assert forged.get_json()["error"]["details"]["unknown_fields"]

    # 伪造失败后仍是原来的注释：截止仍然按服务器时间拒绝
    advance(school["clock"], 601)
    assert save(school, "stu_a1", submission, [(item["id"], ["A"])]).status_code == 409


# ---- T-010-02 截止最终化 ----

def test_T010_02_ended_draft_is_finalized_at_ends_at_and_non_starters_stay_unsubmitted(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    assessment = publish(school, [question], ends_offset=600)
    item = items_of(school, assessment["id"], "stu_a1")[0]

    submission_a = start(school, "stu_a1", assessment["id"])
    asserted = save(school, "stu_a1", submission_a, [(item["id"], ["A"])])
    assert asserted.status_code == 200
    # 学生甲保存后断开；学生乙从未开始

    advance(school["clock"], 601)
    body = stats(school)
    assert body.status_code == 200, body.get_data(as_text=True)
    row = body.get_json()["data"]["assessments"][0]
    assert row["roster_count"] == 4
    assert row["submitted_count"] == 1

    # 甲被最终化，提交时间取 ends_at（不是这次统计访问的时间）
    a_row = scalar(
        school["app"],
        "SELECT status || '|' || submit_reason || '|' || submitted_at FROM submissions WHERE id=?",
        (submission_a["id"],),
    )
    assert a_row == f"submitted|timeout|{assessment['ends_at']}"
    assert scalar(school["app"], "SELECT score FROM submissions WHERE id=?", (submission_a["id"],)) == 10

    # 未开始的乙仍然没有提交记录
    assert scalar(
        school["app"],
        "SELECT COUNT(*) FROM submissions WHERE assessment_id=? AND student_id=?",
        (assessment["id"], school["students"]["stu_a2"]["id"]),
    ) == 0
    # 名单分母仍然是 4（包含未开始的两人）
    assert scalar(
        school["app"],
        "SELECT COUNT(*) FROM assessment_roster WHERE assessment_id=?",
        (assessment["id"],),
    ) == 4


def test_T010_02_early_close_stamps_actual_close_time(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    assessment = publish(school, [question], ends_offset=3600)
    item = items_of(school, assessment["id"], "stu_a1")[0]
    submission = start(school, "stu_a1", assessment["id"])
    save(school, "stu_a1", submission, [(item["id"], ["B"])])

    advance(school["clock"], 120)
    closed_at = school["clock"]["now"]
    closed = post_as(school["app"], school["ta"], "post",
                     f"{API}/assessments/{assessment['id']}/closure",
                     {"version": assessment["version"]})
    assert closed.status_code == 200, closed.get_data(as_text=True)
    body = closed.get_json()["data"]
    assert body["state"] == "closed"
    assert body["ends_at"] == closed_at, "提前结束时 ends_at 收缩为实际结束时间"

    assert scalar(
        school["app"],
        "SELECT status || '|' || submitted_at FROM submissions WHERE id=?",
        (submission["id"],),
    ) == f"submitted|{closed_at}"

    # 已结束后不能再开始作答
    assert post_as(school["app"], actor(school, "stu_a2"), "post",
                   f"{API}/assessments/{assessment['id']}/submissions", {}).status_code == 409


# ---- T-010-03 公开前不泄露 ----

def test_T010_03_no_answer_correct_or_score_before_release_even_after_end(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    assessment = publish(school, [question], ends_offset=600)
    item = items_of(school, assessment["id"], "stu_a1")[0]

    submission = start(school, "stu_a1", assessment["id"])
    finalized = save(school, "stu_a1", submission, [(item["id"], ["B"])])
    assert finalized.status_code == 200
    assert finalized.get_json()["data"]["score"] is None, "未公开反馈前不返回分数"

    advance(school["clock"], 601)  # 已结束但未公开反馈

    detail = post_as(school["app"], actor(school, "stu_a1"), "get",
                     f"{API}/assessments/{assessment['id']}")
    detail_body = detail.get_json()["data"]
    assert detail_body["effective_state"] == "closed"
    assert detail_body["feedback_released"] is False
    assert set(detail_body["items"][0]) == {
        "id", "question_id", "position", "points", "type", "stem_md", "options", "knowledge_ids",
    }
    assert "answer" not in str(detail_body) and "explanation_md" not in str(detail_body)

    result = post_as(school["app"], actor(school, "stu_a1"), "get",
                     f"{API}/submissions/{submission['id']}/result")
    result_body = result.get_json()["data"]
    assert result_body["feedback_available"] is False
    assert result_body["score"] is None
    assert set(result_body["items"][0]) == {"item_id", "selected"}

    # 已结束但未公开：题目仍不进入自练候选
    practice = post_as(school["app"], actor(school, "stu_a1"), "post", f"{API}/practice-sessions", {
        "knowledge_ids": [school["point"]["id"]], "count": 1,
    })
    assert practice.status_code == 422
    assert practice.get_json()["error"]["details"]["available"] == 0

    # 教师公开后学生才看到答案与解析
    released = post_as(school["app"], school["ta"], "post",
                       f"{API}/assessments/{assessment['id']}/feedback-release",
                       {"version": body_version(school, assessment["id"])})
    assert released.status_code == 200, released.get_data(as_text=True)
    after = post_as(school["app"], actor(school, "stu_a1"), "get",
                    f"{API}/submissions/{submission['id']}/result").get_json()["data"]
    assert after["feedback_available"] is True
    assert after["score"] == 0
    assert after["items"][0]["correct"] is False
    assert after["items"][0]["answer"] == ["A"]
    assert after["items"][0]["explanation_md"]


def body_version(school, assessment_id):
    response = post_as(school["app"], school["ta"], "get", f"{API}/assessments/{assessment_id}")
    return response.get_json()["data"]["version"]


def test_T010_03_teacher_sees_statistics_before_release_but_students_cannot(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    assessment = publish(school, [question], ends_offset=600)
    item = items_of(school, assessment["id"], "stu_a1")[0]
    submission = start(school, "stu_a1", assessment["id"])
    submit(school, "stu_a1", save(school, "stu_a1", submission, [(item["id"], ["A"])]).get_json()["data"])

    # 讲评前（且测评仍在进行中）教师即可看统计
    teacher_view = stats(school)
    assert teacher_view.status_code == 200, teacher_view.get_data(as_text=True)
    assert teacher_view.get_json()["data"]["items"][0]["answered_count"] == 1

    # 学生无权访问
    assert stats(school, who="stu_a1").status_code == 403
    # 其他班教师按跨班对象处理
    assert stats(school, who="tb").status_code == 404


# ---- T-010-04 统计口径 ----

def test_T010_04_submission_rate_and_item_counts(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    assessment = publish(school, [question], ends_offset=600, points=10)
    items = {name: items_of(school, assessment["id"], name) for name in ("stu_a1", "stu_a2", "stu_a3")}
    item_id = items["stu_a1"][0]["id"]

    # 甲答对；乙答错；丙提交白卷（不答）；丁没提交
    submit(school, "stu_a1", save(school, "stu_a1", start(school, "stu_a1", assessment["id"]), [(item_id, ["A"])]).get_json()["data"])
    submit(school, "stu_a2", save(school, "stu_a2", start(school, "stu_a2", assessment["id"]), [(item_id, ["B"])]).get_json()["data"])
    blank = start(school, "stu_a3", assessment["id"])
    submit(school, "stu_a3", blank)

    advance(school["clock"], 1)  # 默认窗口右开，超出同一秒后才计入 submitted_at
    body = stats(school).get_json()["data"]
    row = body["assessments"][0]
    assert row["roster_count"] == 4
    assert row["submitted_count"] == 3
    assert row["submission_rate"] == 0.75
    assert row["blank_count"] == 1, "白卷单列"
    assert row["mean_percent"] == 33.33  # (100 + 0 + 0) / 3

    item_row = body["items"][0]
    assert item_row["item_id"] == item_id
    assert item_row["answered_count"] == 3, "分母是已提交人数（含漏答）"
    assert item_row["unanswered_count"] == 1
    assert item_row["correct_count"] == 1
    assert item_row["correct_rate"] == 0.3333
    assert item_row["option_counts"] == {"A": 1, "B": 1}
    # 选项分布与漏答可对账：实答数 = 机会数 - 漏答数 = 选项计数之和（单选）
    assert item_row["answered_count"] - item_row["unanswered_count"] == sum(
        item_row["option_counts"].values()
    )


def test_T010_04_correct_rate_uses_two_of_three(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    assessment = publish(school, [question], ends_offset=600)
    item_id = items_of(school, assessment["id"], "stu_a1")[0]["id"]

    for name, choice in (("stu_a1", ["A"]), ("stu_a2", ["A"]), ("stu_a3", ["B"])):
        submission = start(school, name, assessment["id"])
        submit(school, name, save(school, name, submission, [(item_id, choice)]).get_json()["data"])

    advance(school["clock"], 1)
    item_row = stats(school).get_json()["data"]["items"][0]
    assert item_row["correct_count"] == 2
    assert item_row["correct_rate"] == 0.6667


def test_T010_04_statistics_are_anonymous_and_bucketed(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    second = make_question(school["app"], school["ta"], stem="第二题", point=school["point"])
    draft = post_as(school["app"], school["ta"], "post", f"{API}/assessments", {
        "class_id": school["class_a"]["id"], "kind": "quiz", "title": "两题各 10 分",
        "items": [{"question_id": question["id"], "points": 10}, {"question_id": second["id"], "points": 10}],
    }).get_json()["data"]
    base = parse(school["clock"]["now"])
    published = post_as(school["app"], school["ta"], "post",
                        f"{API}/assessments/{draft['id']}/publication", {
                            "version": draft["version"],
                            "starts_at": stamp(base - timedelta(seconds=60)),
                            "ends_at": stamp(base + timedelta(seconds=600)),
                        }).get_json()["data"]
    items = items_of(school, published["id"], "stu_a1")

    # 甲 20/20 = 100%、乙 10/20 = 50%、丙 0/20 = 0%
    submit(school, "stu_a1", save(school, "stu_a1", start(school, "stu_a1", published["id"]),
           [(items[0]["id"], ["A"]), (items[1]["id"], ["A"])]).get_json()["data"])
    submit(school, "stu_a2", save(school, "stu_a2", start(school, "stu_a2", published["id"]),
           [(items[0]["id"], ["A"]), (items[1]["id"], ["B"])]).get_json()["data"])
    submit(school, "stu_a3", save(school, "stu_a3", start(school, "stu_a3", published["id"]),
           [(items[0]["id"], ["B"]), (items[1]["id"], ["B"])]).get_json()["data"])

    advance(school["clock"], 1)
    body = stats(school).get_json()["data"]
    buckets = {row["range"]: row["count"] for row in body["score_buckets"]}
    assert buckets == {"0-<60": 2, "60-<70": 0, "70-<80": 0, "80-<90": 0, "90-100": 1}
    # 统计只给聚合值，不含任何学生标识
    assert "student_id" not in str(body)

    # 知识点首答：窗口内每个学生的该题首答都算一次机会
    assert body["knowledge"]
    knowledge_row = body["knowledge"][0]
    assert knowledge_row["knowledge_id"] == school["point"]["id"]
    assert knowledge_row["first_attempt_count"] >= 3


# ---- E057 窗口、格式与边界 ----

def test_T010_stats_window_rules(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    publish(school, [question], ends_offset=600)

    only_from = post_as(school["app"], school["ta"], "get",
                        f"{API}/analytics/assessment?class_id=1&from=2026-09-01T00:00:00Z")
    assert only_from.status_code == 400

    base = parse(school["clock"]["now"])
    too_long = post_as(
        school["app"], school["ta"], "get",
        f"{API}/analytics/assessment?class_id=1&from={stamp(base - timedelta(days=400))}"
        f"&to={stamp(base)}",
    )
    assert too_long.status_code == 400

    reversed_range = post_as(
        school["app"], school["ta"], "get",
        f"{API}/analytics/assessment?class_id=1&from={stamp(base)}"
        f"&to={stamp(base - timedelta(days=1))}",
    )
    assert reversed_range.status_code == 400

    missing_class = post_as(school["app"], school["ta"], "get", f"{API}/analytics/assessment")
    assert missing_class.status_code == 400

    # 默认窗口最近 30 天，覆盖刚发布的测评
    default_view = stats(school).get_json()["data"]
    assert default_view["assessments"]

    # 窗口收窄到测评结束之前时，该测评不再计入
    narrow = post_as(
        school["app"], school["ta"], "get",
        f"{API}/analytics/assessment?class_id=1&from={stamp(base - timedelta(days=5))}"
        f"&to={stamp(base - timedelta(days=1))}",
    ).get_json()["data"]
    assert narrow["assessments"] == []


def test_T010_stats_csv_export(school):
    question = make_question(school["app"], school["ta"], point=school["point"])
    assessment = publish(school, [question], ends_offset=600)
    item_id = items_of(school, assessment["id"], "stu_a1")[0]["id"]
    submit(school, "stu_a1", save(school, "stu_a1", start(school, "stu_a1", assessment["id"]),
           [(item_id, ["A"])]).get_json()["data"])

    advance(school["clock"], 1)
    response = post_as(school["app"], school["ta"], "get",
                       f"{API}/analytics/assessment?class_id=1&format=csv")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    text = response.get_data(as_text=True)
    assert text.startswith("﻿"), "CSV 带 UTF-8 BOM"
    header = text.lstrip("﻿").splitlines()[0]
    assert header.startswith("section,assessment_id,item_id")
    assert "assessment" in text and "item" in text and "score_bucket" in text


def test_T010_anonymous_and_admin_cannot_read_statistics(school):
    anonymous = school["app"].test_client()
    assert anonymous.get(f"{API}/analytics/assessment?class_id=1").status_code == 401
    assert post_as(school["app"], school["admin"], "get",
                   f"{API}/analytics/assessment?class_id=1").status_code == 403


# ---- 纯口径单测（不依赖数据库）----

def test_score_bucket_boundaries():
    assert bucket_label(0) == "0-<60"
    assert bucket_label(59.99) == "0-<60"
    assert bucket_label(60) == "60-<70"
    assert bucket_label(69.99) == "60-<70"
    assert bucket_label(70) == "70-<80"
    assert bucket_label(80) == "80-<90"
    assert bucket_label(90) == "90-100"
    assert bucket_label(100) == "90-100"
    assert bucket_label(None) is None


def test_percent_of_does_not_fake_zero():
    assert percent_of(15, 20) == 75.0
    assert percent_of(0, 20) == 0.0
    assert percent_of(5, 0) is None
    assert percent_of(None, 20) is None


def test_csv_formula_injection_is_escaped():
    assert csv_safe("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert csv_safe("+1") == "'+1"
    assert csv_safe("-1") == "'-1"
    assert csv_safe("@x") == "'@x"
    assert csv_safe("正常文本") == "正常文本"
    assert csv_safe(None) == ""
