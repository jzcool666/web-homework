"""E056 GET /analytics/learning：学习进度与资源统计（SPEC-006 第 4 节）。

- 权限：仅教师，且只能读本人任教班级；跨班按 404，学生与管理员 403，匿名 401。
- JSON 与 CSV 共用同一份统计结果与同一套权限校验：先把 payload 算出来，
  再决定是返回 JSON 还是 CSV。
- `from`/`to` 只接受 UTC 整日边界；默认最近 30 个 UTC 自然日，截止到当前 UTC 日
  的下一日 00:00。`from` 只过滤资源事件，不改变进度快照口径。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, request
from sqlalchemy import select

from .auth import current_user, roles_required
from .errors import ApiError, success
from .models import Enrollment, SchoolClass, User
from .models_content import KnowledgePoint, LearningProgress, Resource, ResourceEvent, ResourceVersion
from .stats_learning import (
    MAX_WINDOW_DAYS,
    PROGRESS_BASIS,
    csv_body,
    default_window,
    parse_day_boundary,
    stamp,
    summarize_progress,
    summarize_resources,
)
from .store import db_session

bp = Blueprint("learning", __name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def _chapter_param() -> int | None:
    raw = request.args.get("chapter_id")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError("INVALID_REQUEST", "chapter_id 必须是正整数") from None
    if value < 1:
        raise ApiError("INVALID_REQUEST", "chapter_id 必须是正整数")
    return value


def _day_param(raw: str, name: str) -> datetime:
    try:
        return parse_day_boundary(raw, name)
    except ValueError:
        raise ApiError(
            "VALIDATION_ERROR",
            "请求字段不合法",
            {"fields": {name: "必须是 UTC 整日边界，如 2026-09-29T00:00:00Z"}},
        ) from None


def _stats_window() -> tuple[str, str]:
    """UTC 整日窗口 [from,to)；两者同时给出或都省略，最长 366 天。"""
    raw_from = request.args.get("from")
    raw_to = request.args.get("to")
    if (raw_from is None) != (raw_to is None):
        raise ApiError("INVALID_REQUEST", "from 与 to 必须同时给出或同时省略")
    if raw_from is None:
        from_dt, to_dt = default_window(_now())
    else:
        from_dt = _day_param(raw_from, "from")
        to_dt = _day_param(raw_to, "to")
    if to_dt <= from_dt:
        raise ApiError("INVALID_REQUEST", "to 必须晚于 from")
    if to_dt - from_dt > timedelta(days=MAX_WINDOW_DAYS):
        raise ApiError("INVALID_REQUEST", f"统计窗口最长 {MAX_WINDOW_DAYS} 天")
    return stamp(from_dt), stamp(to_dt)


def _require_class_teacher(session, class_id: int) -> SchoolClass:
    school_class = session.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_user().id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _csv_response(payload: dict) -> Response:
    # mimetype 只给 text/csv：Flask 会自行追加 charset=utf-8，重复写会出现两次
    response = Response(csv_body(payload), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=learning-stats.csv"
    return response


@bp.get("/analytics/learning")
@roles_required("teacher")
def learning_analytics():
    window_from, window_to = _stats_window()
    class_id = _stats_class_id()
    chapter_id = _chapter_param()
    session = db_session()
    _require_class_teacher(session, class_id)

    # 当前有效在册学生：进度快照只算他们
    student_ids = list(
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
    # 曾在本班的学生（含已退班）：历史资源活动仍然统计
    ever_ids = set(
        session.scalars(
            select(Enrollment.student_id).where(Enrollment.class_id == class_id)
        )
    )

    published_stmt = select(KnowledgePoint.id).where(KnowledgePoint.published == 1)
    if chapter_id is not None:
        published_stmt = published_stmt.where(KnowledgePoint.chapter_id == chapter_id)
    published_ids = list(session.scalars(published_stmt.order_by(KnowledgePoint.id)))

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

    # 窗口边界是 UTC 整日，前 10 位即事件表使用的 YYYY-MM-DD
    from_day, to_day = window_from[:10], window_to[:10]
    events = []
    resource_of_version: dict[int, int] = {}
    if ever_ids:
        event_stmt = (
            select(
                ResourceEvent.student_id,
                ResourceEvent.resource_version_id,
                ResourceEvent.event_kind,
                ResourceEvent.event_day,
                ResourceVersion.resource_id,
                Resource.knowledge_id,
            )
            .join(ResourceVersion, ResourceVersion.id == ResourceEvent.resource_version_id)
            .join(Resource, Resource.id == ResourceVersion.resource_id)
            .where(
                ResourceEvent.student_id.in_(ever_ids),
                ResourceEvent.event_day >= from_day,
                ResourceEvent.event_day < to_day,
            )
        )
        if chapter_id is not None:
            # 章节筛选要比较「资料关联知识点所属的章节」，不是知识点 ID 本身；
            # 未关联知识点的资料在按章节筛选时不出现
            event_stmt = event_stmt.join(
                KnowledgePoint, KnowledgePoint.id == Resource.knowledge_id
            ).where(KnowledgePoint.chapter_id == chapter_id)
        for student_id, version_id, kind, event_day, resource_id, _knowledge_id in session.execute(
            event_stmt
        ):
            resource_of_version[version_id] = resource_id
            events.append(
                {
                    "student_id": student_id,
                    "resource_version_id": version_id,
                    "event_kind": kind,
                    "event_day": event_day,
                }
            )

    payload = {
        "window": {"from": window_from, "to": window_to},
        "published_knowledge_count": progress["published_knowledge_count"],
        "students": progress["students"],
        "resources": summarize_resources(events=events, resource_of_version=resource_of_version),
        "progress_basis": PROGRESS_BASIS,
    }
    if request.args.get("format") == "csv":
        return _csv_response(payload)
    if request.args.get("format") not in (None, "json"):
        raise ApiError("INVALID_REQUEST", "format 只支持 json 或 csv")
    return success(payload)
