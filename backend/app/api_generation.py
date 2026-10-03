"""E062 POST /paper-generations：约束智能组卷（SPEC-011）。

规则要点（SPEC-011 第 4 节）：
- 只在已发布题库（最多 500 题）中选题；题量、每难度配额精确、每知识点覆盖
  ≥ 下限、同题不重复。难度配额之和必须等于 count。
- 目标优先级 0.8*p_i + 0.2*seed 随机项，p_i 取目标班级已提交首答的拉普拉斯
  平滑错误率；求解为确定性分支定界，相同 seed 与相同历史必然同结果。
- 无解与超时严格分开：证明无解 → 422 INFEASIBLE_PAPER；限时仍无解 →
  503 SOLVER_TIMEOUT。求解参数与所选题号写入 assessments.generation_json。
"""

from __future__ import annotations

from flask import Blueprint, current_app
from sqlalchemy import select

from .auth import current_user, roles_required
from .errors import ApiError, success
from .generation_service import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    DIFFICULTY_KEYS,
    MAX_CANDIDATES,
    MAX_KNOWLEDGE_MINIMUMS,
    TIME_LIMIT_SECONDS,
    Infeasible,
    SolverTimeout,
    build_coverage,
    candidate_fingerprint,
    compute_priorities,
    solve,
)
from .grading import build_snapshot
from .models import Enrollment, SchoolClass, User
from .models_assessment import (
    CLASS_KINDS,
    MAX_ITEMS,
    MIN_ITEMS,
    STATE_DRAFT,
    STATUS_SUBMITTED,
    Assessment,
    AssessmentItem,
    Question,
    QuestionKnowledge,
    Submission,
    SubmissionAnswer,
    to_json,
)
from .models_content import KnowledgePoint
from .store import db_session
from .validation import json_object, text_field

bp = Blueprint("generation", __name__)

DEFAULT_POINTS = 10


def _fields_error(field: str, rule: str):
    raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {field: rule}})


def _int_field(
    body: dict, name: str, *, minimum: int | None = None, maximum: int | None = None
) -> int:
    value = body.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        _fields_error(name, "必须是整数")
    if minimum is not None and value < minimum:
        _fields_error(name, f"必须≥{minimum}")
    if maximum is not None and value > maximum:
        _fields_error(name, f"必须≤{maximum}")
    return value


def _difficulty_counts_field(body: dict, count: int) -> dict[int, int]:
    raw = body.get("difficulty_counts")
    if not isinstance(raw, dict):
        _fields_error("difficulty_counts", "必须是 {easy,medium,hard} 对象")
    unknown = sorted(set(raw) - set(DIFFICULTY_KEYS))
    if unknown:
        _fields_error("difficulty_counts", f"不支持的键：{','.join(unknown)}")
    counts: dict[int, int] = {}
    for name, difficulty in DIFFICULTY_KEYS.items():
        value = raw.get(name, 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            _fields_error("difficulty_counts", "每项必须是非负整数")
        counts[difficulty] = value
    if sum(counts.values()) != count:
        _fields_error("difficulty_counts", f"难度配额之和必须等于 count（{count}）")
    return counts


def _knowledge_minimums_field(body: dict) -> dict[int, int]:
    raw = body.get("knowledge_minimums")
    if not isinstance(raw, list):
        _fields_error("knowledge_minimums", "必须是数组")
    if len(raw) > MAX_KNOWLEDGE_MINIMUMS:
        _fields_error("knowledge_minimums", f"最多 {MAX_KNOWLEDGE_MINIMUMS} 个知识点")
    minimums: dict[int, int] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            _fields_error("knowledge_minimums", "每项必须是 {knowledge_id,min_count}")
        unknown = set(entry) - {"knowledge_id", "min_count"}
        if unknown:
            _fields_error("knowledge_minimums", f"不支持字段：{','.join(sorted(unknown))}")
        knowledge_id = entry.get("knowledge_id")
        if not isinstance(knowledge_id, int) or isinstance(knowledge_id, bool) or knowledge_id < 1:
            _fields_error("knowledge_minimums", "knowledge_id 必须是正整数")
        if knowledge_id in minimums:
            _fields_error("knowledge_minimums", "同一个知识点不能重复")
        min_count = entry.get("min_count")
        if not isinstance(min_count, int) or isinstance(min_count, bool) or min_count < 1:
            _fields_error("knowledge_minimums", "min_count 必须是正整数")
        minimums[knowledge_id] = min_count
    return minimums


def _require_class_teacher(session, class_id: int) -> SchoolClass:
    school_class = session.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_user().id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _load_candidates(session) -> list[dict]:
    """已发布可用题，按 ID 升序取前 500 道（固定候选集，保证可复现）。"""
    questions = list(
        session.scalars(
            select(Question).where(Question.published == 1).order_by(Question.id).limit(MAX_CANDIDATES)
        )
    )
    if not questions:
        return []
    ids = [question.id for question in questions]
    tags: dict[int, list[int]] = {qid: [] for qid in ids}
    for question_id, knowledge_id in session.execute(
        select(QuestionKnowledge.question_id, QuestionKnowledge.knowledge_id).where(
            QuestionKnowledge.question_id.in_(ids)
        )
    ).all():
        tags[question_id].append(knowledge_id)
    return [
        {
            "id": question.id,
            "version": question.version,
            "difficulty": question.difficulty,
            "knowledge_ids": sorted(tags.get(question.id, [])),
        }
        for question in questions
    ]


def _class_student_ids(session, class_id: int) -> list[int]:
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


def _history_stats(session, question_ids, student_ids) -> dict[int, tuple[int, int]]:
    """目标班级已提交首答的 (错误数, 机会数)，按题目聚合。

    首答 = 该学生该题目全历史最早一次已提交作答；机会数按学生计一次。
    """
    if not question_ids or not student_ids:
        return {}
    rows = session.execute(
        select(
            AssessmentItem.question_id,
            Submission.student_id,
            Submission.submitted_at,
            Submission.id,
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
    earliest: dict[tuple[int, int], tuple[str, int, bool]] = {}
    for question_id, student_id, submitted_at, submission_id, correct in rows:
        key = (student_id, question_id)
        current = earliest.get(key)
        if current is None or (submitted_at, submission_id) < current[:2]:
            earliest[key] = (submitted_at, submission_id, bool(correct))
    stats: dict[int, list[int]] = {}
    for (_student_id, question_id), (_stamp, _sid, correct) in earliest.items():
        bucket = stats.setdefault(question_id, [0, 0])
        bucket[0] += 0 if correct else 1
        bucket[1] += 1
    return {qid: (errors, opportunities) for qid, (errors, opportunities) in stats.items()}


def _require_knowledge_points(session, knowledge_minimums) -> None:
    ids = set(knowledge_minimums)
    if not ids:
        return
    found = set(session.scalars(select(KnowledgePoint.id).where(KnowledgePoint.id.in_(ids))))
    missing = sorted(ids - found)
    if missing:
        _fields_error("knowledge_minimums", f"知识点不存在：{','.join(str(i) for i in missing)}")


def _persist_draft(session, *, class_id, owner_id, kind, title, selected_ids, points, generation) -> int:
    assessment = Assessment(
        class_id=class_id,
        owner_id=owner_id,
        kind=kind,
        title=title,
        state=STATE_DRAFT,
        origin="generated",
        total_score=0,
        generation_json=to_json(generation),
    )
    session.add(assessment)
    session.flush()

    knowledge_map: dict[int, list[int]] = {}
    title_map: dict[int, str] = {}
    if selected_ids:
        for question_id, knowledge_id in session.execute(
            select(QuestionKnowledge.question_id, QuestionKnowledge.knowledge_id).where(
                QuestionKnowledge.question_id.in_(selected_ids)
            )
        ).all():
            knowledge_map.setdefault(question_id, []).append(knowledge_id)
        all_knowledge = {kid for kids in knowledge_map.values() for kid in kids}
        if all_knowledge:
            for knowledge_id, topic in session.execute(
                select(KnowledgePoint.id, KnowledgePoint.title).where(
                    KnowledgePoint.id.in_(all_knowledge)
                )
            ).all():
                title_map[knowledge_id] = topic

    for position, question_id in enumerate(selected_ids, start=1):
        question = session.get(Question, question_id)
        knowledge_ids = sorted(knowledge_map.get(question_id, []))
        session.add(
            AssessmentItem(
                assessment_id=assessment.id,
                question_id=question_id,
                position=position,
                points=points,
                snapshot_json=to_json(
                    build_snapshot(question, knowledge_ids, [title_map[k] for k in knowledge_ids])
                ),
            )
        )
    assessment.total_score = points * len(selected_ids)
    session.commit()
    return assessment.id


@bp.post("/paper-generations")
@roles_required("teacher")
def generate_paper():
    body = json_object(
        ("class_id", "title", "kind", "count", "difficulty_counts", "knowledge_minimums", "seed")
    )
    kind = body.get("kind")
    if kind not in CLASS_KINDS:
        _fields_error("kind", "quiz/homework/exam")
    class_id = _int_field(body, "class_id", minimum=1)
    title = text_field(body, "title", rule="1—100 个字符", min_len=1, max_len=100).strip()
    if not title:
        _fields_error("title", "1—100 个字符")
    count = _int_field(body, "count", minimum=MIN_ITEMS, maximum=MAX_ITEMS)
    difficulty_counts = _difficulty_counts_field(body, count)
    knowledge_minimums = _knowledge_minimums_field(body)
    seed = _int_field(body, "seed", minimum=-(2**31), maximum=2**31 - 1)

    session = db_session()
    school_class = _require_class_teacher(session, class_id)
    if not school_class.active:
        raise ApiError("STATE_CONFLICT", "班级已停用，不能发起新的测评活动")

    _require_knowledge_points(session, knowledge_minimums)
    candidates = _load_candidates(session)
    student_ids = _class_student_ids(session, class_id)
    history = _history_stats(session, [item["id"] for item in candidates], student_ids)
    priorities = compute_priorities(candidates, history, seed)

    time_limit = float(current_app.config.get("PAPER_SOLVER_TIME_LIMIT_SECONDS", TIME_LIMIT_SECONDS))
    try:
        selected_ids, solver_status, elapsed = solve(
            candidates, difficulty_counts, knowledge_minimums, priorities, time_limit=time_limit
        )
    except Infeasible as exc:
        raise ApiError("INFEASIBLE_PAPER", "题库无法满足当前条件", {"constraints": exc.constraints})
    except SolverTimeout as exc:
        raise ApiError(
            "SOLVER_TIMEOUT",
            "组卷求解超时，请稍后重试或放宽约束",
            {"time_limit_seconds": time_limit},
        ) from exc

    coverage = build_coverage(selected_ids, candidates, knowledge_minimums)
    difficulty_out = {
        name: difficulty_counts[difficulty] for name, difficulty in DIFFICULTY_KEYS.items()
    }
    generation = {
        "algorithm": ALGORITHM_NAME,
        "algorithm_version": ALGORITHM_VERSION,
        "solver_status": solver_status,
        "seed": seed,
        "time_limit_seconds": time_limit,
        "elapsed_seconds": round(elapsed, 4),
        "candidate_count": len(candidates),
        "candidate_fingerprint": candidate_fingerprint(candidates),
        "inputs": {
            "count": count,
            "difficulty_counts": difficulty_out,
            "knowledge_minimums": [
                {"knowledge_id": kid, "min_count": knowledge_minimums[kid]}
                for kid in sorted(knowledge_minimums)
            ],
        },
        "selected_ids": selected_ids,
        "priorities": {str(qid): round(priorities[qid], 6) for qid in selected_ids},
        "coverage": coverage,
        "difficulty_counts": difficulty_out,
    }
    assessment_id = _persist_draft(
        session,
        class_id=class_id,
        owner_id=current_user().id,
        kind=kind,
        title=title,
        selected_ids=selected_ids,
        points=DEFAULT_POINTS,
        generation=generation,
    )

    return success(
        {
            "assessment_id": assessment_id,
            "selected_ids": selected_ids,
            "solver_status": solver_status,
            "coverage": coverage,
            "difficulty_counts": difficulty_out,
            "seed": seed,
        },
        201,
    )
