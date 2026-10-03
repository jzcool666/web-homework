"""E023—E027：备课与预习发布（SPEC-008 第 4 节）。

- 备课条目在库内是四个可空外键，对外只暴露 target_type/target_id；每条恰好一个目标，
  计划内顺序唯一。
- 引用内容必须是该教师可见的：已发布内容，或本人草稿；引用他人未发布草稿返回 422。
- 发布预习时把条目与内容摘要冻结进 snapshot_json；之后改原计划不改写已发布快照。
- 题目快照只含题干，不含答案与解析；学生只能读本班预习。
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, request
from sqlalchemy import delete, func, select

from .auth import current_user, roles_required
from .errors import ApiError, success
from .models import Enrollment, SchoolClass
from .models_assessment import Question, from_json, to_json
from .models_content import KnowledgePoint, Resource, ResourceVersion
from .models_experiment import Experiment
from .models_lesson import (
    EXCERPT_MAX,
    MAX_ITEMS,
    NOTES_MAX,
    TARGET_EXPERIMENT,
    TARGET_KNOWLEDGE,
    TARGET_QUESTION,
    TARGET_RESOURCE_VERSION,
    TARGET_TYPES,
    LessonPlan,
    LessonPlanItem,
    PreviewAssignment,
    plan_public,
    preview_public,
)
from .store import db_session
from .validation import json_object, pagination, text_field

bp = Blueprint("lesson", __name__)

STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _now() -> str:
    return datetime.now(timezone.utc).strftime(STAMP_FORMAT)


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=timezone.utc)


def _fields_error(field: str, rule: str):
    raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {field: rule}})


def _int_field(body: dict, name: str, *, minimum: int = 1) -> int:
    value = body.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        _fields_error(name, "必须是正整数")
    return value


def _timestamp_field(body: dict, name: str) -> str | None:
    """可空时间字段：缺省或 null 归一为 None。"""
    if name not in body or body[name] is None:
        return None
    value = body[name]
    if not isinstance(value, str):
        _fields_error(name, "必须是带 Z 的 UTC 时间")
    try:
        _parse(value)
    except ValueError:
        _fields_error(name, "必须是带 Z 的 UTC 时间，如 2026-09-29T01:00:00Z")
    return value


def _title(body: dict, name: str = "title") -> str:
    value = text_field(body, name, rule="1—100 个字符", min_len=1, max_len=100).strip()
    if not value:
        _fields_error(name, "1—100 个字符")
    return value


def _notes(body: dict) -> str:
    value = body.get("notes", "")
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > NOTES_MAX:
        _fields_error("notes", f"不超过 {NOTES_MAX} 个字符")
    return value


# ---- 可见内容解析 ----

def _visible_knowledge(session, target_id: int) -> KnowledgePoint:
    point = session.get(KnowledgePoint, target_id)
    user = current_user()
    if point is None or not (point.published or point.owner_id == user.id):
        _fields_error("items", f"知识点 {target_id} 不可引用（不存在或不是已发布内容/本人草稿）")
    return point


def _visible_resource_version(session, target_id: int) -> tuple[ResourceVersion, Resource]:
    version = session.get(ResourceVersion, target_id)
    if version is None:
        _fields_error("items", f"资源版本 {target_id} 不可引用")
    resource = session.get(Resource, version.resource_id)
    user = current_user()
    if resource is None or not (resource.published or resource.owner_id == user.id):
        _fields_error("items", f"资源版本 {target_id} 不可引用（所属资料不是已发布内容/本人草稿）")
    return version, resource


def _visible_question(session, target_id: int) -> Question:
    question = session.get(Question, target_id)
    user = current_user()
    if question is None or not (question.published or question.owner_id == user.id):
        _fields_error("items", f"题目 {target_id} 不可引用（不存在或不是已发布内容/本人草稿）")
    return question


def _visible_experiment(session, target_id: int) -> Experiment:
    experiment = session.get(Experiment, target_id)
    user = current_user()
    if experiment is None or not (experiment.published or experiment.owner_id == user.id):
        _fields_error("items", f"实验 {target_id} 不可引用（不存在或不是已发布内容/本人草稿）")
    return experiment


def _validate_items(raw) -> list[dict]:
    """校验条目结构：顺序唯一、每条恰好一个目标、目标类型合法。"""
    if not isinstance(raw, list) or len(raw) > MAX_ITEMS:
        _fields_error("items", f"必须是不超过 {MAX_ITEMS} 条的数组")
    orders: set[int] = set()
    prepared: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            _fields_error("items", "每项必须是 {sort_order,target_type,target_id}")
        unknown = set(entry) - {"sort_order", "target_type", "target_id"}
        if unknown:
            _fields_error("items", f"不支持字段：{','.join(sorted(unknown))}")
        order = entry.get("sort_order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            _fields_error("items", "sort_order 必须是不小于 1 的整数")
        if order in orders:
            _fields_error("items", "sort_order 在同一份备课单内必须唯一")
        orders.add(order)
        target_type = entry.get("target_type")
        if target_type not in TARGET_TYPES:
            _fields_error("items", f"target_type 只能是 {'/'.join(TARGET_TYPES)}")
        target_id = entry.get("target_id")
        if not isinstance(target_id, int) or isinstance(target_id, bool) or target_id < 1:
            _fields_error("items", "target_id 必须是正整数")
        prepared.append({"sort_order": order, "target_type": target_type, "target_id": target_id})
    prepared.sort(key=lambda item: item["sort_order"])
    return prepared


def _resolve_targets(session, prepared) -> dict[tuple[str, int], object]:
    """解析并校验所有引用；返回 (type, id) → 目标对象。"""
    resolved: dict[tuple[str, int], object] = {}
    for item in prepared:
        key = (item["target_type"], item["target_id"])
        if key in resolved:
            continue
        if item["target_type"] == TARGET_KNOWLEDGE:
            resolved[key] = _visible_knowledge(session, item["target_id"])
        elif item["target_type"] == TARGET_RESOURCE_VERSION:
            resolved[key] = _visible_resource_version(session, item["target_id"])
        elif item["target_type"] == TARGET_QUESTION:
            resolved[key] = _visible_question(session, item["target_id"])
        elif item["target_type"] == TARGET_EXPERIMENT:
            resolved[key] = _visible_experiment(session, item["target_id"])
    return resolved


def _write_items(session, plan: LessonPlan, prepared) -> None:
    session.execute(delete(LessonPlanItem).where(LessonPlanItem.plan_id == plan.id))
    session.flush()
    for item in prepared:
        column = {
            TARGET_KNOWLEDGE: "knowledge_id",
            TARGET_RESOURCE_VERSION: "resource_version_id",
            TARGET_QUESTION: "question_id",
            TARGET_EXPERIMENT: "experiment_id",
        }[item["target_type"]]
        session.add(
            LessonPlanItem(
                plan_id=plan.id,
                sort_order=item["sort_order"],
                **{column: item["target_id"]},
            )
        )


def _items_of(session, plan_id: int) -> list[LessonPlanItem]:
    return list(
        session.scalars(
            select(LessonPlanItem)
            .where(LessonPlanItem.plan_id == plan_id)
            .order_by(LessonPlanItem.sort_order)
        )
    )


def _own_plan(session, plan_id: int) -> LessonPlan:
    """备课单不按班级隔离，只有所有者可读写；他人一律 404。"""
    plan = session.get(LessonPlan, plan_id)
    if plan is None or plan.owner_id != current_user().id:
        raise ApiError("NOT_FOUND", "备课单不存在")
    return plan


def _require_class_teacher(session, class_id: int) -> SchoolClass:
    school_class = session.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_user().id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _require_class_student(session, class_id: int) -> SchoolClass:
    user = current_user()
    school_class = session.get(SchoolClass, class_id)
    if school_class is None:
        raise ApiError("NOT_FOUND", "班级不存在")
    if user.role == "student":
        enrolled = session.scalar(
            select(Enrollment.class_id).where(
                Enrollment.class_id == class_id,
                Enrollment.student_id == user.id,
                Enrollment.active == 1,
            )
        )
        if enrolled is None:
            raise ApiError("NOT_FOUND", "班级不存在")
    elif school_class.teacher_id != user.id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


# ---- E023 /lesson-plans ----

@bp.get("/lesson-plans")
@roles_required("teacher")
def list_lesson_plans():
    page, page_size = pagination()
    session = db_session()
    stmt = (
        select(LessonPlan)
        .where(LessonPlan.owner_id == current_user().id)
        .order_by(LessonPlan.created_at.desc(), LessonPlan.id.desc())
    )
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return success(
        [plan_public(plan, _items_of(session, plan.id)) for plan in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@bp.post("/lesson-plans")
@roles_required("teacher")
def create_lesson_plan():
    body = json_object(["title", "planned_at", "notes", "items"])
    title = _title(body)
    planned_at = _timestamp_field(body, "planned_at")
    notes = _notes(body)
    prepared = _validate_items(body.get("items", []))

    session = db_session()
    _resolve_targets(session, prepared)  # 引用校验先于落库，失败不留半成品
    plan = LessonPlan(
        title=title, owner_id=current_user().id, planned_at=planned_at, notes=notes
    )
    session.add(plan)
    session.flush()
    _write_items(session, plan, prepared)
    session.commit()
    return success(plan_public(plan, _items_of(session, plan.id)), 201)


# ---- E024 /lesson-plans/{id} ----

@bp.get("/lesson-plans/<int:plan_id>")
@roles_required("teacher")
def get_lesson_plan(plan_id: int):
    session = db_session()
    plan = _own_plan(session, plan_id)
    return success(plan_public(plan, _items_of(session, plan.id)))


@bp.patch("/lesson-plans/<int:plan_id>")
@roles_required("teacher")
def patch_lesson_plan(plan_id: int):
    body = json_object(["version", "title", "planned_at", "notes", "items"])
    session = db_session()
    plan = _own_plan(session, plan_id)

    version = _int_field(body, "version")
    if version != plan.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "备课单已被修改，请刷新后重试",
            {"expected_version": version, "current_version": plan.version},
        )
    if not {"title", "planned_at", "notes", "items"} & set(body):
        raise ApiError("VALIDATION_ERROR", "没有可更新的字段")

    prepared = None
    if "items" in body:
        prepared = _validate_items(body.get("items"))
        _resolve_targets(session, prepared)
    if "title" in body:
        plan.title = _title(body)
    if "planned_at" in body:
        plan.planned_at = _timestamp_field(body, "planned_at")
    if "notes" in body:
        plan.notes = _notes(body)
    if prepared is not None:
        _write_items(session, plan, prepared)
    plan.version += 1
    session.commit()
    return success(plan_public(plan, _items_of(session, plan.id)))


# ---- E025 /lesson-plans/{id}/copies ----

@bp.post("/lesson-plans/<int:plan_id>/copies")
@roles_required("teacher")
def copy_lesson_plan(plan_id: int):
    body = json_object(["title"])
    session = db_session()
    source = _own_plan(session, plan_id)
    title = _title(body)

    copy = LessonPlan(
        title=title,
        owner_id=current_user().id,
        planned_at=source.planned_at,
        notes=source.notes,
    )
    session.add(copy)
    session.flush()
    # 只复制条目引用，不复制内容、文件或题库
    for item in _items_of(session, source.id):
        session.add(
            LessonPlanItem(
                plan_id=copy.id,
                sort_order=item.sort_order,
                knowledge_id=item.knowledge_id,
                resource_version_id=item.resource_version_id,
                question_id=item.question_id,
                experiment_id=item.experiment_id,
            )
        )
    session.commit()
    return success(plan_public(copy, _items_of(session, copy.id)), 201)


# ---- 预习快照 ----

def _excerpt(body_md: str) -> str:
    text = body_md or ""
    if len(text) <= EXCERPT_MAX:
        return text
    return text[:EXCERPT_MAX] + "…"


def _snapshot_content(session, target_type: str, target_id: int, resolved) -> dict:
    """条目在预习快照里的内容摘要；题目只保留题干。"""
    if target_type == TARGET_KNOWLEDGE:
        point = resolved.get((target_type, target_id)) or session.get(KnowledgePoint, target_id)
        return {
            "title": point.title,
            "excerpt": _excerpt(point.body_md),
            "source_url": point.source_url,
        }
    if target_type == TARGET_RESOURCE_VERSION:
        version, resource = resolved[(target_type, target_id)]
        return {
            "resource_title": resource.title,
            "category": resource.category,
            "version_no": version.version_no,
            "kind": version.kind,
            "original_name": version.original_name,
            "mime": version.mime,
            "size_bytes": version.size_bytes,
            "external_url": version.external_url,
            "note": version.note,
        }
    if target_type == TARGET_QUESTION:
        question = resolved.get((target_type, target_id)) or session.get(Question, target_id)
        # 只放题干：不含 answer/explanation 等判定信息
        return {"stem_md": question.stem_md}
    experiment = resolved.get((target_type, target_id)) or session.get(Experiment, target_id)
    return {
        "title": experiment.title,
        "simulator_type": experiment.simulator_type,
        "steps_md": experiment.steps_md,
    }


def _build_snapshot(session, plan: LessonPlan, items, resolved) -> dict:
    return {
        "plan_title": plan.title,
        "plan_notes": plan.notes,
        "captured_at": _now(),
        "items": [
            {
                "sort_order": item.sort_order,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "content": _snapshot_content(session, item.target_type, item.target_id, resolved),
            }
            for item in items
        ],
    }


# ---- E026 /preview-assignments ----

@bp.post("/preview-assignments")
@roles_required("teacher")
def create_preview_assignment():
    body = json_object(["class_id", "plan_id", "due_at"])
    class_id = _int_field(body, "class_id")
    plan_id = _int_field(body, "plan_id")
    due_at = _timestamp_field(body, "due_at")

    session = db_session()
    school_class = _require_class_teacher(session, class_id)
    if not school_class.active:
        raise ApiError("STATE_CONFLICT", "班级已停用，不能发布新预习")
    plan = _own_plan(session, plan_id)

    items = _items_of(session, plan.id)
    prepared = [
        {"sort_order": item.sort_order, "target_type": item.target_type, "target_id": item.target_id}
        for item in items
    ]
    # 发布时再校验一次引用可见性：计划可能引用了之后被撤回为草稿的内容
    resolved = _resolve_targets(session, prepared)
    preview = PreviewAssignment(
        plan_id=plan.id,
        class_id=class_id,
        due_at=due_at,
        snapshot_json=to_json(_build_snapshot(session, plan, items, resolved)),
    )
    session.add(preview)
    session.commit()
    return success(preview_public(preview, from_json(preview.snapshot_json, default={})), 201)


# ---- E027 /preview-assignments ----

@bp.get("/preview-assignments")
@roles_required("teacher", "student")
def list_preview_assignments():
    page, page_size = pagination()
    raw_class = request.args.get("class_id")
    if raw_class is None:
        raise ApiError("INVALID_REQUEST", "缺少必填查询参数 class_id")
    try:
        class_id = int(raw_class)
    except (TypeError, ValueError):
        raise ApiError("INVALID_REQUEST", "class_id 必须是正整数")
    if class_id < 1:
        raise ApiError("INVALID_REQUEST", "class_id 必须是正整数")

    session = db_session()
    _require_class_student(session, class_id)
    stmt = (
        select(PreviewAssignment)
        .where(PreviewAssignment.class_id == class_id)
        .order_by(PreviewAssignment.created_at.desc(), PreviewAssignment.id.desc())
    )
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return success(
        [
            preview_public(row, from_json(row.snapshot_json, default={}))
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )
