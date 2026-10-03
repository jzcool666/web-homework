"""SPEC-015 个性化复习推荐：T-015-01 至 T-015-04 及配套边界。

固定数据与独立数据库。主图用 SPEC-005 的 `seed-content` 写入（六单元 12 知识点、
15 条先修关系），保证被测的就是真实课程种子；作答信号走 SPEC-009 的自练流程
（自练 `feedback_released=1`，与错题本 E047 的口径一致）。
"""

from __future__ import annotations

import pytest

from app.recommendation_service import (
    DEFAULT_LIMIT,
    is_mastered,
    knowledge_signals,
    rank,
    score_of,
)
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
POINT_COUNTER = "二进制计数器与模值"
POINT_REGISTER = "4 位移位寄存器与位序"


def login_as(app, login_name, password=DEFAULT_PASSWORD):
    client = app.test_client()
    csrf = get_csrf(client)
    response = login(client, csrf, login_name=login_name, password=password)
    assert response.status_code == 200, response.get_data(as_text=True)
    return client, response.get_json()["data"]["csrf_token"]


def post_as(app, actor, method, path, payload=None):
    client, token = actor
    kwargs = {"json": payload} if payload is not None else {}
    return api_call(client, method, path, csrf_token=token, **kwargs)


def get_as(app, actor, path):
    client, _token = actor
    return client.get(path)


@pytest.fixture
def school(upgraded_app):
    """教师、一个班、三名在班学生，以及 SPEC-005 的课程种子。"""
    app = upgraded_app
    create_admin(app)
    admin, admin_csrf = login_as(app, "admin_root", ADMIN_PASSWORD)
    teacher = post_as(app, (admin, admin_csrf), "post", f"{API}/users", {
        "login_name": "teacher_aaa", "display_name": "教师甲",
        "password": DEFAULT_PASSWORD, "role": "teacher",
    }).get_json()["data"]
    class_a = post_as(app, (admin, admin_csrf), "post", f"{API}/classes", {
        "name": "时序逻辑甲班", "teacher_id": teacher["id"],
    }).get_json()["data"]

    students = {}
    for index, (login_name, number) in enumerate(
        [("stu_a0001", "20241111"), ("stu_a0002", "20242222"), ("stu_a0003", "20243333")]
    ):
        client = app.test_client()
        csrf = get_csrf(client)
        response = register(client, csrf, login_name=login_name, student_no=number,
                            display_name=f"学生{index + 1}")
        assert response.status_code == 201, response.get_data(as_text=True)
        students[login_name] = response.get_json()["data"]
        post_as(app, (admin, admin_csrf), "put", f"{API}/classes/{class_a['id']}/enrollments", {
            "student_id": students[login_name]["id"], "active": True,
        })

    runner = app.test_cli_runner()
    seeded = runner.invoke(args=["seed-content", "--owner-login", "teacher_aaa"])
    assert seeded.exit_code == 0, seeded.output

    return {
        "app": app,
        "admin": (admin, admin_csrf),
        "teacher": login_as(app, "teacher_aaa"),
        "actors": {
            name: login_as(app, name) for name in ("stu_a0001", "stu_a0002", "stu_a0003")
        },
        "class_id": class_a["id"],
        "teacher_id": teacher["id"],
    }


def points(app) -> dict[str, dict]:
    with app.app_context():
        from app.models_content import KnowledgePoint

        session = app.extensions["db_session"]()
        try:
            return {
                point.title: {"id": point.id, "version": point.version}
                for point in session.query(KnowledgePoint).all()
            }
        finally:
            session.close()


def make_question(school, *, stem, knowledge_id, difficulty=1):
    response = post_as(school["app"], school["teacher"], "post", f"{API}/questions", {
        "type": "single",
        "stem_md": stem,
        "options": [{"key": "A", "label": "正确"}, {"key": "B", "label": "错误"}],
        "answer": ["A"],
        "explanation_md": f"{stem} 的解析",
        "difficulty": difficulty,
        "knowledge_ids": [knowledge_id],
        "published": True,
    })
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def practise(school, who, *, knowledge_id, count, wrong=True):
    """让学生做一次自练并把全部题目按对/错提交，返回自练测评。"""
    actor = school["actors"][who]
    created = post_as(school["app"], actor, "post", f"{API}/practice-sessions", {
        "knowledge_ids": [knowledge_id], "count": count,
    })
    assert created.status_code == 201, created.get_data(as_text=True)
    assessment = created.get_json()["data"]

    submission = post_as(school["app"], actor, "post",
                         f"{API}/assessments/{assessment['id']}/submissions", {}).get_json()["data"]
    answers = [
        {"item_id": item["id"], "selected": ["B"] if wrong else ["A"]}
        for item in assessment["items"]
    ]
    saved = post_as(school["app"], actor, "put",
                    f"{API}/submissions/{submission['id']}/answers",
                    {"version": submission["version"], "answers": answers})
    assert saved.status_code == 200, saved.get_data(as_text=True)
    final = post_as(school["app"], actor, "post",
                    f"{API}/submissions/{submission['id']}/finalization",
                    {"version": saved.get_json()["data"]["version"]})
    assert final.status_code == 200, final.get_data(as_text=True)
    return assessment


def recommendations(school, who="stu_a0001", query=""):
    return get_as(school["app"], school["actors"][who], f"{API}/me/recommendations{query}")


def data_of(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


# ---- T-015-01 不同薄弱点给出不同推荐与理由 ----

def test_T015_01_weak_points_drive_different_recommendations(school):
    titles = points(school["app"])
    counter = titles[POINT_COUNTER]["id"]
    register_point = titles[POINT_REGISTER]["id"]
    make_question(school, stem="模 6 计数器下一状态？", knowledge_id=counter)
    make_question(school, stem="模 6 计数器状态数？", knowledge_id=counter)
    make_question(school, stem="移位寄存器位序？", knowledge_id=register_point)

    practice_a = practise(school, "stu_a0001", knowledge_id=counter, count=2)
    practice_b = practise(school, "stu_a0002", knowledge_id=register_point, count=1)
    assert practice_a["kind"] == "practice" and practice_b["kind"] == "practice"

    student_a = data_of(recommendations(school, "stu_a0001"))
    student_b = data_of(recommendations(school, "stu_a0002"))

    assert student_a["algorithm_version"]
    assert student_a["items"][0]["kind"] == "knowledge"
    assert student_a["items"][0]["knowledge_id"] == counter
    assert student_b["items"][0]["knowledge_id"] == register_point
    assert student_a["items"][0]["knowledge_id"] != student_b["items"][0]["knowledge_id"]
    assert student_a["items"][0]["title"] != student_b["items"][0]["title"]

    reason_a = " ".join(student_a["items"][0]["reasons"])
    reason_b = " ".join(student_b["items"][0]["reasons"])
    assert "2/2 道相关题目首答错误" in reason_a, reason_a
    assert "1/1 道相关题目首答错误" in reason_b, reason_b
    assert reason_a != reason_b
    # 理由只说自己错的次数，不借别人的薄弱点
    assert "移位寄存器" not in reason_a and "计数器" not in reason_b
    assert student_a["items"][0]["score"] == 100.0

    # 薄弱知识点后面跟着它「还没答对」的练习
    practice_items = [item for item in student_a["items"] if item["kind"] == "question"]
    assert len(practice_items) == 2, "两道计数器练习都还没答对，都应进入推荐"
    assert {item["knowledge_id"] for item in practice_items} == {counter}
    assert all("尚未答对" in " ".join(item["reasons"]) for item in practice_items)


# ---- T-015-02 冷启动 ----

def test_T015_02_new_student_gets_plain_base_path_without_fake_reasons(school):
    data = data_of(recommendations(school, "stu_a0003"))
    assert len(data["items"]) == DEFAULT_LIMIT
    assert all(item["kind"] == "knowledge" for item in data["items"])
    assert all(item["score"] is None for item in data["items"]), "冷启动不得给虚构得分"
    assert all(item["reasons"] == ["按章节顺序的基础路径"] for item in data["items"])
    for item in data["items"]:
        joined = " ".join(item["reasons"])
        assert "答错" not in joined and "未通过" not in joined and "未完成" not in joined

    # 第一章的知识点排在前面：章节顺序 + 章内排序
    titles = points(school["app"])
    assert data["items"][0]["knowledge_id"] == titles["组合逻辑与时序逻辑的区别"]["id"]
    assert all(item["resource_id"] == item["knowledge_id"] for item in data["items"])


# ---- T-015-03 已掌握被排除、候选不足时不重复 ----

def test_T015_03_mastered_candidate_is_excluded_and_short_list_is_not_padded(school):
    titles = points(school["app"])
    counter = titles[POINT_COUNTER]["id"]
    register_point = titles[POINT_REGISTER]["id"]
    make_question(school, stem="模 6 计数器下一状态？", knowledge_id=counter)
    make_question(school, stem="移位寄存器位序？", knowledge_id=register_point)

    # 学生甲：计数器答错一次（薄弱）；寄存器首答全对并标记完成 → 已掌握
    practise(school, "stu_a0001", knowledge_id=counter, count=1, wrong=True)
    practise(school, "stu_a0001", knowledge_id=register_point, count=1, wrong=False)
    marked = post_as(school["app"], school["actors"]["stu_a0001"], "put",
                     f"{API}/me/learning-progress",
                     {"knowledge_id": register_point, "completed": True})
    assert marked.status_code == 200, marked.get_data(as_text=True)

    items = data_of(recommendations(school, "stu_a0001", "?limit=10"))["items"]
    assert items[0]["knowledge_id"] == counter
    assert register_point not in {item["knowledge_id"] for item in items}, "已掌握知识点不应再被推荐"
    assert (register_point, register_point) not in {
        (item["kind"], item["resource_id"]) for item in items
    }

    # 候选不足 limit 时返回实际数量，不重复凑数
    keep = {counter, register_point}
    for title, meta in titles.items():
        if meta["id"] in keep:
            continue
        removed = post_as(school["app"], school["teacher"], "patch",
                          f"{API}/knowledge-points/{meta['id']}",
                          {"version": meta["version"], "published": False})
        assert removed.status_code == 200, removed.get_data(as_text=True)

    short = data_of(recommendations(school, "stu_a0001", "?limit=10"))["items"]
    assert len(short) < 10, "候选不足时不应凑到 limit"
    keys = [(item["kind"], item["resource_id"]) for item in short]
    assert len(keys) == len(set(keys)), "推荐不得重复同一条目"
    assert all(item["knowledge_id"] == counter for item in short), \
        "撤下发布后只剩下计数器这一条链的候选"


# ---- T-015-04 隔离与未公开测评的题 ----

def test_T015_04_recommendations_are_own_only_and_hide_unreleased_questions(school):
    titles = points(school["app"])
    counter = titles[POINT_COUNTER]["id"]
    hidden = make_question(school, stem="隐藏题：模 6 计数器回卷", knowledge_id=counter)
    visible = make_question(school, stem="可见题：模 6 计数器状态数", knowledge_id=counter)

    # 教师把「隐藏题」放进班级测评并发布，但**不公开反馈**
    draft = post_as(school["app"], school["teacher"], "post", f"{API}/assessments", {
        "class_id": school["class_id"], "kind": "quiz", "title": "进行中的随堂测",
        "items": [{"question_id": hidden["id"], "points": 10}],
    }).get_json()["data"]
    published = post_as(school["app"], school["teacher"], "post",
                        f"{API}/assessments/{draft['id']}/publication",
                        {"version": draft["version"], "starts_at": "2026-01-01T00:00:00Z",
                         "ends_at": "2026-12-31T00:00:00Z"})
    assert published.status_code == 200, published.get_data(as_text=True)

    practise(school, "stu_a0001", knowledge_id=counter, count=1, wrong=True)
    items = data_of(recommendations(school, "stu_a0001", "?limit=10"))["items"]
    resource_ids = {item["resource_id"] for item in items if item["kind"] == "question"}
    assert hidden["id"] not in resource_ids, "未公开反馈的测评所用题不得进入推荐"
    assert visible["id"] in resource_ids

    # 端点固定按本人会话计算：伪造?student_id 不改变结果，也读不到别人的推荐
    b_plain = data_of(recommendations(school, "stu_a0002", "?limit=5"))
    b_with_id = data_of(recommendations(school, "stu_a0002", "?limit=5&student_id=1"))
    assert b_plain == b_with_id, "多余的 student_id 参数不得改变本人推荐"
    student_a = data_of(recommendations(school, "stu_a0001", "?limit=5"))
    assert student_a["items"] != b_plain["items"], "不同学生的推荐不应相同"
    assert student_a["items"][0]["knowledge_id"] == counter
    assert all(item["score"] is None for item in b_plain["items"])


# ---- 公共错误约定与 limit 边界 ----

def test_access_control_and_limit_validation(school):
    anonymous = school["app"].test_client()
    response = anonymous.get(f"{API}/me/recommendations")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "UNAUTHENTICATED"

    teacher = get_as(school["app"], school["teacher"], f"{API}/me/recommendations")
    assert teacher.status_code == 403
    assert teacher.get_json()["error"]["code"] == "FORBIDDEN"

    for bad, status in (("?limit=0", 422), ("?limit=11", 422), ("?limit=abc", 400)):
        rejected = recommendations(school, "stu_a0003", bad)
        assert rejected.status_code == status, bad
    out_of_range = recommendations(school, "stu_a0003", "?limit=11")
    assert "limit" in out_of_range.get_json()["error"]["details"]["fields"]

    assert len(data_of(recommendations(school, "stu_a0003", "?limit=1"))["items"]) == 1
    assert DEFAULT_LIMIT == len(data_of(recommendations(school, "stu_a0003"))["items"])
    assert len(data_of(recommendations(school, "stu_a0003", "?limit=10"))["items"]) == 10


# ---- 纯函数：权重、缺失项与已掌握判定 ----

def test_service_weights_and_missing_signals():
    # 只有错题信号时按该信号单独归一化，缺失项不当失败
    assert score_of(knowledge_signals({"attempts": 4, "errors": 1})) == 25.0
    assert score_of(knowledge_signals({})) is None
    # 三信号齐全：0.5*0.5 + 0.3*1 + 0.2*0 = 0.55
    full = knowledge_signals({
        "attempts": 4, "errors": 2, "completed": 0, "experiment_attempts": 2,
        "experiment_failures": 0,
    })
    assert score_of(full) == 55.0

    # 已完成 + 正确率 .75 不算掌握；正确率 .9 且实验通过才算
    near = knowledge_signals({"attempts": 4, "errors": 1, "completed": 1})
    assert is_mastered(near) is False
    mastered = knowledge_signals({"attempts": 10, "errors": 1, "completed": 1})
    assert is_mastered(mastered) is True
    with_failed_experiment = knowledge_signals({
        "attempts": 10, "errors": 1, "completed": 1, "experiment_attempts": 2,
        "experiment_failures": 1,
    })
    assert is_mastered(with_failed_experiment) is False

    # 薄弱点先出、同分按章节顺序与 ID 排序、无信号的候选排在最后
    points_input = [
        {"id": 5, "title": "乙", "chapter_id": 2, "chapter_sort": 2, "sort_order": 1},
        {"id": 9, "title": "甲", "chapter_id": 1, "chapter_sort": 1, "sort_order": 2},
        {"id": 3, "title": "丙", "chapter_id": 1, "chapter_sort": 1, "sort_order": 2},
    ]
    signals = {5: {"attempts": 2, "errors": 1}, 9: {"attempts": 2, "errors": 1}}
    ranked = rank(points=points_input, edges=[], signals_by_point=signals,
                  questions_by_point={}, limit=5)
    assert [item["resource_id"] for item in ranked] == [9, 5, 3]
    assert [item["score"] for item in ranked] == [50.0, 50.0, None]


def test_service_prerequisite_uses_explicit_incomplete_only():
    points_input = [
        {"id": 1, "title": "先修", "chapter_id": 1, "chapter_sort": 1, "sort_order": 5},
        {"id": 2, "title": "薄弱", "chapter_id": 1, "chapter_sort": 1, "sort_order": 1},
    ]
    # 先修只有「明确未完成」才排在薄弱点之前；没有记录不算未完成
    unmarked = rank(points=points_input, edges=[(1, 2)],
                    signals_by_point={2: {"attempts": 1, "errors": 1}},
                    questions_by_point={}, limit=5)
    assert [item["resource_id"] for item in unmarked] == [2, 1]

    marked = rank(points=points_input, edges=[(1, 2)],
                  signals_by_point={1: {"completed": 0}, 2: {"attempts": 1, "errors": 1}},
                  questions_by_point={}, limit=5)
    assert [item["resource_id"] for item in marked] == [1, 2]
    assert "先修知识点" in marked[0]["reasons"][0]
