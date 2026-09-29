"""E058 GET /analytics/experiment（SPEC-014）。

统计范围为**教师本人任教班级的当前有效在册学生**：跨班返回 404，学生返回 403，
JSON 与 CSV 走同一个权限校验，因此导出同样不能越权（SPEC-014 第 4 节第 4 条）。

窗口与 class_id 的解析方式与 SPEC-010 的统计接口保持一致；这里的辅助函数是本模块
私有实现，不改动 api_assessment.py 的对应逻辑（避免与并行模块的文件冲突）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, request
from sqlalchemy import select

from .auth import current_user, roles_required
from .errors import ApiError, success
from .models import Enrollment, SchoolClass
from .models_attempt import ExperimentAttempt
from .models_experiment import Experiment
from .stats_experiment import CSV_COLUMNS, csv_body, summarize_experiment_stats
from .store import db_session

bp = Blueprint("experiment_stats", __name__)

WINDOW_DEFAULT_DAYS = 30
WINDOW_MAX_DAYS = 366
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
            "INVALID_REQUEST", f"{name} 必须是带 Z 的 UTC 时间，如 2026-09-29T01:00:00Z"
        )


def _stats_window() -> tuple[str, str]:
    """统计窗口 [from,to)：两者同时给出或都省略，默认最近 30 天，最长 366 天。"""
    raw_from = request.args.get("from")
    raw_to = request.args.get("to")
    if (raw_from is None) != (raw_to is None):
        raise ApiError("INVALID_REQUEST", "from 与 to 必须同时给出或同时省略")
    if raw_from is None:
        # 存储精度为秒；默认窗口须覆盖「当前秒」刚写入的尝试，同时保持右开语义
        to_dt = _parse(_now().strftime(STAMP_FORMAT)) + timedelta(seconds=1)
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
        raise ApiError("INVALID_REQUEST", "class_id 必须是正整数") from None
    if value < 1:
        raise ApiError("INVALID_REQUEST", "class_id 必须是正整数")
    return value


def _require_class_teacher(session, class_id: int) -> SchoolClass:
    """仅本人任教班级；其他班级一律按 404 处理，避免泄露班级是否存在。"""
    school_class = session.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_user().id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _filter_experiment_id() -> int | None:
    raw = request.args.get("experiment_id")
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError("INVALID_REQUEST", "experiment_id 必须是正整数") from None
    if value < 1:
        raise ApiError("INVALID_REQUEST", "experiment_id 必须是正整数")
    return value


def _csv_response(payload: dict) -> Response:
    response = Response(csv_body(payload), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=experiment-stats.csv"
    return response


@bp.get("/analytics/experiment")
@roles_required("teacher")
def experiment_analytics():
    window_from, window_to = _stats_window()
    class_id = _stats_class_id()
    session = db_session()
    _require_class_teacher(session, class_id)

    # 当前有效在册学生；退班历史不并入统计（SPEC-014 第 4 节第 4 条）
    roster = set(
        session.scalars(
            select(Enrollment.student_id).where(
                Enrollment.class_id == class_id, Enrollment.active == 1
            )
        )
    )

    stmt = select(Experiment).where(Experiment.published == 1)
    if (wanted := _filter_experiment_id()) is not None:
        stmt = stmt.where(Experiment.id == wanted)
    experiments = [(item.id, item.title) for item in session.scalars(stmt.order_by(Experiment.id))]

    attempt_rows: list[tuple[int, int, int]] = []
    if roster and experiments:
        attempt_rows = [
            (experiment_id, student_id, passed)
            for experiment_id, student_id, passed in session.execute(
                select(
                    ExperimentAttempt.experiment_id,
                    ExperimentAttempt.student_id,
                    ExperimentAttempt.passed,
                ).where(
                    ExperimentAttempt.experiment_id.in_([eid for eid, _ in experiments]),
                    ExperimentAttempt.student_id.in_(roster),
                    ExperimentAttempt.created_at >= window_from,
                    ExperimentAttempt.created_at < window_to,
                )
            ).all()
        ]

    payload = {
        "window": {"from": window_from, "to": window_to},
        **summarize_experiment_stats(experiments=experiments, attempt_rows=attempt_rows),
    }

    fmt = request.args.get("format")
    if fmt == "csv":
        return _csv_response(payload)
    if fmt not in (None, "json"):
        raise ApiError("INVALID_REQUEST", "format 只支持 json 或 csv")
    return success(payload)
