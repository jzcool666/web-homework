"""E063/E064 学习预警与分组（SPEC-004）。

- 权限：仅教师，且只能操作本人任教班级；跨班 404、学生与管理员 403、匿名 401。
- E063 显式生成一批快照；E064 只读取最近同窗口的**完整批次**，没有批次就返回
  空数组，不自动假造数据（APIC 第 7 节、DBD 第 7 节）。
- 三个因素的数据都引用既有统计口径而不是另算一套：出勤用 SPEC-003 的
  `summarize_attendance`，进度用 SPEC-006 的 `summarize_progress`，首答正确率
  按 SPEC-010「全历史最早已提交作答、再按 submitted_at 落窗」的同一条规则聚合，
  只是按学生分组（SPEC-010 的私有函数会丢掉 student_id，因此这里保留它）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, request
from sqlalchemy import select

from .api_attendance import settle_task
from .auth import current_user, roles_required
from .errors import ApiError, success
from .models import Enrollment, SchoolClass, User, now_utc
from .models_assessment import (
    CLASS_KINDS,
    STATUS_SUBMITTED,
    STATE_CLOSED,
    STATE_PUBLISHED,
    Assessment,
    AssessmentItem,
    Submission,
    SubmissionAnswer,
)
from .models_attendance import AttendanceRecord, AttendanceTask
from .models_content import KnowledgePoint, LearningProgress
from .models_experiment import load_json, dump_json
from .models_warning import WarningSnapshot
from .stats_assessment import ratio
from .stats_attendance import summarize_attendance
from .stats_learning import summarize_progress
from .store import db_session
from .validation import json_object, pagination
from .warning_service import (
    ALGORITHM_VERSION,
    DISCLAIMER,
    MIN_ACCURACY_ATTEMPTS,
    MIN_CLUSTER_STUDENTS,
    summarize_warnings,
)

bp = Blueprint("warning", __name__)

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 366
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _parse(raw: str) -> datetime:
    return datetime.strptime(raw, STAMP_FORMAT).replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _window_param(raw, name: str) -> datetime:
    if not isinstance(raw, str):
        raise ApiError(
            "VALIDATION_ERROR", "请求字段不合法", {"fields": {name: "必填且为字符串"}}
        )
    try:
        return _parse(raw)
    except ValueError:
        raise ApiError(
            "VALIDATION_ERROR",
            "请求字段不合法",
            {"fields": {name: "必须是带 Z 的 UTC 时间，如 2026-09-29T00:00:00Z"}},
        ) from None


def _resolve_window(raw_from, raw_to) -> tuple[str, str]:
    """窗口 [from,to)：缺省为最近30个UTC自然日，最长366天。"""
    if (raw_from is None) != (raw_to is None):
        raise ApiError("INVALID_REQUEST", "from 与 to 必须同时给出或同时省略")
    if raw_from is None:
        to_dt = _now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        from_dt = to_dt - timedelta(days=DEFAULT_WINDOW_DAYS)
    else:
        from_dt = _window_param(raw_from, "from")
        to_dt = _window_param(raw_to, "to")
    if to_dt <= from_dt:
        raise ApiError("INVALID_REQUEST", "to 必须晚于 from")
    if to_dt - from_dt > timedelta(days=MAX_WINDOW_DAYS):
        raise ApiError("INVALID_REQUEST", f"统计窗口最长 {MAX_WINDOW_DAYS} 天")
    return from_dt.strftime(STAMP_FORMAT), to_dt.strftime(STAMP_FORMAT)


def _class_id_from(raw, *, from_body: bool) -> int:
    """查询串里缺失/非法按 400（与 E055—E057 一致）；请求体字段错误按 422。"""
    if isinstance(raw, str) and raw.isdigit() and int(raw) > 0:
        return int(raw)
    if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
        return raw
    if from_body:
        raise ApiError(
            "VALIDATION_ERROR", "请求字段不合法", {"fields": {"class_id": "必须是正整数"}}
        )
    raise ApiError("INVALID_REQUEST", "class_id 必须是正整数")


def _require_class_teacher(session, class_id: int) -> SchoolClass:
    school_class = session.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_user().id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _roster(session, class_id: int) -> list[int]:
    """当前有效在册学生：退班学生不再参与新快照。"""
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


def _settle_ended_tasks(session, class_id: int) -> None:
    tasks = list(
        session.scalars(select(AttendanceTask).where(AttendanceTask.class_id == class_id))
    )
    if any(settle_task(session, task) for task in tasks):
        session.commit()


def _attendance_by_student(session, class_id: int, window_from: str, window_to: str) -> dict:
    """出勤率按 SPEC-003 的口径：只算已结算任务、请假不计入分母。"""
    tasks = list(
        session.scalars(
            select(AttendanceTask).where(
                AttendanceTask.class_id == class_id,
                AttendanceTask.settled_at.is_not(None),
                AttendanceTask.opens_at >= window_from,
                AttendanceTask.opens_at < window_to,
            )
        )
    )
    records = []
    if tasks:
        records = list(
            session.execute(
                select(
                    AttendanceRecord.task_id,
                    AttendanceRecord.student_id,
                    AttendanceRecord.status,
                ).where(AttendanceRecord.task_id.in_([task.id for task in tasks]))
            ).all()
        )
    attendance = summarize_attendance(
        settled_tasks=len(tasks), records=records, student_meta={}
    )
    return {row["student_id"]: row for row in attendance["students"]}


def _progress_by_student(session, *, class_id: int, student_ids, window_to: str) -> dict:
    """完成率按 SPEC-006 的口径：分母是当前已发布知识点，只算 to 之前完成的记录。"""
    published_ids = list(
        session.scalars(
            select(KnowledgePoint.id)
            .where(KnowledgePoint.published == 1)
            .order_by(KnowledgePoint.id)
        )
    )
    records = []
    if student_ids and published_ids:
        records = [
            {
                "student_id": row.student_id,
                "knowledge_id": row.knowledge_id,
                "completed": row.completed,
                "completed_at": row.completed_at,
            }
            for row in session.scalars(
                select(LearningProgress).where(
                    LearningProgress.student_id.in_(student_ids),
                    LearningProgress.knowledge_id.in_(published_ids),
                )
            )
        ]
    progress = summarize_progress(
        student_ids=student_ids,
        published_knowledge_ids=published_ids,
        records=records,
        to_stamp=window_to,
    )
    # 样本量＝该学生在这批已发布知识点上的明确记录条数
    record_counts: dict[int, int] = {}
    for record in records:
        record_counts[record["student_id"]] = record_counts.get(record["student_id"], 0) + 1
    return {
        row["student_id"]: {
            "completion_rate": row["completion_rate"],
            "published_count": progress["published_knowledge_count"],
            "record_count": record_counts.get(row["student_id"], 0),
        }
        for row in progress["students"]
    }


def _first_attempt_rows(session, *, class_id: int, student_ids, window_from: str, window_to: str):
    """按学生汇总首答：每个 (学生, 题目) 取全历史最早的已提交作答，再按窗口筛选。

    规则与 SPEC-010 的知识点首答一致；这里保留 student_id 以便按学生计样本量。
    """
    if not student_ids:
        return {}
    assessment_ids = list(
        session.scalars(
            select(Assessment.id).where(
                Assessment.class_id == class_id,
                Assessment.kind.in_(CLASS_KINDS),
                Assessment.state.in_((STATE_PUBLISHED, STATE_CLOSED)),
            )
        )
    )
    if not assessment_ids:
        return {}
    rows = session.execute(
        select(
            AssessmentItem.question_id,
            Submission.id,
            Submission.student_id,
            Submission.submitted_at,
            SubmissionAnswer.correct,
        )
        .join(SubmissionAnswer, SubmissionAnswer.item_id == AssessmentItem.id)
        .join(Submission, Submission.id == SubmissionAnswer.submission_id)
        .where(
            AssessmentItem.assessment_id.in_(assessment_ids),
            Submission.student_id.in_(student_ids),
            Submission.status == STATUS_SUBMITTED,
            Submission.submitted_at.is_not(None),
        )
    ).all()
    earliest: dict[tuple[int, int], tuple[str, int, bool]] = {}
    for question_id, submission_id, student_id, submitted_at, correct in rows:
        key = (student_id, question_id)
        current = earliest.get(key)
        if current is None or (submitted_at, submission_id) < (current[0], current[1]):
            earliest[key] = (submitted_at, submission_id, bool(correct))

    summary: dict[int, dict] = {}
    for (student_id, _question_id), (submitted_at, _sid, correct) in earliest.items():
        if not (window_from <= submitted_at < window_to):
            continue
        bucket = summary.setdefault(student_id, {"count": 0, "correct": 0})
        bucket["count"] += 1
        if correct:
            bucket["correct"] += 1
    return summary


def _collect_students(session, *, class_id: int, window_from: str, window_to: str) -> list[dict]:
    """把三个因素拼成每个学生的输入；达不到样本门槛的因素按不可用处理。"""
    _settle_ended_tasks(session, class_id)
    student_ids = _roster(session, class_id)
    attendance = _attendance_by_student(session, class_id, window_from, window_to)
    progress = _progress_by_student(
        session, class_id=class_id, student_ids=student_ids, window_to=window_to
    )
    accuracy = _first_attempt_rows(
        session,
        class_id=class_id,
        student_ids=student_ids,
        window_from=window_from,
        window_to=window_to,
    )

    students = []
    for student_id in student_ids:
        attendance_row = attendance.get(student_id)
        attendance_rate = attendance_row["attendance_rate"] if attendance_row else None
        attendance_denominator = 0
        if attendance_row:
            counts = attendance_row["counts"]
            attendance_denominator = counts["present"] + counts["late"] + counts["absent"]

        progress_row = progress.get(student_id, {})
        completion_rate = progress_row.get("completion_rate")
        if not progress_row.get("published_count") or not progress_row.get("record_count"):
            completion_rate = None

        attempt = accuracy.get(student_id, {"count": 0, "correct": 0})
        first_accuracy = None
        if attempt["count"] >= MIN_ACCURACY_ATTEMPTS:
            first_accuracy = ratio(attempt["correct"], attempt["count"])

        students.append(
            {
                "student_id": student_id,
                "attendance_rate": attendance_rate,
                "completion_rate": completion_rate,
                "first_accuracy": first_accuracy,
                "sample_counts": {
                    "attendance": attendance_denominator,
                    "progress": progress_row.get("record_count", 0),
                    "accuracy": attempt["count"],
                },
            }
        )
    return students


def _warning_public(row: WarningSnapshot) -> dict:
    evidence = load_json(row.evidence_json, {})
    return {
        "student_id": row.student_id,
        "score": row.score,
        "level": row.level,
        "factors": evidence.get("factors", {}),
        "available_factors": evidence.get("available_factors", []),
        "sample_counts": evidence.get("sample_counts", {}),
        "cluster_label": row.cluster_label,
        "reasons": evidence.get("reasons", []),
        "generated_at": row.generated_at,
    }


def _next_batch_no(session, *, class_id: int, window_from: str, window_to: str) -> int:
    rows = session.scalars(
        select(WarningSnapshot).where(
            WarningSnapshot.class_id == class_id,
            WarningSnapshot.window_start == window_from,
            WarningSnapshot.window_end == window_to,
        )
    )
    return 1 + max(
        (load_json(row.evidence_json, {}).get("batch_no") or 0 for row in rows), default=0
    )


@bp.post("/warnings/generations")
@roles_required("teacher")
def generate_warnings():
    body = json_object(["class_id", "from", "to"])
    class_id = _class_id_from(body.get("class_id"), from_body=True)
    window_from, window_to = _resolve_window(body.get("from"), body.get("to"))
    session = db_session()
    _require_class_teacher(session, class_id)

    students = _collect_students(
        session, class_id=class_id, window_from=window_from, window_to=window_to
    )
    rows, cluster_reason = summarize_warnings(students=students)

    generated_at = now_utc()
    batch_no = _next_batch_no(
        session, class_id=class_id, window_from=window_from, window_to=window_to
    )
    roster_size = len(students)
    for row in rows:
        evidence = {
            "batch_no": batch_no,
            "roster_size": roster_size,
            "factors": row["factors"],
            "available_factors": row["available_factors"],
            "sample_counts": row["sample_counts"],
            "reasons": row["reasons"],
            "cluster_reason": cluster_reason,
            "disclaimer": DISCLAIMER,
        }
        session.add(
            WarningSnapshot(
                class_id=class_id,
                student_id=row["student_id"],
                window_start=window_from,
                window_end=window_to,
                algorithm_version=ALGORITHM_VERSION,
                evidence_json=dump_json(evidence),
                score=row["score"],
                level=row["level"],
                cluster_label=row["cluster_label"],
                generated_at=generated_at,
            )
        )
    session.commit()

    payload = [
        {
            "student_id": row["student_id"],
            "score": row["score"],
            "level": row["level"],
            "factors": row["factors"],
            "available_factors": row["available_factors"],
            "sample_counts": row["sample_counts"],
            "cluster_label": row["cluster_label"],
            "reasons": row["reasons"],
            "generated_at": generated_at,
        }
        for row in rows
    ]
    return success(
        {
            "generated_at": generated_at,
            "algorithm_version": ALGORITHM_VERSION,
            "window": {"from": window_from, "to": window_to},
            "cluster_reason": cluster_reason,
            "disclaimer": DISCLAIMER,
            "students": payload,
        },
        201,
    )


@bp.get("/warnings")
@roles_required("teacher")
def list_warnings():
    class_id = _class_id_from(request.args.get("class_id"), from_body=False)
    window_from, window_to = _resolve_window(request.args.get("from"), request.args.get("to"))
    page, page_size = pagination()
    session = db_session()
    _require_class_teacher(session, class_id)

    rows = list(
        session.scalars(
            select(WarningSnapshot)
            .where(
                WarningSnapshot.class_id == class_id,
                WarningSnapshot.window_start == window_from,
                WarningSnapshot.window_end == window_to,
            )
            .order_by(WarningSnapshot.id)
        )
    )
    # 按批次号归组；只保留「行数与生成时名单数一致」的完整批次
    batches: dict[int, list[WarningSnapshot]] = {}
    for row in rows:
        evidence = load_json(row.evidence_json, {})
        batch_no = evidence.get("batch_no")
        if batch_no is None:
            continue
        batches.setdefault(int(batch_no), []).append(row)

    latest: list[WarningSnapshot] = []
    for batch_no in sorted(batches, reverse=True):
        batch = batches[batch_no]
        roster_size = load_json(batch[0].evidence_json, {}).get("roster_size")
        if roster_size is not None and len(batch) == int(roster_size):
            latest = sorted(batch, key=lambda item: item.student_id)
            break

    total = len(latest)
    start = (page - 1) * page_size
    sliced = latest[start : start + page_size]
    return success(
        [_warning_public(row) for row in sliced],
        page=page,
        page_size=page_size,
        total=total,
    )
