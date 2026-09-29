"""E050 学生提交实验预测、E051 本人实验记录（SPEC-013 第 4 节）。

规则要点：
- 学生只能提交 `experiment_version`、`predictions`、`request_key`；输入序列由服务端
  实验快照固定，`passed`/`expected`/`input_sequence` 等字段一律 422，因此判分不可伪造。
- 标准状态由 `experiment_service` 复用 `simulator.py` 从固定输入序列重算，不采信客户端。
- `request_key` 按学生唯一：同 key 同内容重试返回原结果且不新增记录，同 key 不同内容 409。
- 旧 `experiment_version` 返回 409，要求学生刷新后重交。
"""

from __future__ import annotations

import uuid

from flask import Blueprint, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .auth import login_required, require_course_access, roles_required
from .errors import ApiError, success
from .experiment_service import (
    CheckpointError,
    expected_states,
    first_difference,
    require_checkpoints,
    state_range,
)
from .models_attempt import ExperimentAttempt, attempt_public, experiment_attempt_snapshot
from .models_experiment import Experiment, dump_json, load_json
from .store import db_session
from .validation import json_object, pagination

bp = Blueprint("attempt", __name__)


def _fields_error(name: str, rule: str):
    raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: rule}})


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


def _paginate(session, stmt, page: int, page_size: int):
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return rows, total


def _visible_experiment(session, experiment_id: int) -> Experiment:
    """学生只读已发布实验；草稿按 404 处理，不泄露其存在。"""
    experiment = session.get(Experiment, experiment_id)
    if experiment is None or not experiment.published:
        raise ApiError("NOT_FOUND", "实验不存在")
    return experiment


def _experiment_version_field(body: dict) -> int:
    value = body.get("experiment_version")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fields_error("experiment_version", "必须是正整数")
    return value


def _request_key_field(body: dict) -> str:
    value = body.get("request_key")
    if not isinstance(value, str):
        _fields_error("request_key", "必须是 UUID 字符串")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        _fields_error("request_key", "必须是 UUID 字符串")
    # 统一成规范形式：同一 UUID 的不同大小写写法视为同一个 key
    return str(parsed)


def _predictions_field(body: dict, simulator_type: str, count: int) -> list[int]:
    raw = body.get("predictions")
    if not isinstance(raw, list):
        _fields_error("predictions", "必须是整数数组")
    if len(raw) != count:
        _fields_error("predictions", f"长度必须等于检查点数 {count}（当前 {len(raw)}）")
    low, high = state_range(simulator_type)
    values: list[int] = []
    for index, item in enumerate(raw):
        if isinstance(item, bool) or not isinstance(item, int) or not low <= item <= high:
            _fields_error(f"predictions[{index}]", f"必须是 {low}—{high} 的整数")
        values.append(item)
    return values


def _checkpoints_or_422(experiment: Experiment) -> list[dict]:
    try:
        return require_checkpoints(
            experiment.simulator_type,
            load_json(experiment.config_json, {}),
            load_json(experiment.input_sequence_json, []),
        )
    except CheckpointError as exc:
        raise ApiError("VALIDATION_ERROR", exc.message) from exc


def _same_payload(
    attempt: ExperimentAttempt, experiment_id: int, experiment_version: int, predictions: list[int]
) -> bool:
    """同 key 重试是否完全同内容：实验、版本与预测序列都要一致。"""
    snapshot = load_json(attempt.experiment_snapshot_json, {})
    return (
        attempt.experiment_id == experiment_id
        and snapshot.get("experiment_version") == experiment_version
        and load_json(attempt.predictions_json, []) == predictions
    )


# ---- E050 提交预测 ----

@bp.post("/experiments/<int:experiment_id>/attempts")
@roles_required("student")
def submit_attempt(experiment_id: int):
    user = require_course_access()
    body = json_object(["experiment_version", "predictions", "request_key"])
    experiment_version = _experiment_version_field(body)
    request_key = _request_key_field(body)

    session = db_session()
    experiment = _visible_experiment(session, experiment_id)

    if experiment_version != experiment.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "实验已被更新，请刷新后再提交",
            {"expected_version": experiment_version, "current_version": experiment.version},
        )

    checkpoints = _checkpoints_or_422(experiment)
    predictions = _predictions_field(body, experiment.simulator_type, len(checkpoints))

    existing = session.scalar(
        select(ExperimentAttempt).where(
            ExperimentAttempt.student_id == user.id,
            ExperimentAttempt.request_key == request_key,
        )
    )
    if existing is not None:
        if not _same_payload(existing, experiment_id, experiment_version, predictions):
            raise ApiError(
                "DUPLICATE",
                "该 request_key 已用于另一次提交，请换一个 key",
                {"attempt_id": existing.id},
            )
        # 同 key 同内容：返回原结果，不新增记录（断线重试友好）
        return success(attempt_public(existing))

    expected = expected_states(checkpoints)
    first_error = first_difference(expected, predictions)
    attempt = ExperimentAttempt(
        experiment_id=experiment_id,
        student_id=user.id,
        experiment_snapshot_json=dump_json(
            experiment_attempt_snapshot(
                experiment.simulator_type,
                load_json(experiment.config_json, {}),
                load_json(experiment.input_sequence_json, []),
                experiment_version,
            )
        ),
        predictions_json=dump_json(predictions),
        expected_json=dump_json(expected),
        passed=0 if first_error is not None else 1,
        first_error_index=first_error,
        request_key=request_key,
    )
    session.add(attempt)
    try:
        session.commit()
    except IntegrityError as exc:
        # 并发同 key：回滚后按已存在的记录判断是否为同内容重试
        session.rollback()
        raced = session.scalar(
            select(ExperimentAttempt).where(
                ExperimentAttempt.student_id == user.id,
                ExperimentAttempt.request_key == request_key,
            )
        )
        if raced is not None and _same_payload(raced, experiment_id, experiment_version, predictions):
            return success(attempt_public(raced))
        raise ApiError(
            "DUPLICATE", "该 request_key 已用于另一次提交，请换一个 key"
        ) from exc

    return success(attempt_public(attempt), 201)


# ---- E051 本人历史 ----

@bp.get("/me/experiment-attempts")
@login_required
def list_my_attempts():
    user = require_course_access()
    if user.role != "student":
        raise ApiError("FORBIDDEN", "只有学生有个人实验记录")
    page, page_size = pagination()
    session = db_session()
    # 只返回本人的记录：模型没有按 id 读取单个尝试的接口，他人记录不存在可见路径
    stmt = select(ExperimentAttempt).where(ExperimentAttempt.student_id == user.id)

    experiment_id = _int_arg("experiment_id", required=False)
    if experiment_id is not None:
        stmt = stmt.where(ExperimentAttempt.experiment_id == experiment_id)

    stmt = stmt.order_by(
        ExperimentAttempt.created_at.desc(), ExperimentAttempt.id.desc()
    )
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [attempt_public(row) for row in rows], page=page, page_size=page_size, total=total
    )
