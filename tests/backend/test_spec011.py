"""SPEC-011 约束智能组卷：T-011-01 至 T-011-04 及公共错误约定。

每个用例使用自己的临时数据库（`upgraded_app` 夹具）。组卷不依赖服务器时间，
因此不冻结时钟；超时用 `PAPER_SOLVER_TIME_LIMIT_SECONDS=0` 触发，避免真的等待
2 秒，也保证「证明无解 422」与「限时无解 503」两条路径都能被稳定复现。
"""

from __future__ import annotations

import json

import pytest

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
STUDENTS = [
    ("stu_a1", "20241001", "学生甲"),
    ("stu_a2", "20241002", "学生乙"),
    ("stu_a3", "20241003", "学生丙"),
    ("stu_a4", "20241004", "学生丁"),
]


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


@pytest.fixture
def school(upgraded_app):
    """教师甲/乙、两个班、甲班四名学生、章节与四个知识点。"""
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
    points = {}
    for index, name in enumerate(["触发器", "状态机", "计数器", "移位寄存器"]):
        points[f"k{index + 1}"] = post_as(app, ta, "post", f"{API}/knowledge-points", {
            "chapter_id": chapter["id"], "title": name, "body_md": f"{name}说明",
            "source_url": None, "sort_order": index, "published": True,
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

    return {
        "app": app,
        "admin": (admin, admin_csrf),
        "ta": ta,
        "tb": tb,
        "class_a": class_a,
        "class_b": class_b,
        "points": points,
        "students": students,
        "actors": {name: login_as(app, name) for name, _n, _d in STUDENTS},
    }


def make_question(app, actor, *, stem, difficulty, knowledge_ids, published=True):
    response = post_as(app, actor, "post", f"{API}/questions", {
        "type": "single",
        "stem_md": stem,
        "options": [{"key": "A", "label": "正确"}, {"key": "B", "label": "错误"}],
        "answer": ["A"],
        "explanation_md": f"{stem} 的解析",
        "difficulty": difficulty,
        "knowledge_ids": knowledge_ids,
        "published": published,
    })
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["data"]


def generate(school, payload, *, who="ta"):
    return post_as(school["app"], school[who], "post", f"{API}/paper-generations", payload)


def base_payload(school, **overrides):
    payload = {
        "class_id": school["class_a"]["id"],
        "title": "约束组卷",
        "kind": "quiz",
        "count": 10,
        "difficulty_counts": {"easy": 4, "medium": 4, "hard": 2},
        "knowledge_minimums": [],
        "seed": 20261002,
    }
    payload.update(overrides)
    return payload


def difficulties_of(school, question_ids):
    engine = school["app"].extensions["db_engine"]
    with engine.connect() as connection:
        mapping = {
            row[0]: row[1]
            for row in connection.exec_driver_sql("SELECT id, difficulty FROM questions")
        }
    return [mapping[qid] for qid in question_ids]


def knowledge_of(school, question_ids):
    engine = school["app"].extensions["db_engine"]
    with engine.connect() as connection:
        rows = connection.exec_driver_sql(
            "SELECT question_id, knowledge_id FROM question_knowledge ORDER BY knowledge_id"
        ).all()
    tags: dict[int, set[int]] = {}
    for question_id, knowledge_id in rows:
        tags.setdefault(question_id, set()).add(knowledge_id)
    return {qid: tags.get(qid, set()) for qid in question_ids}


# ---- T-011-01 逐项满足且无重复 ----

def test_T011_01_selection_satisfies_count_difficulty_and_knowledge(school):
    kid1, kid2 = school["points"]["k1"]["id"], school["points"]["k2"]["id"]
    # 6 简单、6 进阶、4 困难，选 4/4/2；多标签让覆盖更真实
    for index in range(6):
        make_question(school["app"], school["ta"], stem=f"简单 {index}",
                      difficulty=1, knowledge_ids=[kid1] if index % 2 else [kid1, kid2])
    for index in range(6):
        make_question(school["app"], school["ta"], stem=f"进阶 {index}",
                      difficulty=2, knowledge_ids=[kid2] if index % 2 else [kid1, kid2])
    for index in range(4):
        make_question(school["app"], school["ta"], stem=f"困难 {index}",
                      difficulty=3, knowledge_ids=[kid1, kid2])

    response = generate(school, base_payload(
        school, count=10,
        difficulty_counts={"easy": 4, "medium": 4, "hard": 2},
        knowledge_minimums=[{"knowledge_id": kid1, "min_count": 3},
                            {"knowledge_id": kid2, "min_count": 2}],
    ))
    assert response.status_code == 201, response.get_data(as_text=True)
    data = response.get_json()["data"]

    selected = data["selected_ids"]
    assert len(selected) == 10
    assert len(set(selected)) == 10, "同题不得重复"
    assert data["solver_status"] in {"optimal", "feasible"}
    assert data["difficulty_counts"] == {"easy": 4, "medium": 4, "hard": 2}

    picked = difficulties_of(school, selected)
    assert picked.count(1) == 4 and picked.count(2) == 4 and picked.count(3) == 2

    tags = knowledge_of(school, selected)
    assert sum(1 for qid in selected if kid1 in tags[qid]) >= 3
    assert sum(1 for qid in selected if kid2 in tags[qid]) >= 2
    for row in data["coverage"]:
        assert row["satisfied"] is True
        assert row["selected_count"] >= row["min_count"]

    # 落库为 generated 草稿，条目与 generation_json 一致
    assert scalar(school["app"], "SELECT origin FROM assessments WHERE id=?",
                  (data["assessment_id"],)) == "generated"
    assert scalar(school["app"], "SELECT state FROM assessments WHERE id=?",
                  (data["assessment_id"],)) == "draft"
    assert scalar(school["app"], "SELECT COUNT(*) FROM assessment_items WHERE assessment_id=?",
                  (data["assessment_id"],)) == 10
    generation = json.loads(scalar(school["app"], "SELECT generation_json FROM assessments WHERE id=?",
                                   (data["assessment_id"],)))
    assert generation["seed"] == 20261002
    assert generation["selected_ids"] == selected
    assert generation["candidate_fingerprint"]
    assert generation["solver_status"] == data["solver_status"]


# ---- T-011-02 多标签覆盖不被误拒 ----

def test_T011_02_multitag_coverage_sum_exceeding_count_is_not_rejected(school):
    kid1, kid2 = school["points"]["k1"]["id"], school["points"]["k2"]["id"]
    make_question(school["app"], school["ta"], stem="双标签一", difficulty=1,
                  knowledge_ids=[kid1, kid2])
    make_question(school["app"], school["ta"], stem="双标签二", difficulty=1,
                  knowledge_ids=[kid1, kid2])
    make_question(school["app"], school["ta"], stem="单标签", difficulty=1,
                  knowledge_ids=[kid1])

    # min_count 之和 4 > count 2，但两道双标签题即可同时满足
    response = generate(school, base_payload(
        school, count=2, difficulty_counts={"easy": 2},
        knowledge_minimums=[{"knowledge_id": kid1, "min_count": 2},
                            {"knowledge_id": kid2, "min_count": 2}],
    ))
    assert response.status_code == 201, response.get_data(as_text=True)
    data = response.get_json()["data"]
    assert all(row["satisfied"] for row in data["coverage"])
    tags = knowledge_of(school, data["selected_ids"])
    assert sum(1 for qid in data["selected_ids"] if kid1 in tags[qid]) >= 2
    assert sum(1 for qid in data["selected_ids"] if kid2 in tags[qid]) >= 2


# ---- T-011-03 422 无解与 503 超时不混用 ----

def test_T011_03a_difficulty_shortfall_returns_422_with_explanation(school):
    make_question(school["app"], school["ta"], stem="唯一困难题", difficulty=3,
                  knowledge_ids=[school["points"]["k1"]["id"]])
    response = generate(school, base_payload(
        school, count=3, difficulty_counts={"hard": 3}, knowledge_minimums=[],
    ))
    assert response.status_code == 422, response.get_data(as_text=True)
    error = response.get_json()["error"]
    assert error["code"] == "INFEASIBLE_PAPER"
    constraints = error["details"]["constraints"]
    assert {"kind": "difficulty", "difficulty": "hard", "required": 3, "available": 1} in constraints


def _uncoverable_candidates(school):
    """条件：4 道简单题，K1/K2 各 2 道；count=2 却要 K1≥2 且 K2≥2 → 无解。

    每个知识点单独看都有 2 道可用题（必要条件预检通过），只有组合起来才无解，
    因此必须真正搜索才能判定——正好用来区分「证明无解」与「限时无解」。
    """
    kid1, kid2 = school["points"]["k1"]["id"], school["points"]["k2"]["id"]
    for index in range(2):
        make_question(school["app"], school["ta"], stem=f"K1 专用 {index}",
                      difficulty=1, knowledge_ids=[kid1])
    for index in range(2):
        make_question(school["app"], school["ta"], stem=f"K2 专用 {index}",
                      difficulty=1, knowledge_ids=[kid2])
    return kid1, kid2


def test_T011_03b_timeout_without_solution_returns_503_not_422(school):
    kid1, kid2 = _uncoverable_candidates(school)
    payload = base_payload(
        school, count=2, difficulty_counts={"easy": 2},
        knowledge_minimums=[{"knowledge_id": kid1, "min_count": 2},
                            {"knowledge_id": kid2, "min_count": 2}],
    )
    # 限时 0 秒：搜索尚未证明无解 → 503 SOLVER_TIMEOUT
    school["app"].config["PAPER_SOLVER_TIME_LIMIT_SECONDS"] = 0.0
    timeout = generate(school, payload)
    assert timeout.status_code == 503, timeout.get_data(as_text=True)
    assert timeout.get_json()["error"]["code"] == "SOLVER_TIMEOUT"

    # 恢复限时：同一输入搜索完整结束，证明无解 → 422 INFEASIBLE_PAPER
    school["app"].config["PAPER_SOLVER_TIME_LIMIT_SECONDS"] = 2.0
    infeasible = generate(school, payload)
    assert infeasible.status_code == 422, infeasible.get_data(as_text=True)
    assert infeasible.get_json()["error"]["code"] == "INFEASIBLE_PAPER"


# ---- T-011-04 可复现且受历史错题影响 ----

def _six_easy(school):
    kid1 = school["points"]["k1"]["id"]
    return [
        make_question(school["app"], school["ta"], stem=f"题 {index}",
                      difficulty=1, knowledge_ids=[kid1])
        for index in range(6)
    ]


def test_T011_04_same_seed_replays_and_history_changes_selection(school):
    questions = _six_easy(school)
    kid1 = school["points"]["k1"]["id"]
    payload = base_payload(
        school, count=2, difficulty_counts={"easy": 2},
        knowledge_minimums=[{"knowledge_id": kid1, "min_count": 2}], seed=777,
    )

    first = generate(school, payload)
    second = generate(school, payload)
    assert first.status_code == 201 and second.status_code == 201
    assert first.get_json()["data"]["selected_ids"] == second.get_json()["data"]["selected_ids"], \
        "同版本题库与同种子必须可重放"

    # 让四名学生都答错最后一题、答对其余题，改变历史错题分布
    items = [{"question_id": question["id"], "points": 10} for question in questions]
    draft = post_as(school["app"], school["ta"], "post", f"{API}/assessments", {
        "class_id": school["class_a"]["id"], "kind": "quiz", "title": "历史作答",
        "items": items,
    }).get_json()["data"]
    published = post_as(school["app"], school["ta"], "post",
                        f"{API}/assessments/{draft['id']}/publication",
                        {"version": draft["version"],
                         "starts_at": "2026-01-01T00:00:00Z",
                         "ends_at": "2026-12-31T00:00:00Z"})
    assert published.status_code == 200, published.get_data(as_text=True)
    published_items = post_as(school["app"], school["ta"], "get",
                              f"{API}/assessments/{draft['id']}").get_json()["data"]["items"]
    by_question = {item["question_id"]: item["id"] for item in published_items}

    for login_name, _n, _d in STUDENTS:
        actor = school["actors"][login_name]
        submission = post_as(school["app"], actor, "post",
                             f"{API}/assessments/{draft['id']}/submissions", {}).get_json()["data"]
        pairs = []
        for question in questions:
            selected = ["B"] if question["id"] == questions[-1]["id"] else ["A"]
            pairs.append((by_question[question["id"]], selected))
        saved = post_as(school["app"], actor, "put",
                        f"{API}/submissions/{submission['id']}/answers",
                        {"version": submission["version"], "answers": [
                            {"item_id": item_id, "selected": selected} for item_id, selected in pairs]})
        assert saved.status_code == 200, saved.get_data(as_text=True)
        final = post_as(school["app"], actor, "post",
                        f"{API}/submissions/{submission['id']}/finalization",
                        {"version": saved.get_json()["data"]["version"]})
        assert final.status_code == 200, final.get_data(as_text=True)

    after = generate(school, payload)
    assert after.status_code == 201, after.get_data(as_text=True)
    data = after.get_json()["data"]
    # 四人都答错最后一题 → 该题拉普拉斯错误率最高（p=5/6，其余 1/6），
    # 优先级下界也高于其余题上限，因此对任意种子都必须入选
    hardest = questions[-1]["id"]
    assert hardest in data["selected_ids"]
    for seed in range(1, 9):
        variant = generate(school, {**payload, "seed": seed})
        assert variant.status_code == 201, variant.get_data(as_text=True)
        assert hardest in variant.get_json()["data"]["selected_ids"], f"seed={seed} 未选中高错误率题"

    generation = json.loads(scalar(school["app"], "SELECT generation_json FROM assessments WHERE id=?",
                                   (data["assessment_id"],)))
    before_generation = json.loads(scalar(
        school["app"], "SELECT generation_json FROM assessments WHERE id=?",
        (first.get_json()["data"]["assessment_id"],)))
    assert generation["priorities"] != before_generation["priorities"], \
        "历史错题分布变化后目标优先级应实际变化"


# ---- 公共错误约定 ----

def test_anonymous_401_and_student_403(school):
    anonymous = school["app"].test_client()
    csrf = get_csrf(anonymous)
    anon_response = api_call(anonymous, "post", f"{API}/paper-generations",
                             csrf_token=csrf, json=base_payload(school))
    assert anon_response.status_code == 401
    assert anon_response.get_json()["error"]["code"] == "UNAUTHENTICATED"

    student = post_as(school["app"], school["actors"]["stu_a1"], "post",
                      f"{API}/paper-generations", base_payload(school))
    assert student.status_code == 403


def test_cross_class_class_id_returns_404(school):
    make_question(school["app"], school["ta"], stem="题", difficulty=1,
                  knowledge_ids=[school["points"]["k1"]["id"]])
    # 教师乙用甲班的 class_id 组卷 → 404，不泄露班级存在性
    response = generate(school, base_payload(
        school, class_id=school["class_a"]["id"], count=1,
        difficulty_counts={"easy": 1},
    ), who="tb")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_inactive_class_returns_409(school):
    make_question(school["app"], school["ta"], stem="题", difficulty=1,
                  knowledge_ids=[school["points"]["k1"]["id"]])
    deactivated = post_as(school["app"], school["admin"], "patch",
                          f"{API}/classes/{school['class_a']['id']}",
                          {"active": False, "version": school["class_a"]["version"]})
    assert deactivated.status_code == 200, deactivated.get_data(as_text=True)
    response = generate(school, base_payload(
        school, count=1, difficulty_counts={"easy": 1},
    ))
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "STATE_CONFLICT"


def test_field_errors_return_422(school):
    make_question(school["app"], school["ta"], stem="题", difficulty=1,
                  knowledge_ids=[school["points"]["k1"]["id"]])

    mismatch = generate(school, base_payload(
        school, count=5, difficulty_counts={"easy": 2, "medium": 2}))
    assert mismatch.status_code == 422
    assert mismatch.get_json()["error"]["code"] == "VALIDATION_ERROR"
    assert "difficulty_counts" in mismatch.get_json()["error"]["details"]["fields"]

    unknown_field = generate(school, {**base_payload(school), "solver": "milp"})
    assert unknown_field.status_code == 422
    assert "solver" in unknown_field.get_json()["error"]["details"]["unknown_fields"]

    duplicate_knowledge = generate(school, base_payload(
        school, count=2, difficulty_counts={"easy": 2},
        knowledge_minimums=[{"knowledge_id": school["points"]["k1"]["id"], "min_count": 1},
                            {"knowledge_id": school["points"]["k1"]["id"], "min_count": 1}]))
    assert duplicate_knowledge.status_code == 422

    missing_knowledge = generate(school, base_payload(
        school, count=2, difficulty_counts={"easy": 2},
        knowledge_minimums=[{"knowledge_id": 999999, "min_count": 1}]))
    assert missing_knowledge.status_code == 422

    too_many = generate(school, base_payload(
        school, count=2, difficulty_counts={"easy": 2},
        knowledge_minimums=[{"knowledge_id": school["points"]["k1"]["id"], "min_count": 1}
                            for _ in range(19)]))
    assert too_many.status_code == 422

    bad_count = generate(school, base_payload(school, count=31, difficulty_counts={"easy": 31}))
    assert bad_count.status_code == 422
