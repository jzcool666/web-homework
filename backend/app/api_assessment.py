"""E035—E047 题库与测评（SPEC-009 第 4 节）与 E057 测评统计（SPEC-010）。

规则要点：
- 选项与答案结构由 grading 校验；判分只读 assessment_items.snapshot_json，
  发布时在一个事务里冻结题目版本、答案、解析、知识点与分值，之后改题不回写历史。
- 学生读取题目走服务器投影，未到反馈时机不返回 answer/explanation，也不返回题目难度。
- 作答分两步：E044 只保存（不判分），E045 以服务器已保存答案判分；同测评同学生
  靠 UNIQUE(assessment_id, student_id) 保证只有一份提交，并发开始不会产生第二份。
- 首答 = 该学生该题目最早已提交的一次机会；错题 latest_correct 只看最近一次
  已公开反馈的已提交答案，因此重练答对不会改变首答，也不会抹掉历史错误。
- 班级测评已发布（含已结束）但未公开反馈时，其题目对学生自练与错题重练不可见，
  避免绕过反馈策略提前看到答案。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, request
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from .auth import current_user, login_required, roles_required
from .errors import ApiError, success
from .grading import (
    FieldError,
    STEM_MAX,
    build_snapshot,
    parse_answer,
    parse_options,
    score_submission,
    validate_selected,
)
from .models import Enrollment, SchoolClass, User
from .models_assessment import (
    ASSESSMENT_KINDS,
    CLASS_KINDS,
    DIFFICULTIES,
    KIND_PRACTICE,
    MAX_ITEMS,
    MIN_ITEMS,
    POINTS_MAX,
    POINTS_MIN,
    PRACTICE_HOURS,
    QUESTION_TYPES,
    REASON_MANUAL,
    REASON_TIMEOUT,
    STATE_CLOSED,
    STATE_DRAFT,
    STATE_PUBLISHED,
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    Assessment,
    AssessmentItem,
    AssessmentRoster,
    Question,
    QuestionKnowledge,
    Submission,
    SubmissionAnswer,
    assessment_public,
    effective_state,
    from_json,
    question_public,
    submission_public,
    to_json,
)
from .models_content import KnowledgePoint
from .stats_assessment import (
    percent_of,
    score_bucket_rows,
    summarize_assessment,
    summarize_item,
    summarize_knowledge,
    to_csv,
)
from .store import db_session
from .validation import json_object, pagination, text_field

bp = Blueprint("assessment", __name__)

WRITE_FIELDS = (
    "type",
    "stem_md",
    "options",
    "answer",
    "explanation_md",
    "difficulty",
    "knowledge_ids",
    "published",
)
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SEARCH_MAX = 100
PRACTICE_FILTER_KEYS = ("knowledge_ids", "difficulty")


# ---- 时间与字段 ----

def _now() -> str:
    return datetime.now(timezone.utc).strftime(STAMP_FORMAT)


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=timezone.utc)


def _shift(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime(STAMP_FORMAT)


def _fields_error(field: str, rule: str):
    raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {field: rule}})


def _int_field(body: dict, name: str, *, minimum: int = 0) -> int:
    value = body.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        _fields_error(name, f"必须是不小于 {minimum} 的整数")
    return value


def _bool_field(body: dict, name: str) -> bool:
    value = body.get(name)
    if not isinstance(value, bool):
        _fields_error(name, "必须是布尔值")
    return value


def _stem_field(body: dict, name: str = "stem_md") -> str:
    value = body.get(name)
    if not isinstance(value, str) or not (1 <= len(value) <= STEM_MAX):
        _fields_error(name, f"1—{STEM_MAX} 个字符")
    return value


def _explanation_field(body: dict, name: str = "explanation_md") -> str:
    value = body.get(name)
    if not isinstance(value, str) or not (1 <= len(value) <= STEM_MAX):
        _fields_error(name, f"1—{STEM_MAX} 个字符")
    return value


def _type_field(body: dict) -> str:
    value = body.get("type")
    if value not in QUESTION_TYPES:
        _fields_error("type", "single/multiple/boolean")
    return value


def _difficulty_field(body: dict) -> int:
    value = body.get("difficulty")
    if value not in DIFFICULTIES:
        _fields_error("difficulty", "1/2/3")
    return value


def _points_field(body: dict, name: str = "points") -> int:
    value = body.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or not (POINTS_MIN <= value <= POINTS_MAX):
        _fields_error(name, f"必须是 {POINTS_MIN}—{POINTS_MAX} 的整数")
    return value


def _timestamp_field(body: dict, name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str):
        _fields_error(name, "必须是带 Z 的 UTC 时间")
    try:
        _parse(value)
    except ValueError:
        _fields_error(name, "必须是带 Z 的 UTC 时间，如 2026-09-29T01:00:00Z")
    return value


def _knowledge_ids_field(body: dict, session) -> list[int]:
    raw = body.get("knowledge_ids")
    if not isinstance(raw, list) or not raw:
        _fields_error("knowledge_ids", "必须提供 1—3 个知识点")
    ids = list(dict.fromkeys(raw))
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in ids):
        _fields_error("knowledge_ids", "必须是知识点 ID 数组")
    if not (1 <= len(ids) <= 3):
        _fields_error("knowledge_ids", "每题 1—3 个知识点")
    known = set(session.scalars(select(KnowledgePoint.id).where(KnowledgePoint.id.in_(ids))))
    missing = [item for item in ids if item not in known]
    if missing:
        _fields_error("knowledge_ids", f"知识点不存在：{','.join(str(item) for item in missing)}")
    return ids


def _translate(field_error: FieldError):
    raise ApiError(
        "VALIDATION_ERROR", "请求字段不合法", {"fields": {field_error.field: field_error.rule}}
    )


# ---- 查询辅助 ----

def _paginate(session, stmt, page: int, page_size: int):
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return rows, total


def _knowledge_map(session, question_ids) -> dict[int, list[int]]:
    ids = {qid for qid in question_ids if qid is not None}
    if not ids:
        return {}
    rows = session.execute(
        select(QuestionKnowledge.question_id, QuestionKnowledge.knowledge_id).where(
            QuestionKnowledge.question_id.in_(ids)
        )
    ).all()
    mapping: dict[int, list[int]] = {qid: [] for qid in ids}
    for question_id, knowledge_id in rows:
        mapping[question_id].append(knowledge_id)
    return mapping


def _question_or_404(session, question_id: int) -> Question:
    question = session.get(Question, question_id)
    if question is None:
        raise ApiError("NOT_FOUND", "题目不存在")
    return question


def _readable_question(session, question_id: int) -> Question:
    """教师可读已发布共享题与自己的草稿；他人草稿按 404 处理，不泄露存在性。"""
    question = _question_or_404(session, question_id)
    user = current_user()
    if question.published or question.owner_id == user.id:
        return question
    raise ApiError("NOT_FOUND", "题目不存在")


def _writable_question(session, question_id: int) -> Question:
    question = _question_or_404(session, question_id)
    if question.owner_id != current_user().id:
        raise ApiError("NOT_FOUND", "题目不存在")
    return question


def _require_class_teacher(session, class_id: int) -> SchoolClass:
    school_class = session.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_user().id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _require_active_class(school_class: SchoolClass) -> None:
    if not school_class.active:
        raise ApiError("STATE_CONFLICT", "班级已停用，不能发起新的测评活动")


def _require_student_work_access(session, class_id: int | None, student_id: int) -> None:
    """名单是发布快照；新作答仍须满足当前入班关系与班级状态。"""
    if class_id is None:
        school_class = session.scalar(
            select(SchoolClass)
            .join(Enrollment, Enrollment.class_id == SchoolClass.id)
            .where(Enrollment.student_id == student_id, Enrollment.active == 1)
        )
        if school_class is None:
            raise ApiError("FORBIDDEN", "尚未分配班级，暂不能开始自练")
    else:
        school_class = session.get(SchoolClass, class_id)
        enrollment = session.get(Enrollment, (class_id, student_id))
        if school_class is None or enrollment is None or not enrollment.active:
            raise ApiError("NOT_FOUND", "测评不存在")
    _require_active_class(school_class)


def _own_assessment(session, assessment_id: int) -> Assessment:
    assessment = session.get(Assessment, assessment_id)
    if assessment is None or assessment.owner_id != current_user().id:
        raise ApiError("NOT_FOUND", "测评不存在")
    return assessment


def _items_of(session, assessment_id: int) -> list[AssessmentItem]:
    return list(
        session.scalars(
            select(AssessmentItem)
            .where(AssessmentItem.assessment_id == assessment_id)
            .order_by(AssessmentItem.position)
        )
    )


def _roster_student_ids(session, class_id: int) -> list[int]:
    return list(
        session.scalars(
            select(Enrollment.student_id)
            .join(User, User.id == Enrollment.student_id)
            .where(
                Enrollment.class_id == class_id,
                Enrollment.active == 1,
                User.active == 1,
            )
            .order_by(Enrollment.student_id)
        )
    )


def _active_class_ids(session, student_id: int) -> list[int]:
    return list(
        session.scalars(
            select(Enrollment.class_id).where(
                Enrollment.student_id == student_id, Enrollment.active == 1
            )
        )
    )


def _blocked_question_ids(session, student_id: int) -> set[int]:
    """本班已发布（含已结束）但未公开反馈的班级测评所用题目。

    结束不等于公开：直到 feedback_released=true 才解除排除，避免学生用自练
    或错题重练绕过反馈策略提前看到答案。
    """
    class_ids = _active_class_ids(session, student_id)
    if not class_ids:
        return set()
    rows = session.scalars(
        select(AssessmentItem.question_id)
        .join(Assessment, Assessment.id == AssessmentItem.assessment_id)
        .where(
            Assessment.class_id.in_(class_ids),
            Assessment.kind != KIND_PRACTICE,
            Assessment.state.in_((STATE_PUBLISHED, STATE_CLOSED)),
            Assessment.feedback_released == 0,
        )
    )
    return set(rows)


def _roster_entry(session, assessment_id: int, student_id: int) -> AssessmentRoster | None:
    return session.get(AssessmentRoster, (assessment_id, student_id))


def _submission_or_404(session, submission_id: int) -> Submission:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise ApiError("NOT_FOUND", "提交不存在")
    return submission


def _answers_of(session, submission_id: int) -> list[SubmissionAnswer]:
    return list(
        session.scalars(
            select(SubmissionAnswer)
            .where(SubmissionAnswer.submission_id == submission_id)
            .order_by(SubmissionAnswer.item_id)
        )
    )


# ---- 截止最终化（ADR-006：同一个幂等入口）----

def _ended(assessment: Assessment, now: str) -> bool:
    if assessment.state == STATE_CLOSED:
        return True
    return bool(assessment.ends_at) and now >= assessment.ends_at


def _grade_into(session, submission: Submission, items, reason: str, stamp: str) -> None:
    """按快照判分并落库；stamp 是写进 submitted_at 的时间。

    手动提交传服务器当前时间；截止最终化传测评的有效截止时间（ends_at），
    这样统计窗口不会把后台/访问触发处理的延迟算成提交时间（SPEC-010 第 4.7 条）。
    """
    answers = _answers_of(session, submission.id)
    by_item = {answer.item_id: answer.selected for answer in answers}
    # 漏答也要留痕：没有记录的条目按空答案计 0 分
    for item in items:
        if item.id not in by_item:
            session.add(
                SubmissionAnswer(
                    submission_id=submission.id,
                    item_id=item.id,
                    selected_json="[]",
                    correct=None,
                    awarded_points=None,
                )
            )
    session.flush()
    total, graded = score_submission(items, by_item)
    for answer in _answers_of(session, submission.id):
        correct, awarded = graded.get(answer.item_id, (False, 0))
        answer.correct = 1 if correct else 0
        answer.awarded_points = awarded
    submission.status = STATUS_SUBMITTED
    submission.submitted_at = stamp
    submission.submit_reason = reason
    submission.score = total
    submission.final_request_hash = _request_hash(by_item)
    submission.version += 1


def _request_hash(by_item: dict[int, list[str]]) -> str:
    payload = ";".join(
        f"{item_id}:{','.join(sorted(selected))}" for item_id, selected in sorted(by_item.items())
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _finalize_assessment(session, assessment: Assessment, now: str | None = None) -> int:
    """把已结束测评中仍是 draft 的提交按服务器已保存答案最终化；幂等。

    提交时间统一取测评的有效截止时间 ends_at：自然截止时它就是计划结束时间，
    教师提前结束时 E040 会把它收缩到实际结束时间。没开始的名单成员不会在这里
    产生记录，仍算未提交。
    """
    now = now or _now()
    if assessment.state == STATE_DRAFT or not _ended(assessment, now):
        return 0
    drafts = list(
        session.scalars(
            select(Submission).where(
                Submission.assessment_id == assessment.id,
                Submission.status == STATUS_DRAFT,
            )
        )
    )
    if not drafts:
        return 0
    items = _items_of(session, assessment.id)
    deadline = assessment.ends_at or now
    for submission in drafts:
        _grade_into(session, submission, items, REASON_TIMEOUT, deadline)
    return len(drafts)


# ---- E035 /questions ----

@bp.get("/questions")
@roles_required("teacher")
def list_questions():
    page, page_size = pagination()
    session = db_session()
    user = current_user()
    stmt = select(Question).where(
        or_(Question.published == 1, Question.owner_id == user.id)
    )

    if (knowledge_id := request.args.get("knowledge_id")) is not None:
        try:
            wanted = int(knowledge_id)
        except (TypeError, ValueError):
            raise ApiError("INVALID_REQUEST", "knowledge_id 必须是正整数")
        stmt = stmt.join(
            QuestionKnowledge, QuestionKnowledge.question_id == Question.id
        ).where(QuestionKnowledge.knowledge_id == wanted)

    if (difficulty := request.args.get("difficulty")) is not None:
        try:
            wanted = int(difficulty)
        except (TypeError, ValueError):
            raise ApiError("INVALID_REQUEST", "difficulty 取值不合法", {"allowed": list(DIFFICULTIES)})
        if wanted not in DIFFICULTIES:
            raise ApiError("INVALID_REQUEST", "difficulty 取值不合法", {"allowed": list(DIFFICULTIES)})
        stmt = stmt.where(Question.difficulty == wanted)

    if (question_type := request.args.get("type")) is not None:
        if question_type not in QUESTION_TYPES:
            raise ApiError(
                "INVALID_REQUEST", "type 取值不合法", {"allowed": list(QUESTION_TYPES)}
            )
        stmt = stmt.where(Question.type == question_type)

    if (text := request.args.get("q")) is not None:
        if len(text) > SEARCH_MAX:
            raise ApiError("INVALID_REQUEST", f"q 最长 {SEARCH_MAX} 个字符")
        stmt = stmt.where(Question.stem_md.contains(text, autoescape=True))

    stmt = stmt.order_by(Question.created_at.desc(), Question.id.desc())
    rows, total = _paginate(session, stmt, page, page_size)
    knowledge = _knowledge_map(session, [row.id for row in rows])
    return success(
        [question_public(row, knowledge.get(row.id, [])) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@bp.post("/questions")
@roles_required("teacher")
def create_question():
    body = json_object(WRITE_FIELDS)
    session = db_session()
    question = Question(
        type=_type_field(body),
        stem_md=_stem_field(body),
        explanation_md=_explanation_field(body),
        difficulty=_difficulty_field(body),
        published=1 if _bool_field(body, "published") else 0,
        owner_id=current_user().id,
    )
    # 结构规则集中在 grading，避免同一套校验散落在接口里
    try:
        options = parse_options(body.get("options"), question.type)
        answer = parse_answer(body.get("answer"), question.type, [item["key"] for item in options])
    except FieldError as error:
        _translate(error)
    question.options_json = to_json(options)
    question.answer_json = to_json(answer)

    knowledge_ids = _knowledge_ids_field(body, session)
    session.add(question)
    session.flush()
    for knowledge_id in knowledge_ids:
        session.add(QuestionKnowledge(question_id=question.id, knowledge_id=knowledge_id))
    session.commit()
    return success(question_public(question, knowledge_ids), 201)


# ---- E036 /questions/{id} ----

@bp.get("/questions/<int:question_id>")
@roles_required("teacher")
def get_question(question_id: int):
    session = db_session()
    question = _readable_question(session, question_id)
    knowledge = _knowledge_map(session, [question.id])
    return success(question_public(question, knowledge.get(question.id, [])))


@bp.patch("/questions/<int:question_id>")
@roles_required("teacher")
def patch_question(question_id: int):
    body = json_object(("version",) + WRITE_FIELDS)
    session = db_session()
    question = _writable_question(session, question_id)

    version = _int_field(body, "version", minimum=1)
    if version != question.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "题目已被修改，请刷新后重试",
            {"expected_version": version, "current_version": question.version},
        )

    question_type = _type_field(body) if "type" in body else question.type
    if "stem_md" in body:
        question.stem_md = _stem_field(body)
    if "explanation_md" in body:
        question.explanation_md = _explanation_field(body)
    if "difficulty" in body:
        question.difficulty = _difficulty_field(body)
    if "published" in body:
        question.published = 1 if _bool_field(body, "published") else 0

    options = question.options
    answer = question.answer
    if "options" in body or "type" in body:
        try:
            options = parse_options(body.get("options", question.options), question_type)
        except FieldError as error:
            _translate(error)
    if "answer" in body or "type" in body or "options" in body:
        try:
            answer = parse_answer(body.get("answer", question.answer), question_type, [item["key"] for item in options])
        except FieldError as error:
            _translate(error)
    question.type = question_type
    question.options_json = to_json(options)
    question.answer_json = to_json(answer)

    knowledge_ids = None
    if "knowledge_ids" in body:
        knowledge_ids = _knowledge_ids_field(body, session)
        session.execute(
            delete(QuestionKnowledge).where(QuestionKnowledge.question_id == question.id)
        )
        for knowledge_id in knowledge_ids:
            session.add(QuestionKnowledge(question_id=question.id, knowledge_id=knowledge_id))

    question.version += 1
    session.commit()
    if knowledge_ids is None:
        knowledge_ids = _knowledge_map(session, [question.id]).get(question.id, [])
    return success(question_public(question, knowledge_ids))


# ---- E037 /assessments ----

def _write_items(session, assessment: Assessment, raw_items) -> None:
    """重建草稿条目并写入快照；发布时还会再冻结一次（E039）。"""
    if not isinstance(raw_items, list) or not (MIN_ITEMS <= len(raw_items) <= MAX_ITEMS):
        _fields_error("items", f"必须是 {MIN_ITEMS}—{MAX_ITEMS} 道题")
    question_ids: list[int] = []
    points: list[int] = []
    for entry in raw_items:
        if not isinstance(entry, dict):
            _fields_error("items", "每项必须是 {question_id,points}")
        unknown = set(entry) - {"question_id", "points"}
        if unknown:
            _fields_error("items", f"不支持字段：{','.join(sorted(unknown))}")
        question_id = entry.get("question_id")
        if not isinstance(question_id, int) or isinstance(question_id, bool):
            _fields_error("items", "question_id 必须是正整数")
        question_ids.append(question_id)
        points.append(_points_field(entry))
    if len(set(question_ids)) != len(question_ids):
        _fields_error("items", "同一测评不能重复引用同一道题")

    session.execute(delete(AssessmentItem).where(AssessmentItem.assessment_id == assessment.id))
    session.flush()
    for position, (question_id, point) in enumerate(zip(question_ids, points), start=1):
        question = _readable_question(session, question_id)
        knowledge_ids = _knowledge_map(session, [question.id]).get(question.id, [])
        titles = list(
            session.scalars(
                select(KnowledgePoint.title).where(KnowledgePoint.id.in_(knowledge_ids))
            )
        ) if knowledge_ids else []
        session.add(
            AssessmentItem(
                assessment_id=assessment.id,
                question_id=question_id,
                position=position,
                points=point,
                snapshot_json=to_json(build_snapshot(question, knowledge_ids, titles)),
            )
        )
    assessment.total_score = sum(points)


@bp.get("/assessments")
@login_required
def list_assessments():
    page, page_size = pagination()
    session = db_session()
    user = current_user()
    raw_class = request.args.get("class_id")
    class_id = None
    if raw_class is not None:
        try:
            class_id = int(raw_class)
        except (TypeError, ValueError):
            raise ApiError("INVALID_REQUEST", "class_id 必须是正整数")

    if user.role == "teacher":
        stmt = select(Assessment).where(Assessment.owner_id == user.id)
        if class_id:
            _require_class_teacher(session, class_id)
            stmt = stmt.where(Assessment.class_id == class_id)
    elif user.role == "student":
        stmt = select(Assessment).join(
            AssessmentRoster, AssessmentRoster.assessment_id == Assessment.id
        ).where(AssessmentRoster.student_id == user.id)
        if class_id:
            if class_id not in _active_class_ids(session, user.id):
                raise ApiError("NOT_FOUND", "班级不存在")
            stmt = stmt.where(Assessment.class_id == class_id)
    else:
        raise ApiError("FORBIDDEN", "管理员不参与课堂教学操作")

    if (kind := request.args.get("kind")) is not None:
        if kind not in ASSESSMENT_KINDS:
            raise ApiError("INVALID_REQUEST", "kind 取值不合法", {"allowed": list(ASSESSMENT_KINDS)})
        stmt = stmt.where(Assessment.kind == kind)

    stmt = stmt.order_by(Assessment.created_at.desc(), Assessment.id.desc())
    rows, total = _paginate(session, stmt, page, page_size)
    now = _now()
    # APIC：my_submission_id 只返回当前学生自己的记录 ID，教师为 null
    mine: dict[int, int] = {}
    if user.role == "student" and rows:
        mine = {
            submission.assessment_id: submission.id
            for submission in session.scalars(
                select(Submission).where(
                    Submission.student_id == user.id,
                    Submission.assessment_id.in_([row.id for row in rows]),
                )
            )
        }
    return success(
        [assessment_public(row, None, mine.get(row.id), now) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@bp.post("/assessments")
@roles_required("teacher")
def create_assessment():
    body = json_object(["class_id", "kind", "title", "items"])
    kind = body.get("kind")
    if kind not in CLASS_KINDS:
        _fields_error("kind", "quiz/homework/exam")
    class_id = _int_field(body, "class_id", minimum=1)
    title = text_field(body, "title", rule="1—100 个字符", min_len=1, max_len=100).strip()
    if not title:
        _fields_error("title", "1—100 个字符")

    session = db_session()
    _require_active_class(_require_class_teacher(session, class_id))
    assessment = Assessment(
        class_id=class_id,
        owner_id=current_user().id,
        kind=kind,
        title=title,
        state=STATE_DRAFT,
        origin="manual",
        total_score=0,
    )
    session.add(assessment)
    session.flush()
    _write_items(session, assessment, body.get("items"))
    session.commit()
    return success(assessment_public(assessment, _items_of(session, assessment.id), None, _now()), 201)


# ---- E038 /assessments/{id} ----

def _read_assessment(session, assessment_id: int):
    """返回 (assessment, items, my_submission_id)；无权访问按 404。"""
    assessment = session.get(Assessment, assessment_id)
    if assessment is None:
        raise ApiError("NOT_FOUND", "测评不存在")
    user = current_user()
    if user.role == "teacher":
        if assessment.owner_id != user.id:
            raise ApiError("NOT_FOUND", "测评不存在")
        return assessment, _items_of(session, assessment.id), None
    if user.role != "student":
        raise ApiError("FORBIDDEN", "管理员不参与课堂教学操作")
    if _roster_entry(session, assessment.id, user.id) is None:
        raise ApiError("NOT_FOUND", "测评不存在")
    submission = session.scalar(
        select(Submission).where(
            Submission.assessment_id == assessment.id, Submission.student_id == user.id
        )
    )
    return assessment, _items_of(session, assessment.id), submission.id if submission else None


@bp.get("/assessments/<int:assessment_id>")
@login_required
def get_assessment(assessment_id: int):
    session = db_session()
    assessment, items, my_submission_id = _read_assessment(session, assessment_id)
    now = _now()
    if current_user().role == "student":
        _finalize_assessment(session, assessment, now)
        session.commit()
    # 未到开始时间学生只获活动概要，不返回题目
    state = effective_state(assessment, now)
    if current_user().role == "student" and state == "upcoming":
        items = None
    return success(assessment_public(
        assessment, items, my_submission_id, now,
        include_teacher_snapshot=current_user().role == "teacher",
    ))


@bp.patch("/assessments/<int:assessment_id>")
@roles_required("teacher")
def patch_assessment(assessment_id: int):
    body = json_object(["version", "title", "items"])
    session = db_session()
    assessment = _own_assessment(session, assessment_id)
    if assessment.state != STATE_DRAFT:
        raise ApiError("STATE_CONFLICT", "只有草稿测评可以修改")

    version = _int_field(body, "version", minimum=1)
    if version != assessment.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "测评已被修改，请刷新后重试",
            {"expected_version": version, "current_version": assessment.version},
        )
    if not {"title", "items"} & set(body):
        raise ApiError("VALIDATION_ERROR", "没有可更新的字段")

    if "title" in body:
        title = text_field(body, "title", rule="1—100 个字符", min_len=1, max_len=100).strip()
        if not title:
            _fields_error("title", "1—100 个字符")
        assessment.title = title
    if "items" in body:
        _write_items(session, assessment, body.get("items"))
    assessment.version += 1
    session.commit()
    return success(assessment_public(assessment, _items_of(session, assessment.id), None, _now()))


# ---- E039 /assessments/{id}/publication ----

@bp.post("/assessments/<int:assessment_id>/publication")
@roles_required("teacher")
def publish_assessment(assessment_id: int):
    body = json_object(["version", "starts_at", "ends_at"])
    version = _int_field(body, "version", minimum=1)
    starts_at = _timestamp_field(body, "starts_at")
    ends_at = _timestamp_field(body, "ends_at")
    if ends_at <= starts_at:
        _fields_error("ends_at", "结束时间必须晚于开始时间")

    session = db_session()
    assessment = _own_assessment(session, assessment_id)
    _require_active_class(session.get(SchoolClass, assessment.class_id))
    if assessment.state != STATE_DRAFT:
        raise ApiError("STATE_CONFLICT", "只有草稿测评可以发布")
    if version != assessment.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "测评已被修改，请刷新后重试",
            {"expected_version": version, "current_version": assessment.version},
        )
    items = _items_of(session, assessment.id)
    if not items:
        raise ApiError("STATE_CONFLICT", "测评没有题目，不能发布")

    # 一个事务里冻结题目快照、分值、名单与起止时间
    for item in items:
        question = _question_or_404(session, item.question_id)
        knowledge_ids = _knowledge_map(session, [question.id]).get(question.id, [])
        titles = list(
            session.scalars(
                select(KnowledgePoint.title).where(KnowledgePoint.id.in_(knowledge_ids))
            )
        ) if knowledge_ids else []
        item.snapshot_json = to_json(build_snapshot(question, knowledge_ids, titles))

    session.execute(
        delete(AssessmentRoster).where(AssessmentRoster.assessment_id == assessment.id)
    )
    for student_id in _roster_student_ids(session, assessment.class_id):
        session.add(AssessmentRoster(assessment_id=assessment.id, student_id=student_id))

    assessment.starts_at = starts_at
    assessment.ends_at = ends_at
    assessment.total_score = sum(item.points for item in items)
    assessment.state = STATE_PUBLISHED
    assessment.version += 1
    session.commit()
    return success(assessment_public(assessment, _items_of(session, assessment.id), None, _now()))


# ---- E040 /assessments/{id}/closure ----

@bp.post("/assessments/<int:assessment_id>/closure")
@roles_required("teacher")
def close_assessment(assessment_id: int):
    body = json_object(["version"])
    version = _int_field(body, "version", minimum=1)
    session = db_session()
    assessment = _own_assessment(session, assessment_id)
    if assessment.state != STATE_PUBLISHED:
        raise ApiError("STATE_CONFLICT", "只有已发布测评可以结束")
    if version != assessment.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "测评已被修改，请刷新后重试",
            {"expected_version": version, "current_version": assessment.version},
        )
    assessment.state = STATE_CLOSED
    # 提前结束时把 ends_at 收缩到实际结束时间：ends_at 始终是有效截止时间，
    # 最终化的 submitted_at 与统计窗口都据此取值，不需要额外的关闭时间列。
    now = _now()
    if assessment.ends_at and assessment.ends_at > now:
        assessment.ends_at = now
    assessment.version += 1
    # 结束并最终化已开始草稿（ADR-006 的同一个幂等入口）
    _finalize_assessment(session, assessment, now)
    session.commit()
    return success(assessment_public(assessment, _items_of(session, assessment.id), None, now))


# ---- E041 /assessments/{id}/feedback-release ----

@bp.post("/assessments/<int:assessment_id>/feedback-release")
@roles_required("teacher")
def release_feedback(assessment_id: int):
    body = json_object(["version"])
    version = _int_field(body, "version", minimum=1)
    session = db_session()
    assessment = _own_assessment(session, assessment_id)

    if assessment.feedback_released:
        return success(assessment_public(assessment, None, None, _now()))  # 公开后幂等
    if assessment.state == STATE_DRAFT or not _ended(assessment, _now()):
        raise ApiError("STATE_CONFLICT", "测评尚未有效结束，不能公开反馈")
    if version != assessment.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "测评已被修改，请刷新后重试",
            {"expected_version": version, "current_version": assessment.version},
        )
    assessment.feedback_released = 1
    assessment.version += 1
    session.commit()
    return success(assessment_public(assessment, None, None, _now()))


# ---- E042 /practice-sessions ----

@bp.post("/practice-sessions")
@roles_required("student")
def create_practice_session():
    body = json_object(["knowledge_ids", "difficulty", "count", "mistake_question_ids"])
    using_filter = [key for key in PRACTICE_FILTER_KEYS if key in body]
    using_mistakes = "mistake_question_ids" in body
    if using_filter and using_mistakes:
        raise ApiError(
            "VALIDATION_ERROR", "过滤条件与错题重练只能二选一", {"fields": {"mistake_question_ids": "不能与其他过滤条件同时使用"}}
        )
    if not using_filter and not using_mistakes:
        raise ApiError("VALIDATION_ERROR", "必须提供过滤条件或错题题目")

    count = 5
    if "count" in body:
        value = body.get("count")
        if not isinstance(value, int) or isinstance(value, bool) or not (1 <= value <= 20):
            _fields_error("count", "必须是 1—20 的整数")
        count = value

    session = db_session()
    user = current_user()
    _require_student_work_access(session, None, user.id)
    blocked = _blocked_question_ids(session, user.id)
    stmt = select(Question).where(Question.published == 1)

    if using_mistakes:
        raw_ids = body.get("mistake_question_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            _fields_error("mistake_question_ids", "必须提供题目 ID 数组")
        ids = list(dict.fromkeys(raw_ids))
        if not all(isinstance(item, int) and not isinstance(item, bool) for item in ids):
            _fields_error("mistake_question_ids", "必须是题目 ID 数组")
        stmt = stmt.where(Question.id.in_(ids))
        title_prefix = "错题重练"
    else:
        title_prefix = "自练练习"
        if "knowledge_ids" in body:
            stmt = stmt.join(
                QuestionKnowledge, QuestionKnowledge.question_id == Question.id
            ).where(QuestionKnowledge.knowledge_id.in_(_int_list(body, "knowledge_ids")))
        if "difficulty" in body:
            stmt = stmt.where(Question.difficulty == _difficulty_field(body))

    candidates = [
        question
        for question in session.scalars(stmt.order_by(Question.id))
        if question.id not in blocked
    ]
    if len(candidates) < count:
        raise ApiError(
            "INFEASIBLE_PAPER",
            "题库可用题目不足",
            {
                "requested": count,
                "available": len(candidates),
                "constraints": [
                    {"kind": "count", "required": count, "available": len(candidates)}
                ],
            },
        )
    # 首版按题目 ID 升序取前 count 条，不声称随机组卷（组卷属 SPEC-011）
    chosen = candidates[:count]

    assessment = Assessment(
        class_id=None,
        owner_id=user.id,
        kind=KIND_PRACTICE,
        title=f"{title_prefix}（{_now()}）",
        state=STATE_PUBLISHED,
        starts_at=_now(),
        ends_at=_shift(PRACTICE_HOURS),
        feedback_released=1,
        total_score=len(chosen),
        origin="manual",
    )
    session.add(assessment)
    session.flush()
    session.add(AssessmentRoster(assessment_id=assessment.id, student_id=user.id))
    for position, question in enumerate(chosen, start=1):
        knowledge_ids = _knowledge_map(session, [question.id]).get(question.id, [])
        titles = list(
            session.scalars(
                select(KnowledgePoint.title).where(KnowledgePoint.id.in_(knowledge_ids))
            )
        ) if knowledge_ids else []
        session.add(
            AssessmentItem(
                assessment_id=assessment.id,
                question_id=question.id,
                position=position,
                points=1,
                snapshot_json=to_json(build_snapshot(question, knowledge_ids, titles)),
            )
        )
    session.commit()
    return success(assessment_public(assessment, _items_of(session, assessment.id), None, _now()), 201)


def _int_list(body: dict, name: str) -> list[int]:
    raw = body.get(name)
    if not isinstance(raw, list) or not raw:
        _fields_error(name, "必须提供 ID 数组")
    values = list(dict.fromkeys(raw))
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in values):
        _fields_error(name, "必须是 ID 数组")
    return values


# ---- E043 /assessments/{id}/submissions ----

@bp.post("/assessments/<int:assessment_id>/submissions")
@roles_required("student")
def start_submission(assessment_id: int):
    json_object([])
    session = db_session()
    user = current_user()
    assessment = session.get(Assessment, assessment_id)
    if assessment is None or _roster_entry(session, assessment_id, user.id) is None:
        raise ApiError("NOT_FOUND", "测评不存在")
    if assessment.state == STATE_DRAFT:
        raise ApiError("NOT_FOUND", "测评不存在")
    now = _now()

    # 「创建或返回本人原草稿」是无条件的：截止只拦住新建，不拦住取回自己的提交
    existing = session.scalar(
        select(Submission).where(
            Submission.assessment_id == assessment_id, Submission.student_id == user.id
        )
    )
    if existing is not None:
        return success(
            submission_public(
                existing, _answers_of(session, existing.id), bool(assessment.feedback_released)
            )
        )
    _require_student_work_access(session, assessment.class_id, user.id)
    if _ended(assessment, now):
        raise ApiError("DEADLINE_PASSED", "测评已结束，不能开始作答")
    if assessment.starts_at and now < assessment.starts_at:
        raise ApiError("STATE_CONFLICT", "测评尚未开始")

    submission = Submission(
        assessment_id=assessment_id,
        student_id=user.id,
        status=STATUS_DRAFT,
        started_at=now,
    )
    session.add(submission)
    created = True
    try:
        session.commit()
    except IntegrityError:
        # 并发开始：唯一约束保证只有一份，回读已存在的那份并返回 200
        session.rollback()
        submission = session.scalar(
            select(Submission).where(
                Submission.assessment_id == assessment_id, Submission.student_id == user.id
            )
        )
        if submission is None:
            raise
        created = False
    payload = submission_public(
        submission, _answers_of(session, submission.id), bool(assessment.feedback_released)
    )
    return success(payload, 201 if created else 200)


# ---- E044 /submissions/{id}/answers ----

@bp.put("/submissions/<int:submission_id>/answers")
@roles_required("student")
def save_answers(submission_id: int):
    body = json_object(["version", "answers"])
    version = _int_field(body, "version", minimum=1)
    session = db_session()
    submission = _submission_or_404(session, submission_id)
    if submission.student_id != current_user().id:
        raise ApiError("NOT_FOUND", "提交不存在")
    if submission.status == STATUS_SUBMITTED:
        raise ApiError("STATE_CONFLICT", "已提交的试卷不能再修改")
    if version != submission.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "试卷已被修改，请刷新后重试",
            {"expected_version": version, "current_version": submission.version},
        )
    assessment = session.get(Assessment, submission.assessment_id)
    _require_student_work_access(session, assessment.class_id, current_user().id)
    now = _now()
    if _ended(assessment, now):
        raise ApiError("DEADLINE_PASSED", "测评已结束，不能再保存答案")

    answers = body.get("answers")
    if not isinstance(answers, list):
        _fields_error("answers", "必须是数组")
    items = {item.id: item for item in _items_of(session, assessment.id)}
    prepared: list[tuple[int, list[str]]] = []
    seen_item_ids: set[int] = set()
    for entry in answers:
        if not isinstance(entry, dict):
            _fields_error("answers", "每项必须是 {item_id,selected}")
        unknown = set(entry) - {"item_id", "selected"}
        if unknown:
            _fields_error("answers", f"不支持字段：{','.join(sorted(unknown))}")
        item_id = entry.get("item_id")
        if isinstance(item_id, bool) or not isinstance(item_id, int) or item_id not in items:
            _fields_error("item_id", "该条目不属于本测评")
        if item_id in seen_item_ids:
            _fields_error("answers", "同一条目不能重复提交")
        seen_item_ids.add(item_id)
        snapshot = items[item_id].snapshot
        try:
            selected = validate_selected(entry.get("selected"), [opt.get("key") for opt in snapshot.get("options", [])])
        except FieldError as error:
            _translate(error)
        prepared.append((item_id, selected))

    for item_id, selected in prepared:
        answer = session.get(SubmissionAnswer, (submission.id, item_id))
        if answer is None:
            session.add(
                SubmissionAnswer(
                    submission_id=submission.id,
                    item_id=item_id,
                    selected_json=to_json(selected),
                    correct=None,
                    awarded_points=None,
                )
            )
        else:
            answer.selected_json = to_json(selected)
    submission.version += 1
    session.commit()
    return success(
        submission_public(
            submission, _answers_of(session, submission.id), bool(assessment.feedback_released)
        )
    )


# ---- E045 /submissions/{id}/finalization ----

@bp.post("/submissions/<int:submission_id>/finalization")
@roles_required("student")
def finalize_submission(submission_id: int):
    body = json_object(["version"])
    version = _int_field(body, "version", minimum=1)
    session = db_session()
    submission = _submission_or_404(session, submission_id)
    if submission.student_id != current_user().id:
        raise ApiError("NOT_FOUND", "提交不存在")
    if submission.status == STATUS_SUBMITTED:
        # 同已提交版本重试返回原结果，不重新判分
        assessment = session.get(Assessment, submission.assessment_id)
        return success(
            submission_public(
                submission,
                _answers_of(session, submission.id),
                bool(assessment.feedback_released),
            )
        )
    if version != submission.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "试卷已被修改，请刷新后重试",
            {"expected_version": version, "current_version": submission.version},
        )
    assessment = session.get(Assessment, submission.assessment_id)
    _require_student_work_access(session, assessment.class_id, current_user().id)
    now = _now()
    if _ended(assessment, now):
        raise ApiError("DEADLINE_PASSED", "测评已结束，不能提交")

    items = _items_of(session, assessment.id)
    _grade_into(session, submission, items, REASON_MANUAL, now)
    session.commit()
    return success(
        submission_public(
            submission, _answers_of(session, submission.id), bool(assessment.feedback_released)
        )
    )


# ---- E046 /submissions/{id}/result ----

@bp.get("/submissions/<int:submission_id>/result")
@login_required
def get_result(submission_id: int):
    session = db_session()
    submission = _submission_or_404(session, submission_id)
    user = current_user()
    assessment = session.get(Assessment, submission.assessment_id)

    is_owner_teacher = False
    if user.role == "teacher":
        if assessment.owner_id != user.id:
            raise ApiError("NOT_FOUND", "提交不存在")
        is_owner_teacher = True
    elif user.role == "student":
        if submission.student_id != user.id:
            raise ApiError("NOT_FOUND", "提交不存在")
        now = _now()
        if _finalize_assessment(session, assessment, now):
            session.commit()
    else:
        raise ApiError("FORBIDDEN", "管理员不参与课堂教学操作")

    items = _items_of(session, assessment.id)
    answers = {answer.item_id: answer for answer in _answers_of(session, submission.id)}
    # 反馈策略只约束学生：任课教师看自己班的提交不受公开时机限制
    available = submission.status == STATUS_SUBMITTED and (
        bool(assessment.feedback_released) or is_owner_teacher
    )

    payload_items = []
    for item in items:
        answer = answers.get(item.id)
        selected = answer.selected if answer else []
        if not available:
            payload_items.append({"item_id": item.id, "selected": selected})
            continue
        snapshot = item.snapshot
        payload_items.append(
            {
                "item_id": item.id,
                "selected": selected,
                "correct": bool(answer.correct) if answer and answer.correct is not None else False,
                "awarded_points": answer.awarded_points if answer else 0,
                "answer": snapshot.get("answer", []),
                "explanation_md": snapshot.get("explanation_md", ""),
                "knowledge_ids": snapshot.get("knowledge_ids", []),
            }
        )
    return success(
        {
            "submission_id": submission.id,
            "score": submission.score if available else None,
            "total_score": assessment.total_score,
            "feedback_available": available,
            "items": payload_items,
        }
    )


# ---- E057 /analytics/assessment ----

WINDOW_DEFAULT_DAYS = 30
WINDOW_MAX_DAYS = 366

CSV_COLUMNS = (
    "section",
    "assessment_id",
    "item_id",
    "knowledge_id",
    "range",
    "roster_count",
    "submitted_count",
    "blank_count",
    "submission_rate",
    "mean_percent",
    "answered_count",
    "unanswered_count",
    "correct_count",
    "correct_rate",
    "option_counts",
    "first_attempt_count",
    "first_correct_count",
    "first_accuracy",
    "count",
)


def _window_param(raw: str, name: str) -> datetime:
    if not isinstance(raw, str):
        raise ApiError("INVALID_REQUEST", f"{name} 必须是带 Z 的 UTC 时间")
    try:
        return _parse(raw)
    except ValueError:
        raise ApiError("INVALID_REQUEST", f"{name} 必须是带 Z 的 UTC 时间，如 2026-09-29T01:00:00Z")


def _stats_window() -> tuple[str, str]:
    """统计窗口 [from,to)：两者同时给出或都省略，默认最近 30 天，最长 366 天。

    默认的 to 取服务器当前时间（与其余判定同源），不是进程启动时间。
    """
    raw_from = request.args.get("from")
    raw_to = request.args.get("to")
    if (raw_from is None) != (raw_to is None):
        raise ApiError("INVALID_REQUEST", "from 与 to 必须同时给出或同时省略")
    if raw_from is None:
        # 存储时间精度为秒；默认窗口须包含「当前秒」刚提交的记录，
        # 同时保持 [from,to) 的右开语义。
        to_dt = _parse(_now()) + timedelta(seconds=1)
        from_dt = to_dt - timedelta(days=WINDOW_DEFAULT_DAYS)
    else:
        from_dt = _window_param(raw_from, "from")
        to_dt = _window_param(raw_to, "to")
    if to_dt <= from_dt:
        raise ApiError("INVALID_REQUEST", "to 必须晚于 from")
    if to_dt - from_dt > timedelta(days=WINDOW_MAX_DAYS):
        raise ApiError("INVALID_REQUEST", f"统计窗口最长 {WINDOW_MAX_DAYS} 天")
    return from_dt.strftime(STAMP_FORMAT), to_dt.strftime(STAMP_FORMAT)


def _stats_class_id() -> int:
    raw = request.args.get("class_id")
    if raw is None:
        raise ApiError("INVALID_REQUEST", "缺少必填查询参数 class_id")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError("INVALID_REQUEST", "class_id 必须是正整数")
    if value < 1:
        raise ApiError("INVALID_REQUEST", "class_id 必须是正整数")
    return value


def _stats_answer_rows(session, submission_ids):
    if not submission_ids:
        return {}
    rows = session.execute(
        select(
            SubmissionAnswer.submission_id,
            SubmissionAnswer.item_id,
            SubmissionAnswer.selected_json,
            SubmissionAnswer.correct,
        ).where(SubmissionAnswer.submission_id.in_(submission_ids))
    ).all()
    grouped: dict[int, dict[int, tuple[list[str], bool]]] = {}
    for submission_id, item_id, selected_json, correct in rows:
        grouped.setdefault(submission_id, {})[item_id] = (
            from_json(selected_json),
            bool(correct),
        )
    return grouped


def _first_attempt_rows(session, assessment_ids, question_ids, student_ids, window_from, window_to):
    """每一个 (学生, 题目) 的全历史最早已提交作答，再按 submitted_at 落窗筛选。"""
    if not question_ids or not student_ids:
        return []
    rows = session.execute(
        select(
            AssessmentItem.assessment_id,
            AssessmentItem.question_id,
            AssessmentItem.snapshot_json,
            Submission.id,
            Submission.student_id,
            Submission.submitted_at,
            SubmissionAnswer.correct,
        )
        .join(SubmissionAnswer, SubmissionAnswer.item_id == AssessmentItem.id)
        .join(Submission, Submission.id == SubmissionAnswer.submission_id)
        .where(
            AssessmentItem.question_id.in_(question_ids),
            Submission.student_id.in_(student_ids),
            Submission.status == STATUS_SUBMITTED,
            Submission.submitted_at.is_not(None),
        )
    ).all()
    earliest: dict[tuple[int, int], tuple[str, int, int, bool, list[int]]] = {}
    for assessment_id, question_id, snapshot_json, submission_id, student_id, submitted_at, correct in rows:
        key = (student_id, question_id)
        current = earliest.get(key)
        if current is None or (submitted_at, submission_id) < current[:2]:
            knowledge_ids = from_json(snapshot_json, default={}).get("knowledge_ids", [])
            earliest[key] = (submitted_at, submission_id, assessment_id, bool(correct), knowledge_ids)
    result = []
    selected_assessments = set(assessment_ids)
    for (_student_id, _question_id), (submitted_at, _submission_id, assessment_id, correct, knowledge_ids) in earliest.items():
        if assessment_id not in selected_assessments or not (window_from <= submitted_at < window_to):
            continue
        for knowledge_id in knowledge_ids:
            result.append((knowledge_id, correct))
    return result


@bp.get("/analytics/assessment")
@roles_required("teacher")
def assessment_analytics():
    window_from, window_to = _stats_window()
    class_id = _stats_class_id()
    session = db_session()
    _require_class_teacher(session, class_id)

    # 计入窗口的是「起止区间与 [from,to) 有交集的班级测评」：这样正在进行中的
    # 随堂测也能被教师讲评页看到实时进度，而窗口外的历史测评自然排除。
    stmt = select(Assessment).where(
        Assessment.class_id == class_id,
        Assessment.kind.in_(CLASS_KINDS),
        Assessment.state.in_((STATE_PUBLISHED, STATE_CLOSED)),
        Assessment.starts_at.is_not(None),
        Assessment.starts_at < window_to,
        or_(Assessment.ends_at.is_(None), Assessment.ends_at >= window_from),
    )
    if (raw_assessment := request.args.get("assessment_id")) is not None:
        try:
            wanted = int(raw_assessment)
        except (TypeError, ValueError):
            raise ApiError("INVALID_REQUEST", "assessment_id 必须是正整数")
        stmt = stmt.where(Assessment.id == wanted)
    assessments = list(session.scalars(stmt.order_by(Assessment.starts_at, Assessment.id)))
    assessment_ids = [item.id for item in assessments]

    # 统计查询进入同一个幂等最终化入口：先把已结束的草稿结算，再统计
    for assessment in assessments:
        if _finalize_assessment(session, assessment):
            session.commit()

    roster_map: dict[int, set[int]] = {aid: set() for aid in assessment_ids}
    if assessment_ids:
        for assessment_id, student_id in session.execute(
            select(AssessmentRoster.assessment_id, AssessmentRoster.student_id).where(
                AssessmentRoster.assessment_id.in_(assessment_ids)
            )
        ).all():
            roster_map[assessment_id].add(student_id)

    submissions: list[Submission] = []
    if assessment_ids:
        submissions = list(
            session.scalars(
                select(Submission).where(
                    Submission.assessment_id.in_(assessment_ids),
                    Submission.status == STATUS_SUBMITTED,
                    Submission.submitted_at >= window_from,
                    Submission.submitted_at < window_to,
                )
            )
        )
    answers_by_submission = _stats_answer_rows(session, [row.id for row in submissions])

    submissions_by_assessment: dict[int, list[Submission]] = {}
    for submission in submissions:
        if submission.student_id in roster_map.get(submission.assessment_id, set()):
            submissions_by_assessment.setdefault(submission.assessment_id, []).append(submission)

    def is_blank(submission_id: int) -> bool:
        """白卷：已提交但所有条目都是空答案（与漏答分开核算）。"""
        return not any(
            selected for selected, _correct in answers_by_submission.get(submission_id, {}).values()
        )

    assessment_rows = []
    all_percents: list[float] = []
    for assessment in assessments:
        rows = submissions_by_assessment.get(assessment.id, [])
        percents = [percent_of(row.score, assessment.total_score) for row in rows]
        all_percents.extend([value for value in percents if value is not None])
        assessment_rows.append(
            summarize_assessment(
                assessment_id=assessment.id,
                roster_count=len(roster_map[assessment.id]),
                percents=percents,
                blank_count=sum(1 for row in rows if is_blank(row.id)),
            )
        )

    items = _items_of_many(session, assessment_ids)
    item_rows = []
    for item in items:
        responses = []
        for submission in submissions_by_assessment.get(item.assessment_id, []):
            entry = answers_by_submission.get(submission.id, {}).get(item.id)
            responses.append(entry if entry is not None else ([], False))
        item_rows.append(summarize_item(item_id=item.id, responses=responses))

    question_ids = sorted({item.question_id for item in items})
    student_ids = sorted({sid for ids in roster_map.values() for sid in ids})
    knowledge_rows = summarize_knowledge(
        _first_attempt_rows(session, assessment_ids, question_ids, student_ids, window_from, window_to)
    )
    buckets = score_bucket_rows(all_percents)

    payload = {
        "window": {"from": window_from, "to": window_to},
        "assessments": assessment_rows,
        "items": item_rows,
        "knowledge": knowledge_rows,
        "score_buckets": buckets,
    }
    if request.args.get("format") == "csv":
        return _stats_csv(payload)
    if request.args.get("format") not in (None, "json"):
        raise ApiError("INVALID_REQUEST", "format 只支持 json 或 csv")
    return success(payload)


def _items_of_many(session, assessment_ids) -> list[AssessmentItem]:
    if not assessment_ids:
        return []
    return list(
        session.scalars(
            select(AssessmentItem)
            .where(AssessmentItem.assessment_id.in_(assessment_ids))
            .order_by(AssessmentItem.assessment_id, AssessmentItem.position)
        )
    )


def _stats_csv(payload):
    """CSV 明细：每个块展开成自己的 section，列固定为 CSV_COLUMNS。"""
    rows: list[dict] = []
    for block in payload["assessments"]:
        rows.append({"section": "assessment", **block})
    for block in payload["items"]:
        rows.append(
            {
                "section": "item",
                **block,
                "option_counts": ";".join(
                    f"{key}={value}" for key, value in sorted(block["option_counts"].items())
                ),
            }
        )
    for block in payload["knowledge"]:
        rows.append({"section": "knowledge", **block})
    for block in payload["score_buckets"]:
        rows.append({"section": "score_bucket", **block})
    body = to_csv(CSV_COLUMNS, rows)
    response = Response(body, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=assessment-stats.csv"
    return response


# ---- E047 /me/mistakes ----

@bp.get("/me/mistakes")
@roles_required("student")
def list_mistakes():
    page, page_size = pagination()
    session = db_session()
    user = current_user()

    # 只统计已公开反馈的已提交答案：未公开的测评不透露对错，避免旁路泄露
    stmt = (
        select(
            AssessmentItem.question_id,
            Submission.submitted_at,
            SubmissionAnswer.correct,
            AssessmentItem.snapshot_json,
        )
        .join(SubmissionAnswer, SubmissionAnswer.item_id == AssessmentItem.id)
        .join(Submission, Submission.id == SubmissionAnswer.submission_id)
        .join(Assessment, Assessment.id == Submission.assessment_id)
        .where(
            Submission.student_id == user.id,
            Submission.status == STATUS_SUBMITTED,
            Assessment.feedback_released == 1,
        )
        .order_by(Submission.submitted_at.desc(), Submission.id.desc())
    )
    rows = session.execute(stmt).all()

    knowledge_filter = request.args.get("knowledge_id")
    if knowledge_filter is not None:
        try:
            knowledge_filter = int(knowledge_filter)
        except (TypeError, ValueError):
            raise ApiError("INVALID_REQUEST", "knowledge_id 必须是正整数")

    resolved_filter = None
    if (raw := request.args.get("resolved")) is not None:
        if raw not in {"true", "false"}:
            raise ApiError("INVALID_REQUEST", "resolved 取值不合法", {"allowed": ["true", "false"]})
        resolved_filter = raw == "true"

    blocked = _blocked_question_ids(session, user.id)
    latest: dict[int, dict] = {}
    for question_id, submitted_at, correct, snapshot_json in rows:
        if question_id in blocked:
            continue  # 未公开反馈的题目不出现在错题视图
        entry = latest.get(question_id)
        if entry is None:
            # 行已按提交时间倒序，第一条即最近一次已公开的作答
            entry = {
                "question_id": question_id,
                "last_wrong_at": submitted_at if not correct else None,
                "latest_correct": bool(correct),
                "knowledge_ids": from_json(snapshot_json, default={}).get("knowledge_ids", []),
            }
            latest[question_id] = entry
        elif entry["last_wrong_at"] is None and not correct:
            entry["last_wrong_at"] = submitted_at

    published = set(
        session.scalars(select(Question.id).where(Question.published == 1))
    )
    items = []
    for entry in latest.values():
        if knowledge_filter is not None and knowledge_filter not in entry["knowledge_ids"]:
            continue
        if resolved_filter is not None and entry["latest_correct"] != resolved_filter:
            continue
        if entry["last_wrong_at"] is None and entry["latest_correct"]:
            continue  # 从未答错且最近一次答对：不是错题
        items.append(
            {
                "question_id": entry["question_id"],
                "last_wrong_at": entry["last_wrong_at"],
                "latest_correct": entry["latest_correct"],
                "knowledge_ids": entry["knowledge_ids"],
                "review_available": entry["question_id"] in published,
            }
        )

    items.sort(key=lambda row: (row["last_wrong_at"] or "", row["question_id"]), reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return success(items[start : start + page_size], page=page, page_size=page_size, total=total)
