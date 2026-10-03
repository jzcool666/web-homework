"""E065 GET /me/recommendations：个性化复习推荐（SPEC-015 第 4 节）。

只读、实时计算，不新建画像表、不缓存推荐结果（DBD 第 5 节末段）。三路信号都只取
**本人**记录：

- 错题：本人在已公开反馈的测评/自练中的**全历史首答**（口径同 SPEC-009 的 E047
  与 SPEC-010 的 E057：同一题取最早一次已提交作答，且只有 feedback_released=1
  才计入——学生自己都还看不到对错的测评，不能拿来当推荐依据）。
- 进度：SPEC-006 的 `learning_progress`（只有明确记录才算，缺失不当失败）。
- 实验：SPEC-014/013 的 `experiment_attempts` 按实验挂载的知识点聚合通过率。

屏蔽题复用 SPEC-009 的既有实现 `api_assessment.blocked_question_ids`（本班已发布
或已结束但尚未公开反馈的班级测评所用题）；把「首答聚合」抽成公共函数是评审记录的
D7 清理项，本模块不顺手改他人模块。
"""

from __future__ import annotations

from flask import Blueprint, request
from sqlalchemy import select

from .api_assessment import blocked_question_ids
from .auth import current_user, roles_required
from .errors import ApiError, success
from .models_assessment import (
    STATUS_SUBMITTED,
    Assessment,
    AssessmentItem,
    Question,
    QuestionKnowledge,
    Submission,
    SubmissionAnswer,
    from_json,
)
from .models_attempt import ExperimentAttempt
from .models_content import Chapter, KnowledgeEdge, KnowledgePoint, LearningProgress
from .models_experiment import Experiment
from .recommendation_service import (
    ALGORITHM_VERSION,
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MIN_LIMIT,
    rank,
)
from .store import db_session

bp = Blueprint("recommendation", __name__)


def _limit_arg() -> int:
    """limit 默认 5；非整数是格式错误（400），超出 1—10 是字段错误（422）。"""
    raw = request.args.get("limit")
    if raw is None or raw == "":
        return DEFAULT_LIMIT
    try:
        value = int(raw)
    except ValueError:
        raise ApiError("INVALID_REQUEST", "limit 必须是整数") from None
    if not (MIN_LIMIT <= value <= MAX_LIMIT):
        raise ApiError(
            "VALIDATION_ERROR",
            "请求字段不合法",
            {"fields": {"limit": f"必须是 {MIN_LIMIT}—{MAX_LIMIT} 的整数"}},
        )
    return value


def _published_points(session) -> list[dict]:
    rows = session.execute(
        select(
            KnowledgePoint.id,
            KnowledgePoint.title,
            KnowledgePoint.chapter_id,
            KnowledgePoint.sort_order,
            Chapter.sort_order,
        )
        .join(Chapter, Chapter.id == KnowledgePoint.chapter_id)
        .where(KnowledgePoint.published == 1)
        .order_by(Chapter.sort_order, KnowledgePoint.sort_order, KnowledgePoint.id)
    ).all()
    return [
        {
            "id": row[0],
            "title": row[1],
            "chapter_id": row[2],
            "sort_order": row[3],
            "chapter_sort": row[4],
        }
        for row in rows
    ]


def _published_edges(session, published_ids) -> list[tuple[int, int]]:
    known = set(published_ids)
    rows = session.execute(
        select(KnowledgeEdge.prerequisite_id, KnowledgeEdge.target_id)
    ).all()
    return sorted({(p, t) for p, t in rows if p in known and t in known})


def _progress_of(session, student_id: int) -> dict[int, int]:
    rows = session.execute(
        select(LearningProgress.knowledge_id, LearningProgress.completed).where(
            LearningProgress.student_id == student_id
        )
    ).all()
    return {knowledge_id: int(completed) for knowledge_id, completed in rows}


def _first_answers(session, student_id: int):
    """本人已公开反馈的首答：返回 (每题是否答对, 每条首答的 (知识点, 是否正确))。"""
    rows = session.execute(
        select(
            AssessmentItem.question_id,
            AssessmentItem.snapshot_json,
            Submission.submitted_at,
            Submission.id,
            SubmissionAnswer.correct,
        )
        .join(SubmissionAnswer, SubmissionAnswer.item_id == AssessmentItem.id)
        .join(Submission, Submission.id == SubmissionAnswer.submission_id)
        .join(Assessment, Assessment.id == Submission.assessment_id)
        .where(
            Submission.student_id == student_id,
            Submission.status == STATUS_SUBMITTED,
            Submission.submitted_at.is_not(None),
            Assessment.feedback_released == 1,
        )
    ).all()

    earliest: dict[int, tuple[str, int, bool, list[int]]] = {}
    for question_id, snapshot_json, submitted_at, submission_id, correct in rows:
        current = earliest.get(question_id)
        if current is None or (submitted_at, submission_id) < current[:2]:
            knowledge_ids = from_json(snapshot_json, default={}).get("knowledge_ids", [])
            earliest[question_id] = (
                submitted_at,
                submission_id,
                bool(correct),
                list(knowledge_ids),
            )

    per_knowledge: dict[int, list[int]] = {}
    correct_questions: set[int] = set()
    for question_id, (_stamp, _sid, correct, knowledge_ids) in earliest.items():
        if correct:
            correct_questions.add(question_id)
        for knowledge_id in knowledge_ids:
            bucket = per_knowledge.setdefault(knowledge_id, [0, 0])
            bucket[0] += 0 if correct else 1
            bucket[1] += 1
    return per_knowledge, correct_questions


def _experiment_stats(session, student_id: int) -> dict[int, list[int]]:
    rows = session.execute(
        select(Experiment.knowledge_id, ExperimentAttempt.passed)
        .join(Experiment, Experiment.id == ExperimentAttempt.experiment_id)
        .where(ExperimentAttempt.student_id == student_id)
    ).all()
    stats: dict[int, list[int]] = {}
    for knowledge_id, passed in rows:
        bucket = stats.setdefault(knowledge_id, [0, 0])
        bucket[0] += 0 if passed else 1
        bucket[1] += 1
    return stats


def _practice_questions(session, blocked_ids, correct_questions) -> dict[int, list[dict]]:
    """每个已发布知识点的候选练习：已发布、未屏蔽、本人尚未答对，按题目 ID 升序。"""
    rows = session.execute(
        select(Question.id, Question.stem_md, QuestionKnowledge.knowledge_id)
        .join(QuestionKnowledge, QuestionKnowledge.question_id == Question.id)
        .where(Question.published == 1)
        .order_by(Question.id)
    ).all()
    by_point: dict[int, list[dict]] = {}
    for question_id, stem, knowledge_id in rows:
        if question_id in blocked_ids or question_id in correct_questions:
            continue
        by_point.setdefault(knowledge_id, []).append({"id": question_id, "title": stem})
    return by_point


@bp.get("/me/recommendations")
@roles_required("student")
def my_recommendations():
    limit = _limit_arg()
    session = db_session()
    student_id = current_user().id

    points = _published_points(session)
    edges = _published_edges(session, [point["id"] for point in points])
    progress = _progress_of(session, student_id)
    per_knowledge, correct_questions = _first_answers(session, student_id)
    experiments = _experiment_stats(session, student_id)
    questions = _practice_questions(
        session, blocked_question_ids(session, student_id), correct_questions
    )

    signals: dict[int, dict] = {}
    for point in points:
        point_id = point["id"]
        errors, attempts = per_knowledge.get(point_id, (0, 0))
        failures, experiment_attempts = experiments.get(point_id, (0, 0))
        entry: dict = {}
        if point_id in progress:
            entry["completed"] = progress[point_id]
        if attempts:
            entry["attempts"] = attempts
            entry["errors"] = errors
        if experiment_attempts:
            entry["experiment_attempts"] = experiment_attempts
            entry["experiment_failures"] = failures
        if entry:
            signals[point_id] = entry

    items = rank(
        points=points,
        edges=edges,
        signals_by_point=signals,
        questions_by_point=questions,
        limit=limit,
    )
    return success({"algorithm_version": ALGORITHM_VERSION, "items": items})
