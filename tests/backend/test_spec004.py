"""SPEC-004 学习预警与分组：T-004-01 至 T-004-04 及配套边界。

纯计算用单元测试固定公式与阈值；接口部分用固定种子数据（直接写考勤、进度、
测评三类记录）+ 独立测试库，验证整条管线的 Warning 结果、批次完整性与权限。
三个因素的数据都来自既有统计口径，因此这里也顺带核对了出勤率与完成率的取值。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import create_app
from app.models import Enrollment, SchoolClass, User, now_utc
from app.models_assessment import (
    Assessment,
    AssessmentItem,
    Question,
    Submission,
    SubmissionAnswer,
)
from app.models_attendance import AttendanceRecord, AttendanceTask
from app.models_content import Chapter, KnowledgePoint, LearningProgress
from app.models_warning import WarningSnapshot
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
    downgrade,
)
from app.warning_service import (
    assign_clusters,
    build_factors,
    score_factors,
)

WINDOW_FROM = "2026-09-01T00:00:00Z"
WINDOW_TO = "2026-10-01T00:00:00Z"
WINDOW = {"from": WINDOW_FROM, "to": WINDOW_TO}
SUBMITTED_AT = "2026-09-20T02:00:00Z"
COMPLETED_AT = "2026-09-15T00:00:00Z"


# ---- 纯计算 ----

def test_T004_01_score_matches_the_spec_example():
    """a=.5、p=.25、e=1 → 0.3×.5 + 0.2×.25 + 0.5×1 = 0.7 → score 70、high。"""
    factors = build_factors(attendance_rate=0.5, completion_rate=0.75, first_accuracy=0.0)
    assert factors == {"attendance": 0.5, "progress": 0.25, "accuracy": 1.0}

    score, level, available = score_factors(factors)
    assert score == 70.0
    assert level == "high"
    assert available == ["attendance", "progress", "accuracy"]
    # 逐项贡献：15 + 5 + 50 = 70
    contributions = {name: 100 * weight * factors[name] for name, weight in
                     {"attendance": 0.3, "progress": 0.2, "accuracy": 0.5}.items()}
    assert contributions == {"attendance": 15.0, "progress": 5.0, "accuracy": 50.0}
    assert sum(contributions.values()) == score


def test_T004_01_level_thresholds():
    """等级阈值按可用因素归一化后的 score 判定：<30 low、<60 medium、否则 high。"""
    cases = [
        ({"attendance": 0.2, "progress": None, "accuracy": 0.0}, "low"),      # 7.5
        ({"attendance": 0.8, "progress": None, "accuracy": 0.0}, "medium"),   # 30.0
        ({"attendance": 0.9, "progress": None, "accuracy": 0.4}, "medium"),   # 58.75
        ({"attendance": 1.0, "progress": None, "accuracy": 0.36}, "high"),    # 60.0
        ({"attendance": 1.0, "progress": None, "accuracy": 1.0}, "high"),     # 100.0
    ]
    for factors, expected in cases:
        score, level, available = score_factors(factors)
        assert available == ["attendance", "accuracy"]
        assert level == expected, (factors, score)


def test_T004_02_single_factor_is_insufficient():
    score, level, available = score_factors(
        {"attendance": 0.9, "progress": None, "accuracy": None}
    )
    assert score is None, "只有一类记录不给分数"
    assert level == "insufficient"
    assert available == ["attendance"]


def test_T004_02_missing_accuracy_is_renormalized_not_zero():
    """缺答题时不把 e 当 0，而是把权重归一到 0.3+0.2。"""
    factors = {"attendance": 0.5, "progress": 0.25, "accuracy": None}
    score, level, available = score_factors(factors)
    assert available == ["attendance", "progress"]
    assert score == 40.0, "100×(0.3×0.5+0.2×0.25)/0.5"
    assert level == "medium"
    # 若错误地把缺失当 0 分，会得到 100×(0.15+0.05)/1.0 = 20
    assert score != 20.0


def test_T004_03_nine_complete_students_are_not_clustered():
    rows = [
        {"student_id": index, "factors": {"attendance": index / 10, "progress": 0.1, "accuracy": 0.2}}
        for index in range(9)
    ]
    labels, reason = assign_clusters(rows=rows)
    assert labels == {}
    assert "9" in reason


def test_T004_03_ten_students_with_three_vectors_are_clustered_and_stable():
    def group(ids, value):
        return [
            {
                "student_id": student_id,
                "factors": {"attendance": value, "progress": value, "accuracy": value},
            }
            for student_id in ids
        ]

    rows = group([1, 2, 3, 4], 0.0) + group([5, 6, 7], 0.5) + group([8, 9, 10], 1.0)
    labels, reason = assign_clusters(rows=rows)
    assert reason is None
    assert set(labels.values()) == {0, 1, 2}, "三类向量应各得一簇"
    # 中心平均风险升序编号：0 风险最低、2 最高
    assert {labels[i] for i in (1, 2, 3, 4)} == {0}
    assert {labels[i] for i in (5, 6, 7)} == {1}
    assert {labels[i] for i in (8, 9, 10)} == {2}

    again, _ = assign_clusters(rows=rows)
    assert again == labels, "固定 random_state 后分组应可重放"


def test_T004_03_two_distinct_vectors_are_not_clustered():
    rows = [
        {"student_id": index, "factors": {"attendance": index % 2 * 0.5, "progress": 0.1, "accuracy": 0.2}}
        for index in range(12)
    ]
    labels, reason = assign_clusters(rows=rows)
    assert labels == {}
    assert "2" in reason


# ---- 固定种子：直接写三类记录 ----

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


def _enroll(admin, admin_csrf, class_id: int, student_id: int):
    return api_call(
        admin,
        "put",
        f"{API}/classes/{class_id}/enrollments",
        csrf_token=admin_csrf,
        json={"student_id": student_id, "active": True},
    )


def session_of(app):
    return app.extensions["db_session"]()


def seed_scenario(app, *, class_id: int, owner_id: int, published: int, students: dict):
    """students: student_id → {present, absent, completed, touched, attempts, correct}。

    出勤：建 max(present+absent) 条已结算任务，每人在前 present 条出勤、其后缺勤。
    进度：建 published 个已发布知识点，每人对前 touched 个留有记录（前 completed 个标完成）。
    答题：建 max(attempts) 道题与一次已发布测评，每人提交一份答卷（前 correct 道判对）。
    """
    session = session_of(app)
    specs = list(students.values())

    total_tasks = max((spec.get("present", 0) + spec.get("absent", 0)) for spec in specs)
    for index in range(total_tasks):
        opens = f"2026-09-{10 + index:02d}T01:00:00Z"
        closes = f"2026-09-{10 + index:02d}T01:10:00Z"
        task = AttendanceTask(
            class_id=class_id,
            title=f"考勤 {index + 1}",
            opens_at=opens,
            late_at=opens,
            closes_at=closes,
            code_hash="seed-only",
            settled_at=closes,
            owner_id=owner_id,
        )
        session.add(task)
        session.flush()
        for student_id, spec in students.items():
            if index >= spec.get("present", 0) + spec.get("absent", 0):
                continue
            status = "present" if index < spec.get("present", 0) else "absent"
            session.add(
                AttendanceRecord(task_id=task.id, student_id=student_id, status=status)
            )

    chapter = Chapter(title="第五单元 计数器", sort_order=5, published=1, owner_id=owner_id)
    session.add(chapter)
    session.flush()
    points = []
    for index in range(published):
        point = KnowledgePoint(
            chapter_id=chapter.id,
            title=f"知识点 {index + 1}",
            body_md="模 6 计数器状态为 0000—0101。",
            sort_order=index,
            published=1,
            owner_id=owner_id,
        )
        session.add(point)
        points.append(point)
    session.flush()
    for student_id, spec in students.items():
        for index in range(min(spec.get("touched", 0), published)):
            session.add(
                LearningProgress(
                    student_id=student_id,
                    knowledge_id=points[index].id,
                    completed=1 if index < spec.get("completed", 0) else 0,
                    completed_at=COMPLETED_AT if index < spec.get("completed", 0) else None,
                )
            )

    total_questions = max((spec.get("attempts", 0) for spec in specs), default=0)
    if total_questions:
        questions = []
        for index in range(total_questions):
            question = Question(
                type="single",
                stem_md=f"第 {index + 1} 题：Q=0101 的下一状态？",
                options_json='[{"key":"A","label":"0000"},{"key":"B","label":"0110"}]',
                answer_json='["A"]',
                explanation_md="模 6 计数器下一拍加一。",
                difficulty=1,
                published=1,
                owner_id=owner_id,
            )
            session.add(question)
            questions.append(question)
        session.flush()
        assessment = Assessment(
            class_id=class_id,
            owner_id=owner_id,
            kind="quiz",
            title="模 6 计数器短测",
            state="closed",
            starts_at="2026-09-20T01:00:00Z",
            ends_at="2026-09-20T02:30:00Z",
            total_score=total_questions,
        )
        session.add(assessment)
        session.flush()
        items = []
        for position, question in enumerate(questions, start=1):
            item = AssessmentItem(
                assessment_id=assessment.id,
                question_id=question.id,
                position=position,
                points=1,
            )
            session.add(item)
            items.append(item)
        session.flush()
        for student_id, spec in students.items():
            submission = Submission(
                assessment_id=assessment.id,
                student_id=student_id,
                status="submitted",
                started_at=SUBMITTED_AT,
                submitted_at=SUBMITTED_AT,
                score=spec.get("correct", 0),
            )
            session.add(submission)
            session.flush()
            for index in range(spec.get("attempts", 0)):
                session.add(
                    SubmissionAnswer(
                        submission_id=submission.id,
                        item_id=items[index].id,
                        selected_json='["A"]' if index < spec.get("correct", 0) else '["B"]',
                        correct=1 if index < spec.get("correct", 0) else 0,
                    )
                )
    session.commit()


@pytest.fixture
def lab(tmp_path: Path):
    """教师甲（班甲）+ 教师乙（班乙）；班甲先放 1 名学生，便于逐用例补种。"""
    app = create_app(
        "testing",
        {
            "DATABASE_URL": sqlite_url(tmp_path / "warnings.sqlite"),
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
    student = _register_student(app, "stu_0001", "20240001")
    assert _enroll(admin, admin_csrf, class_a["id"], student["id"]).status_code == 200

    try:
        yield {
            "app": app,
            "admin": (admin, admin_csrf),
            "teacher_a": login_as(app, "teacher_aaa"),
            "teacher_b": login_as(app, "teacher_bbb"),
            "class_a": class_a,
            "class_b": class_b,
            "student_id": student["id"],
            "teacher_id": teacher_a["id"],
        }
    finally:
        app.extensions["db_engine"].dispose()


def warnings(client, class_id: int, **window):
    query = "".join(f"&{key}={value}" for key, value in {**WINDOW, **window}.items())
    return client.get(f"{API}/warnings?class_id={class_id}{query}&page_size=100")


def generate_for(lab, **window):
    """用教师甲的身份生成班甲快照。"""
    client, csrf = lab["teacher_a"]
    payload = {"class_id": lab["class_a"]["id"], **WINDOW, **window}
    return api_call(
        client, "post", f"{API}/warnings/generations", csrf_token=csrf, json=payload
    )


# ---- T-004-01：整条管线 ----


def test_T004_01_pipeline_scores_and_levels(lab):
    """出勤率 .5、完成率 .75、首答正确率 0 → a=.5 p=.25 e=1 → score 70、high。"""
    seed_scenario(
        lab["app"],
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        published=4,
        students={
            lab["student_id"]: {
                "present": 1,
                "absent": 1,
                "completed": 3,
                "touched": 4,
                "attempts": 3,
                "correct": 0,
            }
        },
    )

    response = generate_for(lab)
    assert response.status_code == 201, response.get_data(as_text=True)
    data = response.get_json()["data"]
    assert data["algorithm_version"]
    assert data["cluster_reason"], "样本不足时给出未分组原因"

    row = data["students"][0]
    assert row["factors"] == {"attendance": 0.5, "progress": 0.25, "accuracy": 1.0}
    assert row["score"] == 70.0
    assert row["level"] == "high"
    assert row["available_factors"] == ["attendance", "progress", "accuracy"]
    assert row["sample_counts"] == {"attendance": 2, "progress": 4, "accuracy": 3}
    assert row["cluster_label"] is None
    assert any("出勤" in reason for reason in row["reasons"])
    assert any("70" in str(reason) or "风险" in reason for reason in row["reasons"])

    # 证据落库，且引用的是同一组可追溯数字
    assert scalar(
        lab["app"],
        "SELECT COUNT(*) FROM warning_snapshots WHERE class_id = ?",
        (lab["class_a"]["id"],),
    ) == 1
    evidence = json.loads(scalar(lab["app"], "SELECT evidence_json FROM warning_snapshots"))
    assert evidence["factors"] == {"attendance": 0.5, "progress": 0.25, "accuracy": 1.0}
    assert evidence["sample_counts"] == {"attendance": 2, "progress": 4, "accuracy": 3}
    assert evidence["batch_no"] == 1 and evidence["roster_size"] == 1
    assert evidence["disclaimer"], "证据里保留「不是校准概率」的说明"


# ---- T-004-02：样本不足与缺失重归一化 ----


def test_T004_02_only_one_usable_factor_is_insufficient(lab):
    """只有出勤记录：其他两类没有样本 → 可用项 1 条 → insufficient，score 为 null。"""
    seed_scenario(
        lab["app"],
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        published=4,
        students={
            lab["student_id"]: {"present": 1, "absent": 1, "completed": 0, "touched": 0}
        },
    )

    row = generate_for(lab).get_json()["data"]["students"][0]
    assert row["level"] == "insufficient"
    assert row["score"] is None
    assert row["available_factors"] == ["attendance"]
    assert row["sample_counts"]["accuracy"] == 0
    assert any("少于 2 项" in reason for reason in row["reasons"])
    assert any("首答样本" in reason for reason in row["reasons"])


def test_T004_02_insufficient_when_accuracy_below_threshold(lab):
    """首答只有 2 次（<3）→ 该因素不可用；若其余两项可用则重归一化而不是当 0 分。"""
    seed_scenario(
        lab["app"],
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        published=4,
        students={
            lab["student_id"]: {
                "present": 1,
                "absent": 1,
                "completed": 2,
                "touched": 4,
                "attempts": 2,
                "correct": 0,
            }
        },
    )

    row = generate_for(lab).get_json()["data"]["students"][0]
    assert row["available_factors"] == ["attendance", "progress"]
    assert row["sample_counts"]["accuracy"] == 2
    # a=.5 p=.5 → 100×(0.3×0.5+0.2×0.5)/0.5 = 50
    assert row["score"] == 50.0
    assert row["level"] == "medium"
    assert any("首答样本 2 次" in reason for reason in row["reasons"])


# ---- T-004-03：分组 ----


def test_T004_03_pipeline_clusters_ten_complete_students(lab):
    """10 名三因素齐全、3 类向量的学生 → 响应与库中都带上 cluster_label。"""
    app, admin, admin_csrf = lab["app"], *lab["admin"]
    students = {lab["student_id"]: {
        "present": 1, "absent": 0, "completed": 4, "touched": 4, "attempts": 3, "correct": 3
    }}
    for index in range(2, 11):
        student = _register_student(app, f"stu_{index:04d}", f"20240{index:03d}")
        assert _enroll(admin, admin_csrf, lab["class_a"]["id"], student["id"]).status_code == 200
        if index <= 4:
            spec = {"present": 1, "absent": 0, "completed": 4, "touched": 4, "attempts": 3, "correct": 3}
        elif index <= 7:
            spec = {"present": 1, "absent": 1, "completed": 2, "touched": 4, "attempts": 4, "correct": 2}
        else:
            spec = {"present": 0, "absent": 1, "completed": 0, "touched": 4, "attempts": 3, "correct": 0}
        students[student["id"]] = spec
    seed_scenario(
        app,
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        published=4,
        students=students,
    )

    data = generate_for(lab).get_json()["data"]
    assert data["cluster_reason"] is None
    assert len(data["students"]) == 10
    labels = {row["student_id"]: row["cluster_label"] for row in data["students"]}
    assert set(labels.values()) == {0, 1, 2}
    assert all(row["level"] in ("low", "medium", "high") for row in data["students"])
    stored = scalar(
        app, "SELECT COUNT(*) FROM warning_snapshots WHERE cluster_label IS NOT NULL"
    )
    assert stored == 10


# ---- T-004-04：权限与批次 ----


def test_T004_04_only_own_class_and_roles(lab):
    app = lab["app"]
    teacher_b, csrf_b = lab["teacher_b"]
    class_a_id = lab["class_a"]["id"]

    cross = api_call(
        teacher_b,
        "post",
        f"{API}/warnings/generations",
        csrf_token=csrf_b,
        json={"class_id": class_a_id, **WINDOW},
    )
    assert cross.status_code == 404, "教师乙不能生成班甲的快照"
    assert (
        teacher_b.get(f"{API}/warnings?class_id={class_a_id}&from={WINDOW_FROM}&to={WINDOW_TO}")
        .status_code
        == 404
    )
    assert warnings(lab["teacher_a"][0], class_a_id).status_code == 200

    student_client, _ = login_as(app, "stu_0001")
    assert warnings(student_client, class_a_id).status_code == 403
    assert generate_for(lab).status_code == 201
    assert warnings(app.test_client(), class_a_id).status_code == 401


def test_T004_04_write_requires_csrf(lab):
    client, _ = lab["teacher_a"]
    response = client.post(
        f"{API}/warnings/generations",
        json={"class_id": lab["class_a"]["id"], **WINDOW},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "CSRF_FAILED"


def test_T004_04_no_batch_returns_empty_list(lab):
    response = warnings(lab["teacher_a"][0], lab["class_a"]["id"])
    assert response.status_code == 200
    body = response.get_json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_T004_04_repeated_generations_keep_distinct_batches_and_return_latest(lab):
    seed_scenario(
        lab["app"],
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        published=4,
        students={
            lab["student_id"]: {
                "present": 1, "absent": 1, "completed": 3, "touched": 4, "attempts": 3, "correct": 0
            }
        },
    )
    first = generate_for(lab).get_json()["data"]
    assert first["students"][0]["available_factors"] == ["attendance", "progress", "accuracy"]

    # 第二次生成前删掉进度记录，确保返回的是新批次而不是旧快照
    session = session_of(lab["app"])
    session.query(LearningProgress).delete()
    session.commit()
    second = generate_for(lab).get_json()["data"]

    assert scalar(lab["app"], "SELECT COUNT(*) FROM warning_snapshots") == 2
    with lab["app"].extensions["db_engine"].connect() as connection:
        batch_numbers = sorted(
            json.loads(row[0])["batch_no"]
            for row in connection.exec_driver_sql(
                "SELECT evidence_json FROM warning_snapshots"
            )
        )
    assert batch_numbers == [1, 2], "两次生成写入两个批次"

    listed = warnings(lab["teacher_a"][0], lab["class_a"]["id"]).get_json()
    assert listed["meta"]["total"] == 1, "只返回最近一个完整批次"
    latest = listed["data"][0]
    assert latest["generated_at"] == second["generated_at"]
    assert latest["available_factors"] == ["attendance", "accuracy"], "取的是第二次的数据"
    assert latest["sample_counts"]["progress"] == 0


def test_T004_04_different_windows_are_isolated(lab):
    seed_scenario(
        lab["app"],
        class_id=lab["class_a"]["id"],
        owner_id=lab["teacher_id"],
        published=4,
        students={
            lab["student_id"]: {"present": 1, "absent": 1, "completed": 3, "touched": 4}
        },
    )
    assert generate_for(lab).status_code == 201
    other = warnings(
        lab["teacher_a"][0],
        lab["class_a"]["id"],
        **{"from": "2025-01-01T00:00:00Z", "to": "2025-06-01T00:00:00Z"},
    ).get_json()
    assert other["data"] == [], "窗口不同不返回其他批次的快照"


def test_invalid_parameters_are_rejected(lab):
    client, csrf = lab["teacher_a"]
    class_id = lab["class_a"]["id"]

    def post(payload):
        return api_call(
            client, "post", f"{API}/warnings/generations", csrf_token=csrf, json=payload
        )

    assert post({"class_id": class_id, "from": WINDOW_FROM}).status_code == 400
    assert post({"class_id": class_id, "from": WINDOW_TO, "to": WINDOW_FROM}).status_code == 400
    assert post(
        {"class_id": class_id, "from": "2024-01-01T00:00:00Z", "to": "2026-01-01T00:00:00Z"}
    ).status_code == 400
    assert post({"class_id": class_id, "from": "2026-09-01", "to": WINDOW_TO}).status_code == 422
    assert post({"class_id": class_id, **WINDOW, "extra": 1}).status_code == 422
    assert client.get(f"{API}/warnings").status_code == 400


# ---- 迁移往返 ----

def test_migration_round_trip(tmp_path: Path):
    """upgrade → downgrade 一步（回到 0009_spec007）→ upgrade：只回收本模块的表。"""
    app = create_app(
        "testing",
        {"DATABASE_URL": sqlite_url(tmp_path / "roundtrip.sqlite")},
    )

    def table_exists(name: str) -> bool:
        return scalar(
            app,
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ) == 1

    try:
        upgrade(app)
        assert table_exists("warning_snapshots")

        downgrade(app, "0009_spec007")
        assert not table_exists("warning_snapshots"), "本模块的表随迁移回收"
        assert table_exists("qa_entries"), "只回退本模块一步，前一个模块的表保留"
        assert scalar(
            app,
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name='ix_warning_snapshots_class_generated'",
        ) == 0

        upgrade(app)
        assert table_exists("warning_snapshots")
        assert table_exists("qa_entries")
    finally:
        app.extensions["db_engine"].dispose()
