"""E048/E049 实验定义、E052—E054 共享演示（SPEC-012 第 4 节）。

规则要点：
- 演示状态由**服务器**从旧状态重算，请求只能给输入与时钟事件，不能直接指定 q；
  未知字段一律 422，因此客户端无法用 q/score 之类的字段伪造状态。
- 教师动作带 expected_version，过期返回 409；关闭后动作同样 409。
- reveal_next=false 时 next_q 为 null，响应里不出现未揭示的下一状态（T-012-04）。
- 演示初始化时固定实验配置快照，实验事后修改或撤回不影响进行中的演示。
"""

from __future__ import annotations

from flask import Blueprint, request
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .auth import current_user, login_required, require_course_access, roles_required
from .errors import ApiError, success
from .models import Enrollment, SchoolClass, now_utc
from .models_content import KnowledgePoint
from .models_experiment import (
    STEPS_MD_MAX,
    DemoSession,
    Experiment,
    demo_public,
    dump_json,
    experiment_public,
    experiment_snapshot,
    load_json,
)
from .simulator import (
    MAX_EVENTS,
    SIMULATOR_TYPES,
    SimulationError,
    apply_event,
    compute_next_q,
    initial_state,
    normalize_config,
    validate_demo_action,
    validate_event,
)
from .store import db_session
from .validation import json_object, pagination, text_field

bp = Blueprint("experiment", __name__)

TITLE_MAX = 100
Q_MAX = 100


# ---- 校验与错误映射 ----

def _fields_error(name: str, rule: str):
    raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: rule}})


def _simulation_error(exc: SimulationError):
    raise ApiError(
        "VALIDATION_ERROR", "请求字段不合法", {"fields": {exc.field: exc.rule}}
    ) from exc


def _int_field(body: dict, name: str, *, minimum: int = 1) -> int:
    value = body.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fields_error(name, f"必须是 ≥{minimum} 的整数")
    return value


def _title_field(body: dict) -> str:
    value = text_field(body, "title", rule=f"1—{TITLE_MAX} 个字符", min_len=1, max_len=TITLE_MAX).strip()
    if not value:
        _fields_error("title", f"1—{TITLE_MAX} 个字符")
    return value


def _simulator_type_field(body: dict) -> str:
    value = body.get("simulator_type")
    if value not in SIMULATOR_TYPES:
        _fields_error("simulator_type", "/".join(SIMULATOR_TYPES))
    return value


def _steps_md_field(body: dict) -> str:
    value = body.get("steps_md")
    if not isinstance(value, str) or not (1 <= len(value) <= STEPS_MD_MAX):
        _fields_error("steps_md", f"1—{STEPS_MD_MAX} 个字符")
    return value


def _config_field(simulator_type: str, raw) -> dict:
    try:
        return normalize_config(simulator_type, raw)
    except SimulationError as exc:
        _simulation_error(exc)


def _input_sequence_field(simulator_type: str, raw) -> list:
    if not isinstance(raw, list):
        _fields_error("input_sequence", "必须是事件数组")
    if len(raw) > MAX_EVENTS:
        _fields_error("input_sequence", f"最多 {MAX_EVENTS} 个事件")
    sequence = []
    for index, item in enumerate(raw):
        try:
            sequence.append(validate_event(simulator_type, item))
        except SimulationError as exc:
            _fields_error(f"input_sequence[{index}].{exc.field}", exc.rule)
    return sequence


def _query_text() -> str | None:
    raw = request.args.get("q")
    if raw is None or raw == "":
        return None
    if len(raw) > Q_MAX:
        raise ApiError("INVALID_REQUEST", f"q 最长 {Q_MAX} 个字符")
    return raw


def _int_arg(name: str, *, required: bool) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw == "":
        if required:
            raise ApiError("INVALID_REQUEST", f"{name} 必填")
        return None
    try:
        value = int(raw)
    except ValueError:
        raise ApiError("INVALID_REQUEST", f"{name} 必须是整数") from None
    if value < 1:
        raise ApiError("INVALID_REQUEST", f"{name} 必须是正整数")
    return value


def _bool_arg(name: str) -> bool | None:
    raw = request.args.get(name)
    if raw is None:
        return None
    if raw not in {"true", "false", "1", "0"}:
        raise ApiError("INVALID_REQUEST", f"{name} 取值不合法", {"allowed": ["true", "false"]})
    return raw in {"true", "1"}


def _paginate(session, stmt, page: int, page_size: int):
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return rows, total


# ---- 权限 ----

def _visible_experiment(session, experiment_id: int, user) -> Experiment:
    """学生只读已发布；教师/管理员读「已发布 + 本人草稿」，其余按 404。"""
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise ApiError("NOT_FOUND", "实验不存在")
    if user.role == "student":
        if not experiment.published:
            raise ApiError("NOT_FOUND", "实验不存在")
    elif not experiment.published and experiment.owner_id != user.id:
        raise ApiError("NOT_FOUND", "实验不存在")
    return experiment


def _require_class_teacher(session, class_id: int) -> SchoolClass:
    """教师只能操作本人任教的班级；其他班级一律 404（APIC 第 1 节）。"""
    school_class = session.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_user().id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _require_class_read(session, class_id: int) -> SchoolClass:
    """教师读本人任教班级，学生读本人有效班级；管理员不参与课堂操作。"""
    user = current_user()
    if user.role == "admin":
        raise ApiError("FORBIDDEN", "管理员不参与课堂教学操作")
    school_class = session.get(SchoolClass, class_id)
    if school_class is None:
        raise ApiError("NOT_FOUND", "班级不存在")
    if user.role == "teacher":
        if school_class.teacher_id != user.id:
            raise ApiError("NOT_FOUND", "班级不存在")
        return school_class
    enrollment = session.scalar(
        select(Enrollment).where(
            Enrollment.class_id == class_id,
            Enrollment.student_id == user.id,
            Enrollment.active == 1,
        )
    )
    if enrollment is None:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _demo_or_404(session, demo_id: int) -> DemoSession:
    demo = session.get(DemoSession, demo_id)
    if demo is None:
        raise ApiError("NOT_FOUND", "演示不存在")
    return demo


def _demo_response(demo: DemoSession) -> dict:
    """next_q 只在已揭示时给出；隐藏时不计算也不出现在响应里。"""
    reveal = bool(demo.reveal_next)
    state = load_json(demo.state_json, {})
    next_q = None
    if reveal:
        snapshot = load_json(demo.config_snapshot_json, {})
        next_q = compute_next_q(
            snapshot.get("simulator_type"),
            snapshot.get("config", {}),
            state.get("q", 0),
            state.get("inputs", {}),
        )
    return demo_public(
        demo,
        experiment=load_json(demo.config_snapshot_json, {}),
        reveal_next=reveal,
        next_q=next_q,
    )


# ---- E048 /experiments ----

@bp.get("/experiments")
@login_required
def list_experiments():
    user = require_course_access()
    page, page_size = pagination()
    session = db_session()
    stmt = select(Experiment)
    if user.role == "student":
        stmt = stmt.where(Experiment.published == 1)
    else:
        stmt = stmt.where(or_(Experiment.published == 1, Experiment.owner_id == user.id))

    knowledge_id = _int_arg("knowledge_id", required=False)
    if knowledge_id is not None:
        stmt = stmt.where(Experiment.knowledge_id == knowledge_id)

    q = _query_text()
    if q:
        stmt = stmt.where(Experiment.title.contains(q, autoescape=True))

    stmt = stmt.order_by(Experiment.created_at.desc(), Experiment.id.desc())
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [experiment_public(e) for e in rows], page=page, page_size=page_size, total=total
    )


@bp.post("/experiments")
@roles_required("teacher", "admin")
def create_experiment():
    user = require_course_access()
    body = json_object(
        ["title", "knowledge_id", "simulator_type", "config", "steps_md", "input_sequence", "published"]
    )
    simulator_type = _simulator_type_field(body)
    knowledge_id = _int_field(body, "knowledge_id")
    published = body.get("published")
    if not isinstance(published, bool):
        _fields_error("published", "必须是布尔值")

    session = db_session()
    if session.get(KnowledgePoint, knowledge_id) is None:
        _fields_error("knowledge_id", "知识点不存在")

    experiment = Experiment(
        title=_title_field(body),
        knowledge_id=knowledge_id,
        simulator_type=simulator_type,
        config_json=dump_json(_config_field(simulator_type, body.get("config"))),
        steps_md=_steps_md_field(body),
        input_sequence_json=dump_json(
            _input_sequence_field(simulator_type, body.get("input_sequence"))
        ),
        published=1 if published else 0,
        owner_id=user.id,
    )
    session.add(experiment)
    session.commit()
    return success(experiment_public(experiment), 201)


# ---- E049 /experiments/{id} ----

@bp.get("/experiments/<int:experiment_id>")
@login_required
def get_experiment(experiment_id: int):
    user = require_course_access()
    session = db_session()
    experiment = _visible_experiment(session, experiment_id, user)
    return success(experiment_public(experiment))


@bp.patch("/experiments/<int:experiment_id>")
@roles_required("teacher", "admin")
def patch_experiment(experiment_id: int):
    user = require_course_access()
    body = json_object(
        [
            "version",
            "title",
            "knowledge_id",
            "simulator_type",
            "config",
            "steps_md",
            "input_sequence",
            "published",
        ]
    )
    session = db_session()
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise ApiError("NOT_FOUND", "实验不存在")
    if experiment.owner_id != user.id:
        raise ApiError("FORBIDDEN", "只能修改本人创建的实验")

    version = body.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        _fields_error("version", "必须是整数")
    if version != experiment.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "实验已被修改，请刷新后重试",
            {"expected_version": version, "current_version": experiment.version},
        )

    editable = {"title", "knowledge_id", "simulator_type", "config", "steps_md", "input_sequence", "published"}
    if not editable & set(body):
        raise ApiError("VALIDATION_ERROR", "没有可更新的字段")

    simulator_type = (
        _simulator_type_field(body)
        if "simulator_type" in body else experiment.simulator_type
    )
    # 类型变更后，旧配置和输入序列也必须符合新模型；否则后续开演示可能在
    # compute_next_q 中读取不到计数器模数，或执行不属于该模型的输入事件。
    config = load_json(experiment.config_json, {})
    sequence = load_json(experiment.input_sequence_json, [])
    if "simulator_type" in body or "config" in body:
        config = _config_field(simulator_type, body.get("config", config))
    if "simulator_type" in body or "input_sequence" in body:
        sequence = _input_sequence_field(
            simulator_type, body.get("input_sequence", sequence)
        )

    if "title" in body:
        experiment.title = _title_field(body)
    if "knowledge_id" in body:
        knowledge_id = _int_field(body, "knowledge_id")
        if session.get(KnowledgePoint, knowledge_id) is None:
            _fields_error("knowledge_id", "知识点不存在")
        experiment.knowledge_id = knowledge_id
    if "simulator_type" in body:
        experiment.simulator_type = simulator_type
    if "simulator_type" in body or "config" in body:
        experiment.config_json = dump_json(config)
    if "steps_md" in body:
        experiment.steps_md = _steps_md_field(body)
    if "simulator_type" in body or "input_sequence" in body:
        experiment.input_sequence_json = dump_json(sequence)
    if "published" in body:
        published = body.get("published")
        if not isinstance(published, bool):
            _fields_error("published", "必须是布尔值")
        experiment.published = 1 if published else 0

    # 发布记录更新递增版本；已发布的实验不回溯修改尝试快照（快照属 SPEC-013）
    experiment.version += 1
    session.commit()
    return success(experiment_public(experiment))


# ---- E052 /demo-sessions ----

@bp.get("/demo-sessions")
@login_required
def list_demo_sessions():
    user = require_course_access()
    page, page_size = pagination()
    session = db_session()
    class_id = _int_arg("class_id", required=True)
    _require_class_read(session, class_id)

    stmt = select(DemoSession).where(DemoSession.class_id == class_id)
    active = _bool_arg("active")
    if active is not None:
        stmt = stmt.where(DemoSession.active == (1 if active else 0))
    stmt = stmt.order_by(DemoSession.created_at.desc(), DemoSession.id.desc())

    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [_demo_response(d) for d in rows], page=page, page_size=page_size, total=total
    )


@bp.post("/demo-sessions")
@roles_required("teacher")
def create_demo_session():
    user = require_course_access()
    body = json_object(["class_id", "experiment_id"])
    class_id = _int_field(body, "class_id")
    experiment_id = _int_field(body, "experiment_id")

    session = db_session()
    school_class = _require_class_teacher(session, class_id)
    if not school_class.active:
        raise ApiError("STATE_CONFLICT", "班级已停用，不能发起新演示")
    # 只有可见的实验才能开演示：本人草稿或已发布（含他人的已发布内容）
    experiment = _visible_experiment(session, experiment_id, user)

    existing = session.scalar(
        select(DemoSession.id).where(
            DemoSession.class_id == class_id, DemoSession.active == 1
        )
    )
    if existing is not None:
        raise ApiError(
            "STATE_CONFLICT",
            "该班级已有进行中的演示，请先结束或复用它",
            {"active_demo_id": existing},
        )

    snapshot = experiment_snapshot(experiment)
    demo = DemoSession(
        class_id=class_id,
        experiment_id=experiment.id,
        owner_id=user.id,
        active=1,
        config_snapshot_json=dump_json(snapshot),
        state_json=dump_json(
            initial_state(snapshot["simulator_type"], snapshot["config"])
        ),
        event_log_json=dump_json([]),
        # 预测先隐藏（SPEC-012 第 4 节第 5 条、页面设计「下一状态 [待揭示]」）
        reveal_next=0,
    )
    session.add(demo)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(
            "STATE_CONFLICT", "该班级已有进行中的演示，请先结束或复用它"
        ) from exc
    return success(_demo_response(demo), 201)


# ---- E053 /demo-sessions/{id} ----

@bp.get("/demo-sessions/<int:demo_id>")
@login_required
def get_demo_session(demo_id: int):
    require_course_access()
    session = db_session()
    demo = _demo_or_404(session, demo_id)
    _require_class_read(session, demo.class_id)
    return success(_demo_response(demo))


# ---- E054 /demo-sessions/{id}/actions ----

@bp.post("/demo-sessions/<int:demo_id>/actions")
@roles_required("teacher")
def demo_action(demo_id: int):
    user = require_course_access()
    body = json_object(["expected_version", "event", "action"])
    session = db_session()
    demo = _demo_or_404(session, demo_id)
    school_class = _require_class_teacher(session, demo.class_id)
    if demo.owner_id != user.id:
        raise ApiError("FORBIDDEN", "只能操作本人发起的演示")

    expected = body.get("expected_version")
    if isinstance(expected, bool) or not isinstance(expected, int):
        _fields_error("expected_version", "必须是整数")
    if expected != demo.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "演示已更新，请刷新后再操作",
            {"expected_version": expected, "current_version": demo.version},
        )

    has_event, has_action = "event" in body, "action" in body
    if has_event == has_action:
        _fields_error("event", "必须给出 event 或 action 之一")

    if not demo.active:
        raise ApiError("STATE_CONFLICT", "演示已结束，不能再操作")

    snapshot = load_json(demo.config_snapshot_json, {})
    simulator_type = snapshot.get("simulator_type")
    config = snapshot.get("config", {})
    state = load_json(demo.state_json, {})
    history = load_json(demo.event_log_json, [])

    active = demo.active
    reveal_next = demo.reveal_next
    if has_event:
        try:
            event = validate_event(simulator_type, body["event"])
        except SimulationError as exc:
            _simulation_error(exc)
        if not school_class.active:
            raise ApiError("STATE_CONFLICT", "班级已停用，不能继续演示")
        if len(history) >= MAX_EVENTS and event["op"] != "reset_view":
            # reset_view 会把历史清空，必须始终可用，否则演示会彻底卡死
            raise ApiError(
                "STATE_CONFLICT",
                f"演示事件已达上限（{MAX_EVENTS}），请复位到初态后继续",
                {"event_count": len(history), "max_events": MAX_EVENTS},
            )
        new_state, row = apply_event(
            simulator_type, config, state, event, seq=len(history) + 1
        )
        state = new_state
        # reset_view 恢复初态并清空历史，但不改变 reveal_next（预测模式由教师显式切换）
        history = [] if row is None else [*history, row]
    else:
        try:
            action = validate_demo_action(body["action"])
        except SimulationError as exc:
            _simulation_error(exc)
        if not school_class.active and action["op"] != "close":
            raise ApiError("STATE_CONFLICT", "班级已停用，不能继续演示")
        if action["op"] == "close":
            active = 0
        else:
            reveal_next = 1 if action["value"] else 0

    # 条件更新保证并行请求中只有一个能消费 expected_version。先读后写的 ORM
    # version += 1 无法防止两个请求同时从相同旧状态推导、互相覆盖。
    updated = session.execute(
        update(DemoSession)
        .where(
            DemoSession.id == demo_id,
            DemoSession.version == expected,
            DemoSession.active == 1,
        )
        .values(
            state_json=dump_json(state),
            event_log_json=dump_json(history),
            active=active,
            reveal_next=reveal_next,
            version=expected + 1,
            updated_at=now_utc(),
        ),
        execution_options={"synchronize_session": False},
    ).rowcount
    if updated != 1:
        session.rollback()
        current_version = session.scalar(
            select(DemoSession.version).where(DemoSession.id == demo_id)
        )
        raise ApiError(
            "VERSION_CONFLICT", "演示已更新，请刷新后再操作",
            {"expected_version": expected, "current_version": current_version},
        )
    session.commit()
    session.refresh(demo)
    return success(_demo_response(demo))
