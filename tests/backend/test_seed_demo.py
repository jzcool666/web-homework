"""示例初始化的事务、隔离和真实业务接口检查。"""
import json

import pytest
from sqlalchemy import select

from app import seed_demo as module
from app.grading import parse_answer, parse_options
from app.models import User
from app.models_assessment import Question
from app.security import hash_password, verify_password
from helpers import dump_database, make_app, upgrade
from test_spec001 import login_as

PASSWORD = "DemoTestPass2026"


def seed(app, *, password=PASSWORD):
    return app.test_cli_runner().invoke(args=["seed-demo", "--confirm-demo-database"], env={"DEMO_PASSWORD":password})


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    path = tmp_path_factory.mktemp("seed-demo")/"sample.sqlite"
    app = make_app(path)
    upgrade(app)
    result = seed(app)
    assert result.exit_code == 0, result.output
    yield app, path
    app.extensions["db_engine"].dispose()


def scalar(app, sql):
    with app.extensions["db_engine"].connect() as connection:
        return connection.exec_driver_sql(sql).scalar()


def test_demo_counts_and_all_account_logins(seeded):
    app, _ = seeded
    for table, expected in {"users":18,"classes":2,"knowledge_points":12,"questions":36,
                            "experiments":4,"qa_entries":16,"lab_tasks":4,"attendance_tasks":3}.items():
        assert scalar(app, f"SELECT COUNT(*) FROM {table}") == expected
    for name in module.DEMO_ACCOUNTS:
        client, _ = login_as(app, name, PASSWORD)
        response = client.get("/api/v1/me")
        assert response.status_code == 200
        assert "演示" in response.json["data"]["display_name"]


def test_question_semantics_and_snapshots(seeded):
    app, _ = seeded
    with app.extensions["db_session"]() as session:
        for question in session.scalars(select(Question)):
            options = parse_options(question.options, question.type)
            assert parse_answer(question.answer, question.type, [o["key"] for o in options])
        assert scalar(app, "SELECT COUNT(DISTINCT question_id) FROM question_knowledge") == 36
        assert scalar(app, "SELECT COUNT(*) FROM submissions WHERE score=0") >= 1
    student, _ = login_as(app, "demo_student_01", PASSWORD)
    mistakes = student.get("/api/v1/me/mistakes?page_size=100").json["data"]
    assert any(row["latest_correct"] is True for row in mistakes)
    assert any(row["latest_correct"] is False for row in mistakes)
    class_id = scalar(app, "SELECT id FROM classes WHERE name LIKE '演示班A%'")
    previews = student.get(f"/api/v1/preview-assignments?class_id={class_id}").json["data"]
    assert "excerpt" in next(item["content"] for item in previews[0]["items"] if item["target_type"] == "knowledge")
    text = json.dumps(previews, ensure_ascii=False)
    assert "stem_md" in text
    assert '"answer"' not in text and '"explanation_md"' not in text


def test_live_teacher_statistics_warning_and_other_class(seeded):
    app, _ = seeded
    teacher, csrf = login_as(app, "demo_teacher_a", PASSWORD)
    class_id = scalar(app, "SELECT id FROM classes WHERE name LIKE '演示班A%'")
    other = scalar(app, "SELECT id FROM classes WHERE name LIKE '演示班B%'")
    assert teacher.get(f"/api/v1/analytics/learning?class_id={class_id}").status_code == 200
    assert teacher.get(f"/api/v1/analytics/experiment?class_id={class_id}").status_code == 200
    response = teacher.post("/api/v1/warnings/generations", json={"class_id":class_id}, headers={"X-CSRF-Token":csrf})
    assert response.status_code == 201, response.json
    # 输出模型是生成摘要，按既有读取端点获取逐人分组。
    window = response.json["data"]["window"]
    warnings = teacher.get(f"/api/v1/warnings?class_id={class_id}&from={window['from']}&to={window['to']}").json["data"]
    assert len(warnings) == 12
    labels = {row["cluster_label"] for row in warnings if row["cluster_label"] is not None}
    assert labels == {0,1,2}
    assert sum(row["cluster_label"] is not None for row in warnings) >= 10
    assert any(row["level"] == "insufficient" for row in warnings)
    assert teacher.get(f"/api/v1/analytics/learning?class_id={other}").status_code == 404
    student, _ = login_as(app,"demo_student_13",PASSWORD)
    assert student.get(f"/api/v1/preview-assignments?class_id={class_id}").status_code == 404


def test_repeat_preserves_changed_password_and_all_history(seeded):
    app, path = seeded
    with app.extensions["db_session"]() as session:
        user = session.scalar(select(User).where(User.login_name == "demo_student_15"))
        user.password_hash = hash_password("ChangedDemoPass2026")
        user.version += 1
        session.commit()
    before = dump_database(path)
    result = seed(app, password="AnotherDemoPass2026")
    assert result.exit_code == 0 and "未重置" in result.output
    assert before == dump_database(path)
    with app.extensions["db_session"]() as session:
        user = session.scalar(select(User).where(User.login_name == "demo_student_15"))
        assert verify_password(user.password_hash, "ChangedDemoPass2026")


def test_explicit_confirmation_and_password_required(upgraded_app, db_path):
    before = dump_database(db_path)
    runner = upgraded_app.test_cli_runner()
    missing = runner.invoke(args=["seed-demo"], env={"DEMO_PASSWORD":PASSWORD})
    short = runner.invoke(args=["seed-demo","--confirm-demo-database"], env={"DEMO_PASSWORD":"short"})
    empty = runner.invoke(args=["seed-demo","--confirm-demo-database"], env={"DEMO_PASSWORD":""})
    assert all(result.exit_code != 0 for result in (missing, short, empty))
    assert before == dump_database(db_path)


@pytest.mark.parametrize("name", ["real_teacher", "demo_teacher_a"])
def test_non_demo_or_partial_account_refused(upgraded_app, db_path, name):
    with upgraded_app.extensions["db_session"]() as session:
        session.add(User(login_name=name, display_name="保留原账号", role="teacher", active=1,
                         password_hash=hash_password(PASSWORD)))
        session.commit()
    before = dump_database(db_path)
    result = seed(upgraded_app)
    assert result.exit_code != 0
    assert before == dump_database(db_path)


def test_failure_rolls_back_every_table(upgraded_app, db_path, monkeypatch):
    before = dump_database(db_path)
    def broken(*args, **kwargs):
        raise RuntimeError("Injected seed failure")
    monkeypatch.setattr(module, "_questions", broken)
    result = seed(upgraded_app)
    assert result.exit_code != 0
    assert before == dump_database(db_path)
