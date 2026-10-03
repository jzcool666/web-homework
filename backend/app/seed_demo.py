"""显式确认的专用演示库初始化；模拟历史不代表真实师生使用。

不增加业务接口/迁移，不覆盖非演示数据。全体样例在一个事务中创建。
重复调用不续期、不重开课堂、不重置口令或修改任何历史。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import click
from sqlalchemy import select

from .demo_questions import demo_questions
from .experiment_service import expected_states, first_difference, replay_checkpoints
from .grading import build_snapshot, parse_answer, parse_options, score_submission
from .models import Enrollment, SchoolClass, User
from .models_assessment import (
    Assessment, AssessmentItem, AssessmentRoster, Question, QuestionKnowledge,
    Submission, SubmissionAnswer, to_json,
)
from .models_attendance import AttendanceRecord, AttendanceTask, LeaveRequest
from .models_attempt import ExperimentAttempt, experiment_attempt_snapshot
from .models_content import Favorite, KnowledgePoint, LearningProgress, Resource, ResourceEvent, ResourceVersion
from .models_experiment import DemoSession, Experiment, experiment_snapshot, load_json
from .models_lesson import LessonPlan, LessonPlanItem, PreviewAssignment
from .security import hash_password, hash_token, new_token
from .seed_content import SEED_CHAPTERS, seed_course_content
from .seed_experiments import seed_experiments
from .seed_labs import seed_labs
from .seed_qa import seed_qa_entries
from .simulator import initial_state

PLAN_TITLE = "演示备课 · 计数器与寄存器（模拟数据）"
DEMO_ACCOUNTS = {
    "demo_admin": ("admin", None, "演示管理员"),
    "demo_teacher_a": ("teacher", None, "演示教师A"),
    "demo_teacher_b": ("teacher", None, "演示教师B"),
    **{f"demo_student_{i:02}": ("student", f"{99000000+i}", f"演示学生{i:02}") for i in range(1, 16)},
}


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _guard(session):
    users = list(session.scalars(select(User)))
    if not users:
        return False
    for user in users:
        expected = DEMO_ACCOUNTS.get(user.login_name)
        if expected is None or (user.role, user.student_no) != expected[:2]:
            raise click.ClickException("拒绝初始化：目标库含非演示账号或保留账号身份不匹配，请另建空演示库")
    if len(users) != len(DEMO_ACCOUNTS) or not session.scalar(select(LessonPlan.id).where(LessonPlan.title == PLAN_TITLE)):
        raise click.ClickException("拒绝初始化：演示账号/标记不完整，不会补建或覆盖已有数据")
    return True


def _questions(session, teacher, points):
    rows = []
    for entry in demo_questions():
        options = parse_options(entry["options"], entry["type"])
        answer = parse_answer(entry["answer"], entry["type"], [o["key"] for o in options])
        row = Question(type=entry["type"], stem_md=entry["stem_md"], options_json=to_json(options),
                       answer_json=to_json(answer), explanation_md=entry["explanation_md"],
                       difficulty=entry["difficulty"], published=1, owner_id=teacher.id)
        session.add(row)
        session.flush()
        point = points[entry["knowledge_code"]]
        session.add(QuestionKnowledge(question_id=row.id, knowledge_id=point.id))
        rows.append((row, point))
    return rows


def _assessment(session, teacher, school, students, questions, *, title, state, starts, ends, feedback):
    row = Assessment(owner_id=teacher.id, class_id=school.id, kind="quiz", title=title,
                     state=state, starts_at=stamp(starts), ends_at=stamp(ends),
                     feedback_released=int(feedback), total_score=len(questions)*5, origin="manual",
                     created_at=stamp(starts-timedelta(minutes=10)))
    session.add(row)
    session.flush()
    items = []
    for position, (question, point) in enumerate(questions, 1):
        item = AssessmentItem(assessment_id=row.id, question_id=question.id, position=position,
                              points=5, snapshot_json=to_json(build_snapshot(question, [point.id], [point.title])))
        session.add(item)
        items.append(item)
    if state != "draft":
        for student in students:
            session.add(AssessmentRoster(assessment_id=row.id, student_id=student.id))
    session.flush()
    return row, items


def _submission(session, assessment, student, items, *, selected, submitted_at):
    total, graded = score_submission(items, selected)
    row = Submission(assessment_id=assessment.id, student_id=student.id, status="submitted",
                     started_at=assessment.starts_at, submitted_at=stamp(submitted_at),
                     submit_reason="manual", score=total, created_at=assessment.starts_at,
                     updated_at=stamp(submitted_at))
    session.add(row)
    session.flush()
    for item in items:
        correct, points = graded[item.id]
        session.add(SubmissionAnswer(submission_id=row.id, item_id=item.id,
                                     selected_json=to_json(selected.get(item.id, [])),
                                     correct=int(correct), awarded_points=points))


def _history(session, teacher, school, students, points, now):
    for day in (5, 4, 3):
        opens = now-timedelta(days=day, hours=1)
        closes = opens+timedelta(minutes=30)
        task = AttendanceTask(class_id=school.id, owner_id=teacher.id,
                              title=f"演示考勤 {day}（模拟历史）", opens_at=stamp(opens),
                              late_at=stamp(opens+timedelta(minutes=5)), closes_at=stamp(closes),
                              settled_at=stamp(closes), created_at=stamp(opens), code_hash=hash_token(new_token()))
        session.add(task)
        session.flush()
        for index, student in enumerate(students):
            group = index//4
            status = "present" if group == 0 else ("late" if day == 5 else "present") if group == 1 else "absent"
            # 一名学生的一次请假仍保留其他两次有效分母。
            if index == 11 and day == 3:
                status = "leave"
                session.add(LeaveRequest(task_id=task.id, student_id=student.id,
                                        reason="演示请假原因（模拟）", status="approved", reviewer_id=teacher.id,
                                        review_note="演示批准", reviewed_at=stamp(closes), created_at=stamp(opens)))
            signed = opens+timedelta(minutes=1 if status == "present" else 10)
            session.add(AttendanceRecord(task_id=task.id, student_id=student.id, status=status,
                                         signed_at=stamp(signed) if status in {"present", "late"} else None,
                                         created_at=stamp(opens)))
    for index, student in enumerate(students):
        if index == 11:
            # 没有明确进度记录且课堂未答，只有出勤可用，演示“样本不足”。
            continue
        completed_count = (10, 6, 2)[index//4]
        for number, point in enumerate(points.values()):
            completed = number < completed_count
            session.add(LearningProgress(student_id=student.id, knowledge_id=point.id,
                                         completed=int(completed), completed_at=stamp(now-timedelta(days=2)) if completed else None))
    session.add(Favorite(student_id=students[0].id, knowledge_id=points["k10"].id))


def _experiment_history(session, experiments, students, now):
    for index, student in enumerate(students[:8]):
        experiment = experiments[index%4]
        config = load_json(experiment.config_json, {})
        sequence = load_json(experiment.input_sequence_json, [])
        expected = expected_states(replay_checkpoints(experiment.simulator_type, config, sequence))
        for attempt_no in range(2 if index == 0 else 1):
            actual = expected.copy()
            if (index%3 != 1 and attempt_no == 0):
                actual[0] = (actual[0]+1) % (2 if experiment.simulator_type in {"d", "jk"} else 16)
            first_error = first_difference(expected, actual)
            session.add(ExperimentAttempt(
                experiment_id=experiment.id, student_id=student.id,
                created_at=stamp(now-timedelta(days=2, minutes=30-attempt_no)),
                experiment_snapshot_json=to_json(experiment_attempt_snapshot(experiment.simulator_type, config, sequence, experiment.version)),
                predictions_json=to_json(actual), expected_json=to_json(expected), passed=int(first_error is None),
                first_error_index=first_error, request_key=f"demo-exp-{index}-{attempt_no}",
            ))


def _preview(session, teacher, school, points, questions, experiments, now):
    resource = session.scalar(select(Resource).order_by(Resource.id))
    version = session.scalar(select(ResourceVersion).where(ResourceVersion.resource_id == resource.id))
    point = points["k10"]
    question = questions[27][0]
    experiment = next(e for e in experiments if e.simulator_type == "counter")
    plan = LessonPlan(owner_id=teacher.id, title=PLAN_TITLE, planned_at=stamp(now+timedelta(days=1)),
                      notes="模拟教学安排：先预测5→0，再用逐拍演示核对，最后完成随堂测与实验。")
    session.add(plan)
    session.flush()
    content = [
        ("knowledge", "knowledge_id", point.id, {"title":point.title, "excerpt":point.body_md[:200]+("…" if len(point.body_md)>200 else ""), "source_url":point.source_url}),
        ("resource_version", "resource_version_id", version.id,
         {"resource_title":resource.title, "category":resource.category, "version_no":version.version_no,
          "kind":version.kind, "original_name":version.original_name, "mime":version.mime,
          "size_bytes":version.size_bytes, "external_url":version.external_url, "note":version.note}),
        ("question", "question_id", question.id, {"stem_md":question.stem_md}),
        ("experiment", "experiment_id", experiment.id,
         {"title":experiment.title, "simulator_type":experiment.simulator_type, "steps_md":experiment.steps_md}),
    ]
    snapshot = {"plan_title":plan.title, "plan_notes":plan.notes, "captured_at":stamp(now), "items":[]}
    for order, (kind, column, target_id, brief) in enumerate(content, 1):
        session.add(LessonPlanItem(plan_id=plan.id, sort_order=order, **{column:target_id}))
        snapshot["items"].append({"sort_order":order,"target_type":kind,"target_id":target_id,"content":brief})
    session.add(PreviewAssignment(plan_id=plan.id, class_id=school.id, due_at=stamp(now+timedelta(days=7)), snapshot_json=to_json(snapshot)))
    for student in session.scalars(select(User).where(User.login_name.in_([f"demo_student_{i:02}" for i in range(1, 6)]))):
        session.add(ResourceEvent(student_id=student.id, resource_version_id=version.id,
                                  event_kind="open", event_day=(now-timedelta(days=2)).strftime("%Y-%m-%d")))


def seed_demo(session, password, *, now=None):
    """事务提交由调用者负责；返回是否已经初始化。"""
    if _guard(session):
        return True
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    password_hash = hash_password(password)
    users = {}
    for name, (role, number, label) in DEMO_ACCOUNTS.items():
        user = User(login_name=name, role=role, student_no=number, display_name=label,
                    password_hash=password_hash, active=1, created_at=stamp(now-timedelta(days=8)))
        session.add(user)
        users[name] = user
    session.flush()
    teacher = users["demo_teacher_a"]
    schools = []
    for suffix in ("a", "b"):
        school = SchoolClass(name=f"演示班{suffix.upper()}（模拟数据）", teacher_id=users[f"demo_teacher_{suffix}"].id)
        session.add(school)
        schools.append(school)
    session.flush()
    students = [users[f"demo_student_{i:02}"] for i in range(1, 16)]
    for index, student in enumerate(students):
        session.add(Enrollment(class_id=schools[int(index>=12)].id, student_id=student.id,
                               active=1, joined_at=stamp(now-timedelta(days=8))))
    seed_course_content(session, teacher, echo=lambda _: None)
    seed_experiments(session, teacher, echo=lambda _: None)
    seed_qa_entries(session, teacher, echo=lambda _: None)
    seed_labs(session)
    points = {
        entry[0]:session.scalar(select(KnowledgePoint).where(KnowledgePoint.title == entry[1], KnowledgePoint.owner_id == teacher.id))
        for chapter in SEED_CHAPTERS for entry in chapter[2]
    }
    questions = _questions(session, teacher, points)
    experiments = list(session.scalars(select(Experiment).where(Experiment.owner_id == teacher.id).order_by(Experiment.id)))
    _history(session, teacher, schools[0], students[:12], points, now)
    closed, items = _assessment(session, teacher, schools[0], students[:12], questions[:9],
                               title="演示随堂测 · 已讲评（模拟历史）", state="closed", starts=now-timedelta(days=2, hours=1),
                               ends=now-timedelta(days=2), feedback=True)
    for index, student in enumerate(students[:11]):
        count = (8, 5, 1)[index//4]
        selected = {item.id:item.snapshot["answer"] for item in items[:count]}
        # 留白卷一份，其余错误项以漏答示例呈现；仍按全部9题判分。
        if index == 10:
            selected = {}
        if index == 0:
            selected[items[0].id] = ["B"]
        _submission(session, closed, student, items, selected=selected,
                    submitted_at=now-timedelta(days=2, minutes=20-index))
    # 第12人课堂测评未开始；自练不会混入本班测评首答，保留预警样本不足分支。
    practice, practice_items = _assessment(session, teacher, schools[0], [students[11]], questions[:3],
                                          title="演示补充练习（模拟历史）", state="closed", starts=now-timedelta(days=3),
                                          ends=now-timedelta(days=2), feedback=True)
    practice.kind, practice.class_id, practice.owner_id = "practice", None, students[11].id
    _submission(session, practice, students[11], practice_items, selected={}, submitted_at=now-timedelta(days=2, hours=2))
    correction, correction_items = _assessment(session, teacher, schools[0], [students[0]], questions[:1],
                                              title="演示错题重练（模拟历史）", state="closed", starts=now-timedelta(days=1, hours=1),
                                              ends=now-timedelta(days=1), feedback=True)
    correction.kind, correction.class_id, correction.owner_id = "practice", None, students[0].id
    _submission(session, correction, students[0], correction_items,
                selected={correction_items[0].id:correction_items[0].snapshot["answer"]}, submitted_at=now-timedelta(days=1, minutes=10))
    _assessment(session, teacher, schools[0], students[:12], questions[27:30],
                title="演示随堂测 · 现在作答", state="published", starts=now-timedelta(minutes=5), ends=now+timedelta(days=1), feedback=False)
    _assessment(session, teacher, schools[0], students[:12], questions[18:24],
                title="演示随堂测 · 待发布草稿", state="draft", starts=now+timedelta(hours=1), ends=now+timedelta(hours=2), feedback=False)
    _experiment_history(session, experiments, students, now)
    _preview(session, teacher, schools[0], points, questions, experiments, now)
    experiment = next(e for e in experiments if e.simulator_type == "counter")
    snapshot = experiment_snapshot(experiment)
    session.add(DemoSession(class_id=schools[0].id, experiment_id=experiment.id, owner_id=teacher.id,
                            active=1, config_snapshot_json=to_json(snapshot),
                            state_json=to_json(initial_state(experiment.simulator_type, snapshot["config"])),
                            event_log_json="[]", reveal_next=0))
    session.flush()
    return False


def register_demo_cli(app):
    @app.cli.command("seed-demo")
    @click.option("--confirm-demo-database", is_flag=True, help="明确确认当前DATABASE_URL为专用演示库")
    def command(confirm_demo_database):
        """初始化完整模拟示例，口令从DEMO_PASSWORD读取；已有演示库不重置。"""
        if not confirm_demo_database:
            raise click.ClickException("必须提供 --confirm-demo-database，确认目标是专用演示库")
        password = os.environ.get("DEMO_PASSWORD", "")
        if not 10 <= len(password) <= 128:
            raise click.ClickException("DEMO_PASSWORD 必须为10—128字符，不能使用真实个人口令")
        from .store import db_session
        session = db_session()
        try:
            existed = seed_demo(session, password)
            if existed:
                session.rollback()  # 已有演示库只读，不因重复命令产生修改。
            else:
                session.commit()
        except Exception:
            session.rollback()
            raise
        click.echo("已存在完整演示库，未重置口令、截止或历史" if existed else "已创建模拟演示库：18账号、2班、12知识点、36题、4实验、16问答、4接线任务")
        click.echo("账号：demo_admin、demo_teacher_a/b、demo_student_01—15；口令取自本次DEMO_PASSWORD，不回显")
