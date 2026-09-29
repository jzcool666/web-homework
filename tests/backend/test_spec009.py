"""SPEC-009 题库练习与错题：T-009-01 至 T-009-04 及配套边界。

时间用 `clock` 夹具冻结在 `api_assessment._now`，因为开始/截止、24 小时自练期限
和最终化都取服务器时间；冻结后可以精确命中窗口边界。每个用例独立临时数据库。

跨模块待补测（Issue #6「跨模块待补测」）：#4 的 T-001-02 要求「教师猜测其他班学生
答案 ID 同样拒绝」，本文件用 test_other_teacher_cannot_read_result 补测并回填证据。
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from app import api_assessment
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
    """冻结服务器时间；用 advance() 推进。"""
    state = {"now": stamp(datetime.now(timezone.utc))}
    monkeypatch.setattr(api_assessment, "_now", lambda: state["now"])
    return state


def advance(state: dict, minutes: int) -> None:
    state["now"] = stamp(parse(state["now"]) + timedelta(minutes=minutes))


# ---- 夹具 ----

def login_as(app, login_name: str, password: str = DEFAULT_PASSWORD):
    client = app.test_client()
    csrf = get_csrf(client)
    response = login(client, csrf, login_name=login_name, password=password)
    assert response.status_code == 200, response.get_data(as_text=True)
    return client, response.get_json()["data"]["csrf_token"]


def post_as(app, actor, method, path, payload=None, csrf=None):
    client, token = actor
    kwargs = {"json": payload} if payload is not None else {}
    return api_call(client, method, path, csrf_token=csrf or token, **kwargs)


CREATE_QUESTION_FIELDS = ("type", "stem_md", "options", "answer", "explanation_md", "difficulty", "knowledge_ids", "published")


def make_question(app, teacher, *, stem="Q", qtype="single", options=None, answer=None,
                  difficulty=1, knowledge_ids=None, published=True):
    options = options or [{"key": "A", "label": "正确"}, {"key": "B", "label": "错误"}]
    answer = answer or ["A"]
    response = post_as(
        app,
        teacher,
        "post",
        f"{API}/questions",
        {
            "type": qtype,
            "stem_md": stem,
            "options": options,
            "answer": answer,
            "explanation_md": f"{stem} 的解析",
            "difficulty": difficulty,
            "knowledge_ids": knowledge_ids or [],
            "published": published,
        },
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


@pytest.fixture
def school(upgraded_app, clock):
    """管理员、两位教师、两个班、知识点，以及可用的题目工厂。"""
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
    point2 = post_as(app, ta, "post", f"{API}/knowledge-points", {
        "chapter_id": chapter["id"], "title": "异步复位", "body_md": "时钟无关",
        "source_url": None, "sort_order": 1, "published": True,
    }).get_json()["data"]

    students = {}
    for index, (login_name, number) in enumerate(
        [("stu_a1", "20240901"), ("stu_a2", "20240902"), ("stu_b1", "20240911")], start=1
    ):
        client = app.test_client()
        csrf = get_csrf(client)
        response = register(client, csrf, login_name=login_name, student_no=number)
        assert response.status_code == 201, response.get_data(as_text=True)
        students[login_name] = response.get_json()["data"]
        # 注册后直接登录，避免再走一次匿名会话
        students[login_name + "_actor"] = login_as(app, login_name)

    for login_name, class_id in (("stu_a1", class_a["id"]), ("stu_a2", class_a["id"]), ("stu_b1", class_b["id"])):
        post_as(app, (admin, admin_csrf), "put", f"{API}/classes/{class_id}/enrollments", {
            "student_id": students[login_name]["id"], "active": True,
        })

    return {
        "app": app,
        "clock": clock,
        "admin": (admin, admin_csrf),
        "ta": ta,
        "tb": tb,
        "teacher_a": teacher_a,
        "teacher_b": teacher_b,
        "class_a": class_a,
        "class_b": class_b,
        "point": point,
        "point2": point2,
        "students": students,
        "sa1": students["stu_a1_actor"],
        "sa2": students["stu_a2_actor"],
        "sb1": students["stu_b1_actor"],
    }


def student_id(school, key="stu_a1") -> int:
    return school["students"][key]["id"]


# ---- 题目工厂：三种题型 ----

def single_question(school, **kwargs):
    return make_question(school["app"], school["ta"], qtype="single",
                         options=[{"key": "A", "label": "1"}, {"key": "B", "label": "0"}],
                         answer=["A"], knowledge_ids=[school["point"]["id"]], **kwargs)


def multiple_question(school, **kwargs):
    return make_question(school["app"], school["ta"], qtype="multiple",
                         options=[{"key": "A", "label": "1"}, {"key": "B", "label": "2"},
                                  {"key": "C", "label": "3"}],
                         answer=["A", "B"], knowledge_ids=[school["point"]["id"]], **kwargs)


def boolean_question(school, **kwargs):
    return make_question(school["app"], school["ta"], qtype="boolean",
                         options=[{"key": "true", "label": "正确"}, {"key": "false", "label": "错误"}],
                         answer=["true"], knowledge_ids=[school["point2"]["id"]], **kwargs)


def publish_class_assessment(school, questions, *, minutes_ahead=60, title="随堂小测"):
    """建草稿 → 发布，返回发布后的测评。"""
    items = [{"question_id": q["id"], "points": 10} for q in questions]
    draft = post_as(school["app"], school["ta"], "post", f"{API}/assessments", {
        "class_id": school["class_a"]["id"], "kind": "quiz", "title": title, "items": items,
    }).get_json()["data"]
    starts = parse(school["clock"]["now"])
    response = post_as(school["app"], school["ta"], "post",
                       f"{API}/assessments/{draft['id']}/publication", {
                           "version": draft["version"],
                           "starts_at": stamp(starts - timedelta(minutes=1)),
                           "ends_at": stamp(starts + timedelta(minutes=minutes_ahead)),
                       })
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def start_and_answer(school, actor, assessment_id, pairs, *, submit=True):
    """开始作答 → 保存答案 → 最终化；返回最终化响应。"""
    submission = post_as(school["app"], actor, "post",
                         f"{API}/assessments/{assessment_id}/submissions", {}).get_json()["data"]
    saved = post_as(school["app"], actor, "put", f"{API}/submissions/{submission['id']}/answers", {
        "version": submission["version"],
        "answers": [{"item_id": item_id, "selected": selected} for item_id, selected in pairs],
    })
    assert saved.status_code == 200, saved.get_data(as_text=True)
    if not submit:
        return saved.get_json()["data"]
    final = post_as(school["app"], actor, "post",
                    f"{API}/submissions/{submission['id']}/finalization",
                    {"version": saved.get_json()["data"]["version"]})
    assert final.status_code == 200, final.get_data(as_text=True)
    return final.get_json()["data"]


def items_of(school, assessment_id, actor=None):
    actor = actor or school["ta"]
    response = post_as(school["app"], actor, "get", f"{API}/assessments/{assessment_id}")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]["items"]


def release_after_end(school, assessment_id, *, minutes=61):
    """推进时钟越过结束时间并公开反馈，返回公开后的测评。

    班级测评在公开反馈前不返回分数与答案，因此读成绩的用例都要先走这一步。
    """
    advance(school["clock"], minutes)
    current = api_call(school["ta"][0], "get", f"{API}/assessments/{assessment_id}").get_json()["data"]
    response = post_as(school["app"], school["ta"], "post",
                       f"{API}/assessments/{assessment_id}/feedback-release",
                       {"version": current["version"]})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def result_of(school, actor, submission_id):
    response = api_call(actor[0], "get", f"{API}/submissions/{submission_id}/result")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


# ---- T-009-01 评分 ----

def test_T009_01_single_correct_scores_full_points(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])])
    # 反馈未公开前不返回分数（与 E046 的裁剪一致）
    assert submission["score"] is None

    release_after_end(school, assessment["id"])
    body = result_of(school, school["sa1"], submission["id"])
    assert body["feedback_available"] is True
    assert body["score"] == 10
    assert body["items"][0]["correct"] is True
    assert body["items"][0]["awarded_points"] == 10
    assert body["items"][0]["answer"] == ["A"]


def test_T009_01_single_wrong_and_empty_score_zero(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]

    wrong = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["B"])])
    empty = start_and_answer(school, school["sa2"], assessment["id"], [(item["id"], [])])
    release_after_end(school, assessment["id"])

    assert result_of(school, school["sa1"], wrong["id"])["score"] == 0
    assert result_of(school, school["sa2"], empty["id"])["score"] == 0


def test_T009_01_multiple_subset_extra_and_exact(school):
    question = multiple_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]

    # 少选（只有 A）→ 0 分；多选（A、B、C 全选，多了 C）→ 0 分
    subset = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])])
    extra = start_and_answer(school, school["sa2"], assessment["id"], [(item["id"], ["A", "B", "C"])])
    release_after_end(school, assessment["id"])

    assert result_of(school, school["sa1"], subset["id"])["score"] == 0
    assert result_of(school, school["sa2"], extra["id"])["score"] == 0


def test_T009_01_multiple_exact_match_scores_full(school):
    question = multiple_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    # 顺序不同不影响集合判等
    submission = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["B", "A"])])
    release_after_end(school, assessment["id"])
    assert result_of(school, school["sa1"], submission["id"])["score"] == 10


def test_T009_01_boolean_correct(school):
    question = boolean_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["true"])])
    release_after_end(school, assessment["id"])
    assert result_of(school, school["sa1"], submission["id"])["score"] == 10


def test_T009_01_invalid_option_key_is_422_on_save(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = post_as(school["app"], school["sa1"], "post",
                         f"{API}/assessments/{assessment['id']}/submissions", {}).get_json()["data"]
    response = post_as(school["app"], school["sa1"], "put",
                       f"{API}/submissions/{submission['id']}/answers", {
                           "version": submission["version"],
                           "answers": [{"item_id": item["id"], "selected": ["Z"]}],
                       })
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"
    assert "selected" in response.get_json()["error"]["details"]["fields"]


def test_T009_01_missing_answer_scores_zero_and_leaves_trace(school):
    """漏答按空答案计 0 分，并在 submission_answers 留痕。"""
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    submission = start_and_answer(school, school["sa1"], assessment["id"], [])
    release_after_end(school, assessment["id"])
    assert result_of(school, school["sa1"], submission["id"])["score"] == 0
    assert scalar(
        school["app"],
        "SELECT COUNT(*) FROM submission_answers WHERE submission_id=? AND selected_json='[]' AND correct=0",
        (submission["id"],),
    ) == 1


def test_T009_01_question_write_rules(school):
    """单选一个答案、多选≥2、判断 true/false、选项 key 唯一、知识点 1—3。"""
    cases = [
        ({"type": "single", "options": [{"key": "A", "label": "a"}, {"key": "B", "label": "b"}], "answer": ["A", "B"]}, "answer"),
        ({"type": "multiple", "options": [{"key": "A", "label": "a"}, {"key": "B", "label": "b"}], "answer": ["A"]}, "answer"),
        ({"type": "boolean", "options": [{"key": "A", "label": "a"}, {"key": "B", "label": "b"}], "answer": ["A"]}, "options"),
        ({"type": "single", "options": [{"key": "A", "label": "a"}, {"key": "A", "label": "b"}], "answer": ["A"]}, "options"),
        ({"type": "single", "options": [{"key": "A", "label": "a"}, {"key": "B", "label": "b"}], "answer": ["C"]}, "answer"),
    ]
    for payload, field in cases:
        response = post_as(school["app"], school["ta"], "post", f"{API}/questions", {
            "stem_md": "边界题", "explanation_md": "解析", "difficulty": 1,
            "knowledge_ids": [school["point"]["id"]], "published": True, **payload,
        })
        assert response.status_code == 422, payload
        assert field in response.get_json()["error"]["details"]["fields"], payload

    too_many = post_as(school["app"], school["ta"], "post", f"{API}/questions", {
        "type": "single", "stem_md": "知识点过多", "explanation_md": "解析", "difficulty": 1,
        "options": [{"key": "A", "label": "a"}, {"key": "B", "label": "b"}], "answer": ["A"],
        "knowledge_ids": [school["point"]["id"], school["point2"]["id"], 9999],
        "published": True,
    })
    assert too_many.status_code == 422


# ---- T-009-02 发布冻结 ----

def test_T009_02_editing_question_does_not_change_published_items_or_scores(school):
    question = single_question(school, stem="原始题干")
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])])
    release_after_end(school, assessment["id"])
    assert result_of(school, school["sa1"], submission["id"])["score"] == 10

    before = scalar(
        school["app"], "SELECT snapshot_json FROM assessment_items WHERE id=?", (item["id"],)
    )

    # 教师把答案改成 B，并把题干改掉
    patched = post_as(school["app"], school["ta"], "patch", f"{API}/questions/{question['id']}", {
        "version": question["version"], "answer": ["B"], "stem_md": "改后的题干",
    })
    assert patched.status_code == 200, patched.get_data(as_text=True)
    assert patched.get_json()["data"]["version"] == question["version"] + 1

    after = scalar(
        school["app"], "SELECT snapshot_json FROM assessment_items WHERE id=?", (item["id"],)
    )
    assert before == after, "已发布测评的题目快照不得随题库修改而变化"

    body = result_of(school, school["sa1"], submission["id"])
    assert body["items"][0]["answer"] == ["A"], "已有成绩按发布时的答案解释"
    assert body["score"] == 10

    # 改题后新发布的一份测评使用新答案；任课教师读成绩不受反馈公开时机限制
    fresh = publish_class_assessment(school, [question], title="改题后")
    fresh_item = items_of(school, fresh["id"], school["sa1"])[0]
    fresh_submission = start_and_answer(school, school["sa1"], fresh["id"], [(fresh_item["id"], ["B"])])
    fresh_body = result_of(school, school["ta"], fresh_submission["id"])
    assert fresh_body["feedback_available"] is True
    assert fresh_body["score"] == 10


def test_T009_02_draft_items_can_be_edited_before_publication(school):
    question = single_question(school)
    other = single_question(school, stem="第二题")
    draft = post_as(school["app"], school["ta"], "post", f"{API}/assessments", {
        "class_id": school["class_a"]["id"], "kind": "quiz", "title": "草稿",
        "items": [{"question_id": question["id"], "points": 5}],
    }).get_json()["data"]
    assert draft["state"] == "draft" and draft["total_score"] == 5

    patched = post_as(school["app"], school["ta"], "patch", f"{API}/assessments/{draft['id']}", {
        "version": draft["version"],
        "items": [{"question_id": question["id"], "points": 5}, {"question_id": other["id"], "points": 7}],
    })
    assert patched.status_code == 200
    assert patched.get_json()["data"]["total_score"] == 12


# ---- T-009-03 并发开始与幂等最终化 ----

def test_T009_03_concurrent_start_keeps_single_submission(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    app = school["app"]
    client, csrf = school["sa1"]
    sid = client.get_cookie("sid").value
    barrier = threading.Barrier(2)
    responses = []

    def attempt():
        worker = app.test_client()
        worker.set_cookie("sid", sid)
        barrier.wait(timeout=10)
        responses.append(
            worker.post(
                f"{API}/assessments/{assessment['id']}/submissions",
                headers={"X-CSRF-Token": csrf},
                json={},
            )
        )

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(r.status_code for r in responses) == [200, 201], [
        r.get_data(as_text=True) for r in responses
    ]
    assert len({r.get_json()["data"]["id"] for r in responses}) == 1
    assert scalar(
        app,
        "SELECT COUNT(*) FROM submissions WHERE assessment_id=? AND student_id=?",
        (assessment["id"], student_id(school)),
    ) == 1


def test_T009_03_repeated_finalization_returns_original_result(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])])

    again = post_as(school["app"], school["sa1"], "post",
                    f"{API}/submissions/{submission['id']}/finalization",
                    {"version": submission["version"]})
    assert again.status_code == 200
    assert again.get_json()["data"] == submission, "重试最终化应逐字段返回原结果"

    release_after_end(school, assessment["id"])
    assert result_of(school, school["sa1"], submission["id"])["score"] == 10


def test_T009_03_submitted_submission_rejects_further_edits(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])])

    response = post_as(school["app"], school["sa1"], "put",
                       f"{API}/submissions/{submission['id']}/answers", {
                           "version": submission["version"],
                           "answers": [{"item_id": item["id"], "selected": ["B"]}],
                       })
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "STATE_CONFLICT"


def test_T009_03_stale_version_on_save_is_409(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = post_as(school["app"], school["sa1"], "post",
                         f"{API}/assessments/{assessment['id']}/submissions", {}).get_json()["data"]
    response = post_as(school["app"], school["sa1"], "put",
                       f"{API}/submissions/{submission['id']}/answers", {
                           "version": submission["version"] + 3,
                           "answers": [{"item_id": item["id"], "selected": ["A"]}],
                       })
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "VERSION_CONFLICT"


# ---- T-009-04 首答与重练 ----

def test_T009_04_first_attempt_stays_wrong_after_correct_retry(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]

    first = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["B"])])
    release_after_end(school, assessment["id"])
    assert result_of(school, school["sa1"], first["id"])["score"] == 0

    before = api_call(school["sa1"][0], "get", f"{API}/me/mistakes").get_json()["data"]
    assert [row["question_id"] for row in before] == [question["id"]]
    assert before[0]["latest_correct"] is False
    assert before[0]["last_wrong_at"] == first["submitted_at"]

    # 错题重练：用 mistake_question_ids 建自练并答对（自练提交后立即反馈）
    practice = post_as(school["app"], school["sa1"], "post", f"{API}/practice-sessions", {
        "mistake_question_ids": [question["id"]], "count": 1,
    })
    assert practice.status_code == 201, practice.get_data(as_text=True)
    practice_body = practice.get_json()["data"]
    assert practice_body["kind"] == "practice" and practice_body["feedback_released"] is True
    retried = start_and_answer(
        school, school["sa1"], practice_body["id"], [(practice_body["items"][0]["id"], ["A"])]
    )
    assert retried["score"] == 1, "自练反馈立即可见"

    # 错题最新状态已纠正，但答案错的时间仍是第一次
    after = api_call(school["sa1"][0], "get", f"{API}/me/mistakes").get_json()["data"]
    assert len(after) == 1
    assert after[0]["latest_correct"] is True
    assert after[0]["last_wrong_at"] == before[0]["last_wrong_at"]

    # 首答（最早一次已提交作答）仍是错的：重练答对不改变首答统计
    first_answer = scalar(
        school["app"],
        "SELECT correct FROM submission_answers sa JOIN submissions s ON s.id=sa.submission_id "
        "WHERE s.student_id=? AND s.status='submitted' AND sa.item_id=? ORDER BY s.submitted_at LIMIT 1",
        (student_id(school), item["id"]),
    )
    assert first_answer == 0

    # 原错误仍然可查
    original = result_of(school, school["sa1"], first["id"])
    assert original["score"] == 0
    assert original["items"][0]["correct"] is False
    assert original["items"][0]["selected"] == ["B"]

    # resolved 过滤：已纠正的不再出现在未纠正列表
    unresolved = api_call(school["sa1"][0], "get", f"{API}/me/mistakes?resolved=false")
    assert [row["question_id"] for row in unresolved.get_json()["data"]] == []


def test_T009_04_unreleased_class_questions_are_excluded_from_practice_and_mistakes(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["B"])])
    assert submission["score"] is None, "反馈未公开前提交响应也不返回分数"

    # 反馈尚未公开：结果不透露对错与分数
    hidden = api_call(school["sa1"][0], "get", f"{API}/submissions/{submission['id']}/result")
    hidden_body = hidden.get_json()["data"]
    assert hidden_body["feedback_available"] is False
    assert hidden_body["score"] is None
    assert set(hidden_body["items"][0]) == {"item_id", "selected"}

    # 未公开反馈的题目不能进入自练，也不能进入错题视图
    blocked = post_as(school["app"], school["sa1"], "post", f"{API}/practice-sessions", {
        "knowledge_ids": [school["point"]["id"]],
    })
    assert blocked.status_code == 422
    assert blocked.get_json()["error"]["code"] == "INFEASIBLE_PAPER"
    assert blocked.get_json()["error"]["details"]["available"] == 0

    assert api_call(school["sa1"][0], "get", f"{API}/me/mistakes").get_json()["data"] == []

    # 公开反馈后解除：结果可读，题目可重练
    release_after_end(school, assessment["id"])

    shown_body = result_of(school, school["sa1"], submission["id"])
    assert shown_body["feedback_available"] is True
    assert shown_body["score"] == 0
    assert shown_body["items"][0]["correct"] is False

    allowed = post_as(school["app"], school["sa1"], "post", f"{API}/practice-sessions", {
        "knowledge_ids": [school["point"]["id"]], "count": 1,
    })
    assert allowed.status_code == 201, allowed.get_data(as_text=True)
    rows = api_call(school["sa1"][0], "get", f"{API}/me/mistakes").get_json()["data"]
    assert [row["question_id"] for row in rows] == [question["id"]]


# ---- 反馈时机与学生投影 ----

def test_student_never_receives_answer_fields_before_release(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])

    detail = api_call(school["sa1"][0], "get", f"{API}/assessments/{assessment['id']}")
    items = detail.get_json()["data"]["items"]
    assert items and "answer" not in items[0] and "explanation_md" not in items[0]
    assert set(items[0]) == {"id", "question_id", "position", "points", "type", "stem_md", "options", "knowledge_ids"}


def test_student_before_start_only_gets_summary(school):
    question = single_question(school)
    starts = parse(school["clock"]["now"])
    items = [{"question_id": question["id"], "points": 10}]
    draft = post_as(school["app"], school["ta"], "post", f"{API}/assessments", {
        "class_id": school["class_a"]["id"], "kind": "quiz", "title": "未开始", "items": items,
    }).get_json()["data"]
    published = post_as(school["app"], school["ta"], "post",
                        f"{API}/assessments/{draft['id']}/publication", {
                            "version": draft["version"],
                            "starts_at": stamp(starts + timedelta(minutes=30)),
                            "ends_at": stamp(starts + timedelta(minutes=90)),
                        }).get_json()["data"]
    assert published["effective_state"] == "upcoming"

    detail = api_call(school["sa1"][0], "get", f"{API}/assessments/{draft['id']}")
    body = detail.get_json()["data"]
    assert body["effective_state"] == "upcoming"
    assert body["items"] == []

    early = post_as(school["app"], school["sa1"], "post",
                    f"{API}/assessments/{draft['id']}/submissions", {})
    assert early.status_code == 409
    assert early.get_json()["error"]["code"] == "STATE_CONFLICT"


# ---- 权限与跨班对象（含 #4 T-001-02 补测）----

def test_assessment_list_exposes_own_submission_id(school):
    """APIC：列表里的 my_submission_id 只返回当前学生自己的提交 ID，教师为 null。"""
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])])

    mine = {
        row["id"]: row["my_submission_id"]
        for row in api_call(school["sa1"][0], "get", f"{API}/assessments").get_json()["data"]
    }
    assert mine[assessment["id"]] == submission["id"]

    peer = {
        row["id"]: row["my_submission_id"]
        for row in api_call(school["sa2"][0], "get", f"{API}/assessments").get_json()["data"]
    }
    assert peer[assessment["id"]] is None

    teacher_rows = api_call(school["ta"][0], "get", f"{API}/assessments").get_json()["data"]
    assert all(row["my_submission_id"] is None for row in teacher_rows)


def test_other_teacher_cannot_read_result(school):
    """#4 T-001-02 补测：教师猜测其他班学生答案 ID 返回 404。"""
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    submission = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])])

    other = api_call(school["tb"][0], "get", f"{API}/submissions/{submission['id']}/result")
    assert other.status_code == 404
    assert other.get_json()["error"]["code"] == "NOT_FOUND"

    # 同班另一名学生也不能读别人的提交
    peer = api_call(school["sa2"][0], "get", f"{API}/submissions/{submission['id']}/result")
    assert peer.status_code == 404

    # 任课教师本人可以读
    mine = api_call(school["ta"][0], "get", f"{API}/submissions/{submission['id']}/result")
    assert mine.status_code == 200


def test_teacher_cannot_touch_other_teachers_assessment(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    for method, path, payload in (
        ("get", f"{API}/assessments/{assessment['id']}", None),
        ("patch", f"{API}/assessments/{assessment['id']}", {"version": 1, "title": "越权"}),
        ("post", f"{API}/assessments/{assessment['id']}/closure", {"version": 1}),
        ("post", f"{API}/assessments/{assessment['id']}/feedback-release", {"version": 1}),
    ):
        response = post_as(school["app"], school["tb"], method, path, payload)
        assert response.status_code == 404, f"{path} -> {response.status_code}"


def test_other_teacher_draft_question_is_404(school):
    draft = make_question(school["app"], school["ta"], stem="甲班草稿", published=False,
                          knowledge_ids=[school["point"]["id"]])
    assert api_call(school["tb"][0], "get", f"{API}/questions/{draft['id']}").status_code == 404
    assert api_call(school["ta"][0], "get", f"{API}/questions/{draft['id']}").status_code == 200

    # 已发布题目对另一位教师可读（共享题库）
    shared = single_question(school, stem="共享题")
    assert api_call(school["tb"][0], "get", f"{API}/questions/{shared['id']}").status_code == 200
    patch_other = post_as(school["app"], school["tb"], "patch", f"{API}/questions/{shared['id']}", {
        "version": shared["version"], "stem_md": "越权改题",
    })
    assert patch_other.status_code == 404


def test_student_outside_roster_cannot_reach_assessment(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    assert api_call(school["sb1"][0], "get", f"{API}/assessments/{assessment['id']}").status_code == 404
    assert post_as(school["app"], school["sb1"], "post",
                   f"{API}/assessments/{assessment['id']}/submissions", {}).status_code == 404


def test_admin_and_anonymous_are_refused(school):
    question = single_question(school)
    assert api_call(school["admin"][0], "get", f"{API}/questions").status_code == 403
    assert api_call(school["admin"][0], "get", f"{API}/assessments").status_code == 403

    anonymous = school["app"].test_client()
    assert anonymous.get(f"{API}/questions").status_code == 401
    assert anonymous.get(f"{API}/me/mistakes").status_code == 401

    no_csrf = school["sa1"][0].post(f"{API}/practice-sessions", json={"difficulty": 1})
    assert no_csrf.status_code == 403
    assert no_csrf.get_json()["error"]["code"] == "CSRF_FAILED"


# ---- 自练、发布与结束 ----

def test_start_submission_returns_existing_after_deadline(school):
    """截止只拦住新建：已有提交仍可取回，否则学生再也看不到自己的结果。"""
    question = single_question(school)
    assessment = publish_class_assessment(school, [question], minutes_ahead=30)
    item = items_of(school, assessment["id"], school["sa1"])[0]
    saved = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])], submit=False)

    advance(school["clock"], 31)
    again = post_as(school["app"], school["sa1"], "post",
                    f"{API}/assessments/{assessment['id']}/submissions", {})
    assert again.status_code == 200
    assert again.get_json()["data"]["id"] == saved["id"]

    blocked = post_as(school["app"], school["sa2"], "post",
                      f"{API}/assessments/{assessment['id']}/submissions", {})
    assert blocked.status_code == 409
    assert blocked.get_json()["error"]["code"] == "DEADLINE_PASSED"


def test_practice_session_requires_one_source_and_reports_available(school):
    single_question(school)

    both = post_as(school["app"], school["sa1"], "post", f"{API}/practice-sessions", {
        "knowledge_ids": [school["point"]["id"]], "mistake_question_ids": [1],
    })
    assert both.status_code == 422

    neither = post_as(school["app"], school["sa1"], "post", f"{API}/practice-sessions", {})
    assert neither.status_code == 422

    too_many = post_as(school["app"], school["sa1"], "post", f"{API}/practice-sessions", {
        "knowledge_ids": [school["point"]["id"]], "count": 5,
    })
    assert too_many.status_code == 422
    assert too_many.get_json()["error"]["code"] == "INFEASIBLE_PAPER"
    assert too_many.get_json()["error"]["details"]["available"] == 1
    assert too_many.get_json()["error"]["details"]["requested"] == 5


def test_practice_session_filters_and_lists_for_owner_only(school):
    first = single_question(school, stem="题一")
    second = single_question(school, stem="题二")
    boolean_question(school, stem="题三")

    practice = post_as(school["app"], school["sa1"], "post", f"{API}/practice-sessions", {
        "difficulty": 1, "count": 2,
    })
    assert practice.status_code == 201, practice.get_data(as_text=True)
    body = practice.get_json()["data"]
    assert body["kind"] == "practice" and body["class_id"] is None
    assert len(body["items"]) == 2 and body["total_score"] == 2
    assert body["feedback_released"] is True
    ids = [item["question_id"] for item in body["items"]]
    assert ids == [first["id"], second["id"]]

    # 只有本人能开始与查看自练
    assert post_as(school["app"], school["sa2"], "post",
                   f"{API}/assessments/{body['id']}/submissions", {}).status_code == 404
    assert api_call(school["sa2"][0], "get", f"{API}/assessments/{body['id']}").status_code == 404
    assert api_call(school["tb"][0], "get", f"{API}/assessments/{body['id']}").status_code == 404

    # 自练结束后不能再提交
    advance(school["clock"], 24 * 60 + 1)
    late = post_as(school["app"], school["sa1"], "post",
                   f"{API}/assessments/{body['id']}/submissions", {})
    assert late.status_code == 409
    assert late.get_json()["error"]["code"] == "DEADLINE_PASSED"


def test_publication_validates_window_and_state(school):
    question = single_question(school)
    draft = post_as(school["app"], school["ta"], "post", f"{API}/assessments", {
        "class_id": school["class_a"]["id"], "kind": "quiz", "title": "窗口",
        "items": [{"question_id": question["id"], "points": 10}],
    }).get_json()["data"]
    now = parse(school["clock"]["now"])

    bad = post_as(school["app"], school["ta"], "post",
                  f"{API}/assessments/{draft['id']}/publication", {
                      "version": draft["version"],
                      "starts_at": stamp(now + timedelta(minutes=30)),
                      "ends_at": stamp(now + timedelta(minutes=10)),
                  })
    assert bad.status_code == 422
    assert "ends_at" in bad.get_json()["error"]["details"]["fields"]

    published = post_as(school["app"], school["ta"], "post",
                        f"{API}/assessments/{draft['id']}/publication", {
                            "version": draft["version"],
                            "starts_at": stamp(now - timedelta(minutes=5)),
                            "ends_at": stamp(now + timedelta(minutes=30)),
                        })
    assert published.status_code == 200
    # 发布后不能改题
    blocked = post_as(school["app"], school["ta"], "patch", f"{API}/assessments/{draft['id']}", {
        "version": published.get_json()["data"]["version"], "title": "改标题",
    })
    assert blocked.status_code == 409


def test_closure_finalizes_started_drafts_as_timeout(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question])
    item = items_of(school, assessment["id"], school["sa1"])[0]
    saved = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])], submit=False)

    closed = post_as(school["app"], school["ta"], "post",
                     f"{API}/assessments/{assessment['id']}/closure",
                     {"version": assessment["version"]})
    assert closed.status_code == 200, closed.get_data(as_text=True)
    assert closed.get_json()["data"]["state"] == "closed"

    row = scalar(
        school["app"],
        "SELECT status || '|' || submit_reason || '|' || score FROM submissions WHERE id=?",
        (saved["id"],),
    )
    assert row == "submitted|timeout|10"


def test_reading_result_finalizes_ended_submission(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question], minutes_ahead=30)
    item = items_of(school, assessment["id"], school["sa1"])[0]
    saved = start_and_answer(school, school["sa1"], assessment["id"], [(item["id"], ["A"])], submit=False)
    assert saved["status"] == "draft"

    advance(school["clock"], 31)
    result = api_call(school["sa1"][0], "get", f"{API}/submissions/{saved['id']}/result")
    assert result.status_code == 200
    assert scalar(school["app"], "SELECT status FROM submissions WHERE id=?", (saved["id"],)) == "submitted"

    # 结束后不能再提交或保存
    late = post_as(school["app"], school["sa1"], "post",
                   f"{API}/submissions/{saved['id']}/finalization", {"version": saved["version"]})
    assert late.status_code == 200  # 已经最终化，幂等返回原结果
    fresh = post_as(school["app"], school["sa2"], "post",
                    f"{API}/assessments/{assessment['id']}/submissions", {})
    assert fresh.status_code == 409


def test_feedback_release_requires_closure_and_is_idempotent(school):
    question = single_question(school)
    assessment = publish_class_assessment(school, [question], minutes_ahead=30)

    early = post_as(school["app"], school["ta"], "post",
                    f"{API}/assessments/{assessment['id']}/feedback-release",
                    {"version": assessment["version"]})
    assert early.status_code == 409
    assert early.get_json()["error"]["code"] == "STATE_CONFLICT"

    advance(school["clock"], 31)
    first = post_as(school["app"], school["ta"], "post",
                    f"{API}/assessments/{assessment['id']}/feedback-release",
                    {"version": assessment["version"]})
    assert first.status_code == 200
    assert first.get_json()["data"]["feedback_released"] is True

    # 公开后幂等：重复调用（哪怕 version 过期）仍返回成功
    again = post_as(school["app"], school["ta"], "post",
                    f"{API}/assessments/{assessment['id']}/feedback-release", {"version": 1})
    assert again.status_code == 200
    assert again.get_json()["data"]["feedback_released"] is True


def test_mistakes_filters_and_isolation(school):
    first = single_question(school, stem="题一")
    second = boolean_question(school, stem="题二")
    assessment = publish_class_assessment(school, [first, second])
    items = {item["question_id"]: item for item in items_of(school, assessment["id"], school["sa1"])}
    start_and_answer(school, school["sa1"], assessment["id"], [
        (items[first["id"]]["id"], ["B"]),
        (items[second["id"]]["id"], ["true"]),
    ])
    release_after_end(school, assessment["id"])

    rows = api_call(school["sa1"][0], "get", f"{API}/me/mistakes").get_json()["data"]
    assert [row["question_id"] for row in rows] == [first["id"]]

    by_knowledge = api_call(
        school["sa1"][0], "get", f"{API}/me/mistakes?knowledge_id={school['point2']['id']}"
    ).get_json()["data"]
    assert by_knowledge == []

    # 其他学生看不到别人的错题
    assert api_call(school["sa2"][0], "get", f"{API}/me/mistakes").get_json()["data"] == []
