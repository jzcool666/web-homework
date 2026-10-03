"""E055 GET /analytics/attendance：出勤与风险因素统计（SPEC-003）。

- 权限：仅教师，且只能读本人任教班级；跨班 404、学生与管理员 403、匿名 401。
- JSON 与 CSV 先算出同一份 payload 再分流，因此导出与页面是同一筛选、同一结果。
- 窗口按任务 `opens_at` 选择；进入统计前先对已结束任务做幂等结算，
  只纳入已结算任务，进行中的任务不进分母（SPEC-003 第 4 节第 1 条）。
- 结算复用 SPEC-002 的 `settle_task`，避免出现第二套结算语义。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, request
from sqlalchemy import select

from .api_attendance import settle_task
from .auth import current_user, roles_required
from .errors import ApiError, success
from .models import SchoolClass, User
from .models_assessment import (
    KIND_PRACTICE,
    STATUS_SUBMITTED,
    Assessment,
    Submission,
)
from .models_attendance import AttendanceRecord, AttendanceTask
from .stats_assessment import percent_of
from .stats_attendance import (
    csv_body,
    mean_percent_by_student,
    pearson_correlation,
    summarize_attendance,
)
from .store import db_session

bp = Blueprint("attendance_stats", __name__)

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 366
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(raw: str) -> datetime:
    return datetime.strptime(raw, STAMP_FORMAT).replace(tzinfo=timezone.utc)


def _window_param(raw: str, name: str) -> datetime:
    if not isinstance(raw, str):
        raise ApiError("INVALID_REQUEST", f"{name} 必须是带 Z 的 UTC 时间")
    try:
        return _parse(raw)
    except ValueError:
        raise ApiError(
            "VALIDATION_ERROR",
            "请求字段不合法",
            {"fields": {name: "必须是带 Z 的 UTC 时间，如 2026-09-29T00:00:00Z"}},
        ) from None


def _stats_window() -> tuple[str, str]:
    """统计窗口 [from,to)：两者同时给出或都省略，默认最近 30 天，最长 366 天。"""
    raw_from = request.args.get("from")
    raw_to = request.args.get("to")
    if (raw_from is None) != (raw_to is None):
        raise ApiError("INVALID_REQUEST", "from 与 to 必须同时给出或同时省略")
    if raw_from is None:
        # 存储精度为秒；默认窗口覆盖「当前秒」刚结束的任务，同时保持右开语义
        to_dt = _parse(_now().strftime(STAMP_FORMAT)) + timedelta(seconds=1)
        from_dt = to_dt - timedelta(days=DEFAULT_WINDOW_DAYS)
    else:
        from_dt = _window_param(raw_from, "from")
        to_dt = _window_param(raw_to, "to")
    if to_dt <= from_dt:
        raise ApiError("INVALID_REQUEST", "to 必须晚于 from")
    if to_dt - from_dt > timedelta(days=MAX_WINDOW_DAYS):
        raise ApiError("INVALID_REQUEST", f"统计窗口最长 {MAX_WINDOW_DAYS} 天")
    return from_dt.strftime(STAMP_FORMAT), to_dt.strftime(STAMP_FORMAT)


def _stats_class_id() -> int:
    raw = request.args.get("class_id")
    if raw is None:
        raise ApiError("INVALID_REQUEST", "缺少必填查询参数 class_id")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError("INVALID_REQUEST", "class_id 必须是正整数") from None
    if value < 1:
        raise ApiError("INVALID_REQUEST", "class_id 必须是正整数")
    return value


def _require_class_teacher(session, class_id: int) -> SchoolClass:
    school_class = session.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_user().id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _csv_response(payload: dict) -> Response:
    # mimetype 只给 text/csv：Flask 会自行追加 charset=utf-8
    response = Response(csv_body(payload), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=attendance-stats.csv"
    return response


def _settle_ended_tasks(session, class_id: int) -> None:
    """对已结束但尚未结算的任务做一次幂等结算，再统计。"""
    tasks = list(
        session.scalars(select(AttendanceTask).where(AttendanceTask.class_id == class_id))
    )
    if any(settle_task(session, task) for task in tasks):
        session.commit()


def _assessment_rows(session, class_id: int, window_from: str, window_to: str):
    """本班非 practice 测评中，提交时间落在窗口内的已提交记录。"""
    return session.execute(
        select(Submission.student_id, Submission.score, Assessment.total_score)
        .join(Assessment, Assessment.id == Submission.assessment_id)
        .where(
            Assessment.class_id == class_id,
            Assessment.kind != KIND_PRACTICE,
            Submission.status == STATUS_SUBMITTED,
            Submission.submitted_at.is_not(None),
            Submission.submitted_at >= window_from,
            Submission.submitted_at < window_to,
        )
    ).all()


@bp.get("/analytics/attendance")
@roles_required("teacher")
def attendance_analytics():
    window_from, window_to = _stats_window()
    class_id = _stats_class_id()
    session = db_session()
    _require_class_teacher(session, class_id)

    _settle_ended_tasks(session, class_id)

    # 窗口按 opens_at 选择；只纳入已结算任务
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
    task_ids = [task.id for task in tasks]

    records = []
    if task_ids:
        records = list(
            session.execute(
                select(
                    AttendanceRecord.task_id,
                    AttendanceRecord.student_id,
                    AttendanceRecord.status,
                ).where(AttendanceRecord.task_id.in_(task_ids))
            ).all()
        )

    student_ids = sorted({row[1] for row in records})
    student_meta = {}
    if student_ids:
        student_meta = {
            user.id: user
            for user in session.scalars(select(User).where(User.id.in_(student_ids)))
        }

    attendance = summarize_attendance(
        settled_tasks=len(tasks), records=records, student_meta=student_meta
    )

    score_rows = [
        (student_id, percent_of(score, total))
        for student_id, score, total in _assessment_rows(
            session, class_id, window_from, window_to
        )
    ]
    mean_percent = mean_percent_by_student(rows=score_rows)

    # 相关只用两列都有值的学生；出勤率 null（全请假或没有可计任务）不参与
    pairs = [
        (student["student_id"], student["attendance_rate"], mean_percent[student["student_id"]])
        for student in attendance["students"]
        if student["attendance_rate"] is not None
        and mean_percent.get(student["student_id"]) is not None
    ]

    payload = {
        "window": {"from": window_from, "to": window_to},
        **attendance,
        "correlation": pearson_correlation(pairs=pairs),
    }

    fmt = request.args.get("format")
    if fmt == "csv":
        return _csv_response(payload)
    if fmt not in (None, "json"):
        raise ApiError("INVALID_REQUEST", "format 只支持 json 或 csv")
    return success(payload)
