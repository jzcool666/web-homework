"""E069/E070 时序逻辑识别辅助（SPEC-017）。

- 权限：E069 仅学生与教师，且创建时核对班级——学生只能选本人当前有效班级、
  教师只能选本人任教班级；E070 允许创建者与「任务保存的 class_id 的任课教师」读取，
  其他人一律 404（不区分「不存在」与「无权」，避免泄露任务是否存在）。
- 图片按 ADR-008 以随机 storage_key 落盘到 UPLOAD_DIR/recognition/，原始文件名只用于显示。
- 处理同步完成并限时：超时返回 503 `RECOGNITION_TIMEOUT`，并删除刚写入的文件、
  不保留任务（SPEC-017 第 4 节第 7 条）。
- 识别只是辅助信息：结果带 `requires_review=true`，实验判分仍由 SPEC-013 从配置与
  输入序列重算，不采信识别结论或客户端字段。
"""

from __future__ import annotations

import secrets
import time
from pathlib import Path

from flask import Blueprint, current_app, request
from sqlalchemy import select

from .auth import current_user, roles_required
from .errors import ApiError, success
from .models import Enrollment, SchoolClass
from .models_experiment import dump_json, load_json
from .models_recognition import KIND_STATE_TABLE, RecognitionTask
from .recognition_service import (
    RecognitionFormatError,
    RecognitionTimeout,
    recognize_state_table,
)
from .storage import (
    MAX_UPLOAD_BYTES,
    display_name,
    file_extension,
    upload_root,
    validate_upload,
)
from .store import db_session

bp = Blueprint("recognition", __name__)

RECOGNITION_SUBDIR = "recognition"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
IMAGE_TYPE_RULE = "仅支持 PNG、JPEG 图片"
SIZE_RULE = "单文件不超过 20 MiB"
MULTIPART_SLACK = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 5.0


def _require_class_participant(session, class_id: int) -> SchoolClass:
    """学生看本人有效班级，教师看本人任教班级；其余按 404 处理。"""
    school_class = session.get(SchoolClass, class_id)
    user = current_user()
    if school_class is None:
        raise ApiError("NOT_FOUND", "班级不存在")
    if user.role == "teacher":
        if school_class.teacher_id != user.id:
            raise ApiError("NOT_FOUND", "班级不存在")
        return school_class
    enrolled = session.scalar(
        select(Enrollment.student_id).where(
            Enrollment.class_id == class_id,
            Enrollment.student_id == user.id,
            Enrollment.active == 1,
        )
    )
    if enrolled is None:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


def _can_read(session, task: RecognitionTask) -> bool:
    user = current_user()
    if task.owner_id == user.id:
        return True
    if user.role != "teacher":
        return False
    school_class = session.get(SchoolClass, task.class_id)
    return school_class is not None and school_class.teacher_id == user.id


def _class_id_field() -> int:
    raw = request.form.get("class_id")
    if raw is None or not str(raw).isdigit() or int(raw) < 1:
        raise ApiError(
            "VALIDATION_ERROR", "请求字段不合法", {"fields": {"class_id": "必须是正整数"}}
        )
    return int(raw)


def _kind_field() -> str:
    kind = request.form.get("kind")
    if kind != KIND_STATE_TABLE:
        raise ApiError(
            "VALIDATION_ERROR",
            "请求字段不合法",
            {"fields": {"kind": KIND_STATE_TABLE}},
        )
    return kind


def _read_image() -> tuple[str, bytes]:
    """取出 multipart 图片并做类型/大小/文件头校验（ADR-008）。"""
    if (
        request.content_length is not None
        and request.content_length > MAX_UPLOAD_BYTES + MULTIPART_SLACK
    ):
        raise ApiError("FILE_TOO_LARGE", f"上传文件过大，{SIZE_RULE}")

    storage = request.files.get("image")
    if storage is None or not storage.filename:
        raise ApiError(
            "VALIDATION_ERROR",
            "请提供图片",
            {"fields": {"image": "multipart 需包含 image 字段"}},
        )
    filename = storage.filename
    if file_extension(filename) not in IMAGE_EXTENSIONS:
        # 先按扩展名拦掉 GIF/PDF 等，再交给统一校验
        raise ApiError(
            "FILE_TYPE_UNSUPPORTED", IMAGE_TYPE_RULE, {"allowed": ["png", "jpeg"]}
        )

    payload = storage.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ApiError("FILE_TOO_LARGE", f"上传文件过大，{SIZE_RULE}")
    try:
        validate_upload(filename, payload)
    except ValueError as exc:
        reason = str(exc)
        if reason == "size":
            raise ApiError("FILE_TOO_LARGE", f"上传文件过大，{SIZE_RULE}") from exc
        if reason == "empty":
            raise ApiError(
                "VALIDATION_ERROR", "上传文件为空", {"fields": {"image": "不能为空文件"}}
            ) from exc
        raise ApiError(
            "FILE_TYPE_UNSUPPORTED", IMAGE_TYPE_RULE, {"allowed": ["png", "jpeg"]}
        ) from exc
    return filename, payload


def _store_image(filename: str, payload: bytes) -> dict:
    root = upload_root(current_app.config["UPLOAD_DIR"]) / RECOGNITION_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    extension = file_extension(filename)
    storage_key = f"{RECOGNITION_SUBDIR}/{secrets.token_hex(16)}{extension}"
    (root / Path(storage_key).name).write_bytes(payload)
    return {
        "storage_key": storage_key,
        "original_name": display_name(filename),
        "mime": "image/png" if extension == ".png" else "image/jpeg",
        "size_bytes": len(payload),
    }


def _remove_image(storage_key: str) -> None:
    try:
        (upload_root(current_app.config["UPLOAD_DIR"]) / storage_key).unlink(missing_ok=True)
    except OSError:  # 清理失败不应掩盖真正的错误
        current_app.logger.warning("识别任务临时文件清理失败：%s", storage_key)


def _task_public(task: RecognitionTask) -> dict:
    return {
        "id": task.id,
        "class_id": task.class_id,
        "kind": task.kind,
        "status": task.status,
        "created_at": task.created_at,
        "result": load_json(task.result_json, None),
        "error": load_json(task.error_json, None),
    }


@bp.post("/recognition-tasks")
@roles_required("student", "teacher")
def create_recognition_task():
    # 本接口刻意**忽略**多出来的 multipart 字段（例如 passed/score）：T-017-03 要求
    # 客户端字段被忽略而不是报错，而这些字段在本模块没有任何落库或判分作用，
    # 识别结果也不参与实验判分，因此忽略不会带来「被批量覆盖」的风险。
    class_id = _class_id_field()
    kind = _kind_field()
    session = db_session()
    _require_class_participant(session, class_id)

    filename, payload = _read_image()
    stored = _store_image(filename, payload)

    limit = float(
        current_app.config.get("RECOGNITION_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )
    deadline = time.monotonic() + limit
    try:
        outcome = recognize_state_table(payload, deadline=deadline)
    except RecognitionTimeout as exc:
        _remove_image(stored["storage_key"])
        raise ApiError(
            "RECOGNITION_TIMEOUT",
            "识别超时，未保留任务，请稍后重试",
            status=503,
        ) from exc
    except RecognitionFormatError as exc:  # 兜底：服务内部按格式失败返回
        outcome = {
            "status": "failed",
            "error": {"code": exc.code, "message": exc.reason, "details": exc.details or {}},
        }
    except Exception:
        _remove_image(stored["storage_key"])
        raise

    done = outcome["status"] == "done"
    task = RecognitionTask(
        owner_id=current_user().id,
        class_id=class_id,
        kind=kind,
        storage_key=stored["storage_key"],
        original_name=stored["original_name"],
        mime=stored["mime"],
        size_bytes=stored["size_bytes"],
        status=outcome["status"],
        result_json=dump_json(outcome["result"]) if done else None,
        error_json=dump_json(outcome["error"]) if not done else None,
    )
    session.add(task)
    session.commit()
    return success(_task_public(task), 201)


@bp.get("/recognition-tasks/<int:task_id>")
@roles_required("student", "teacher")
def get_recognition_task(task_id: int):
    session = db_session()
    task = session.get(RecognitionTask, task_id)
    if task is None or not _can_read(session, task):
        raise ApiError("NOT_FOUND", "识别任务不存在")
    return success(_task_public(task))
