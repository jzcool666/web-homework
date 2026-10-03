"""Bounded lab API. Every object is authorized against live class ownership."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from flask import Blueprint, request, Response, current_app, send_file
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from .auth import current_user, roles_required
from .errors import ApiError, success
from .models import SchoolClass, Enrollment, User, now_utc
from .models_content import KnowledgePoint
from .models_lab import LabTask, LabSession, LabAttempt
from .store import db_session
from .validation import json_object, pagination
from .lab_engine import replay, empty_board, LabError
from .lab_suites import grade_wiring
from .lab_templates import template
from .lab_circ import validate_circ, MAX_BYTES
from .lab_logisim import ENGINE_VERSION
from .lab_worker import storage_root, worker_available

bp = Blueprint("labs", __name__)


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def fingerprint(value):
    return hashlib.sha256(dump(value).encode()).hexdigest()


def integer(value, name):
    if type(value) is not int or value < 1:
        raise ApiError("VALIDATION_ERROR", f"{name}必须为正整数")
    return value


def key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", value):
        raise ApiError("VALIDATION_ERROR", "请求键必须为8—64位字母数字下划线或短横线")
    return value


def class_access(id, write=False):
    user = current_user()
    s = db_session()
    row = s.get(SchoolClass, id)
    allowed = row and (
        (user.role == "teacher" and row.teacher_id == user.id)
        or (
            user.role == "student"
            and s.get(Enrollment, (id, user.id)) is not None
            and s.get(Enrollment, (id, user.id)).active
        )
    )
    if not allowed or (write and not row.active):
        raise ApiError("NOT_FOUND", "班级不存在或不可访问")
    return row


def current_class():
    user = current_user()
    s = db_session()
    if user.role == "teacher":
        row = s.scalar(
            select(SchoolClass).where(
                SchoolClass.teacher_id == user.id, SchoolClass.active == 1
            )
        )
    else:
        row = s.scalar(
            select(SchoolClass)
            .join(Enrollment, Enrollment.class_id == SchoolClass.id)
            .where(
                Enrollment.student_id == user.id,
                Enrollment.active == 1,
                SchoolClass.active == 1,
            )
        )
    if row is None:
        raise ApiError("NOT_FOUND", "没有当前有效班级")
    return row


def public_task(row):
    return dict(
        json.loads(row.public_profile_json),
        id=row.id,
        version=row.version,
        knowledge_id=row.knowledge_id,
    )


def task_access(id, version=None):
    row = db_session().get(LabTask, id)
    if (
        row is None
        or not row.published
        or not db_session().get(KnowledgePoint, row.knowledge_id).published
    ):
        raise ApiError("NOT_FOUND", "实验任务不存在或未开放")
    if version is not None and row.version != version:
        raise ApiError("VERSION_CONFLICT", "任务已更新，请重新进入实验")
    return row


def session_access(id, write=False):
    row = db_session().get(LabSession, id)
    user = current_user()
    if row is None:
        raise ApiError("NOT_FOUND", "实验会话不存在")
    if row.owner_id != user.id:
        if user.role != "teacher" or write:
            raise ApiError("NOT_FOUND", "实验会话不存在")
        class_access(row.class_id)
    if write:
        class_access(row.class_id, True)
        task_access(row.task_id, row.task_version)
    return row


def attempt_access(id):
    row = db_session().get(LabAttempt, id)
    if row is None:
        raise ApiError("NOT_FOUND", "实验记录不存在")
    if row.student_id != current_user().id:
        if current_user().role != "teacher":
            raise ApiError("NOT_FOUND", "实验记录不存在")
        class_access(row.class_id)
    return row


def simulation(task, events):
    try:
        return replay(
            task, events, float(current_app.config.get("LAB_SIMULATION_TIMEOUT", 1))
        )
    except LabError as exc:
        status = (
            503
            if exc.code == "LAB_SIMULATION_TIMEOUT"
            else 409
            if exc.code in ("STATE_CONFLICT", "DUPLICATE")
            else 404
            if exc.code == "NOT_FOUND"
            else 422
        )
        raise ApiError(exc.code, str(exc), status=status) from exc


def session_public(row, events=None):
    events = json.loads(row.event_log_json) if events is None else events
    board, state = simulation(json.loads(row.task_snapshot_json), events)
    public_events = [
        {k: v for k, v in e.items() if k != "request_hash"} for e in events
    ]
    return dict(
        id=row.id,
        task_id=row.task_id,
        task_version=row.task_version,
        task=json.loads(row.task_snapshot_json),
        class_id=row.class_id,
        owner_id=row.owner_id,
        kind=row.kind,
        version=len(events) + 1,
        saved_at=events[-1]["received_at"] if events else row.created_at,
        board=board,
        events=public_events,
        state=state,
    )


def attempt_public(row, detail=False):
    student = db_session().get(User, row.student_id)
    task = json.loads(row.task_snapshot_json)
    result = json.loads(row.result_json) if row.result_json else {}
    payload = dict(
        id=row.id,
        task_id=row.task_id,
        task_code=task["code"],
        task_version=task["version"],
        class_id=row.class_id,
        student_id=row.student_id,
        student_display_name=student.display_name,
        student_no=student.student_no,
        mode=row.mode,
        session_id=row.session_id,
        created_at=row.created_at,
        finished_at=row.finished_at,
        status=row.status,
        score=row.score,
        passed=bool(row.passed) if row.passed is not None else None,
        passed_checkpoints=result.get("passed_checkpoints"),
        total_checkpoints=result.get("total_checkpoints"),
        first_failure=result.get("first_failure"),
        error=json.loads(row.error_json) if row.error_json else None,
        suite_version=row.suite_version,
        engine_version=row.engine_version,
        file=dict(
            original_name=row.original_name,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
        )
        if row.mode == "circ"
        else None,
    )
    if detail:
        payload["task"] = task
        payload["session_snapshot"] = (
            json.loads(row.session_snapshot_json) if row.session_snapshot_json else None
        )
    return payload


def paged(statement, serializer):
    s = db_session()
    page, size = pagination()
    total = s.scalar(select(func.count()).select_from(statement.subquery()))
    rows = s.scalars(statement.limit(size).offset((page - 1) * size)).all()
    return success(
        [serializer(r) for r in rows], page=page, page_size=size, total=total
    )


@bp.get("/lab-tasks")
@roles_required("student", "teacher")
def tasks():
    current_class()
    stmt = (
        select(LabTask)
        .join(KnowledgePoint, LabTask.knowledge_id == KnowledgePoint.id)
        .where(LabTask.published == 1, KnowledgePoint.published == 1)
        .order_by(LabTask.code)
    )
    return paged(stmt, public_task)


@bp.get("/lab-tasks/<int:id>")
@roles_required("student", "teacher")
def task(id):
    current_class()
    return success(public_task(task_access(id)))


@bp.get("/lab-tasks/<int:id>/template")
@roles_required("student", "teacher")
def download_template(id):
    current_class()
    row = task_access(id)
    return Response(
        template(public_task(row)),
        mimetype="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{row.code}-5.0.0.circ"'
        },
    )


@bp.post("/lab-sessions")
@roles_required("student", "teacher")
def create_session():
    body = json_object({"task_id", "task_version", "class_id", "request_key"})
    for name in ("task_id", "task_version", "class_id"):
        integer(body.get(name), name)
    request_key = key(body.get("request_key"))
    s = db_session()
    user = current_user()
    sig = fingerprint(body)
    row = s.scalar(
        select(LabSession).where(
            LabSession.owner_id == user.id, LabSession.request_key == request_key
        )
    )
    if row:
        if row.request_hash != sig:
            raise ApiError("STATE_CONFLICT", "同一请求键不能用于不同内容")
        return success(session_public(row))
    class_access(body["class_id"], True)
    t = task_access(body["task_id"], body["task_version"])
    row = LabSession(
        task_id=t.id,
        owner_id=user.id,
        class_id=body["class_id"],
        kind="practice" if user.role == "student" else "demo",
        task_version=t.version,
        task_snapshot_json=dump(public_task(t)),
        board_json=dump(empty_board()),
        event_log_json="[]",
        request_key=request_key,
        request_hash=sig,
    )
    s.add(row)
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        row = s.scalar(
            select(LabSession).where(
                LabSession.owner_id == user.id, LabSession.request_key == request_key
            )
        )
        if row is None or row.request_hash != sig:
            raise ApiError("STATE_CONFLICT", "请求键冲突")
        return success(session_public(row))
    return success(session_public(row), 201)


@bp.get("/lab-sessions/<int:id>")
@roles_required("student", "teacher")
def get_session(id):
    row = session_access(id)
    events = json.loads(row.event_log_json)
    if "at_seq" in request.args:
        events = events[: sequence(len(events))]
    return success(session_public(row, events))


def sequence(maximum):
    value = request.args["at_seq"]
    if not value.isdigit() or not 0 <= int(value) <= maximum:
        raise ApiError("VALIDATION_ERROR", "回放序号超出记录范围")
    return int(value)


@bp.post("/lab-sessions/<int:id>/actions")
@roles_required("student", "teacher")
def action(id):
    body = json_object({"version", "action_key", "op", "payload"})
    integer(body.get("version"), "version")
    key(body.get("action_key"))
    s = db_session()
    row = session_access(id, True)
    events = json.loads(row.event_log_json)
    sig = fingerprint(body)
    for index, event in enumerate(events):
        if event["action_key"] == body["action_key"]:
            if event["request_hash"] != sig:
                raise ApiError("STATE_CONFLICT", "同一动作键不能修改内容")
            return success(session_public(row, events[: index + 1]))
    if row.version != body["version"]:
        raise ApiError("VERSION_CONFLICT", "实验已变化，请刷新后再操作")
    if len(events) >= 512:
        raise ApiError("LAB_LIMIT_EXCEEDED", "过程达到512条，请新建练习", status=422)
    now = now_utc()
    events.append(
        dict(
            seq=len(events) + 1,
            action_key=body["action_key"],
            op=body.get("op"),
            payload=body.get("payload"),
            request_hash=sig,
            received_at=now,
        )
    )
    board, state = simulation(json.loads(row.task_snapshot_json), events)
    count = s.execute(
        update(LabSession)
        .where(LabSession.id == id, LabSession.version == body["version"])
        .values(
            board_json=dump(board),
            event_log_json=dump(events),
            saved_at=now,
            updated_at=now,
            version=LabSession.version + 1,
        )
    ).rowcount
    if count != 1:
        s.rollback()
        raise ApiError("VERSION_CONFLICT", "实验已变化，请刷新后再操作")
    s.commit()
    s.refresh(row)
    return success(session_public(row))


@bp.post("/lab-attempts/wiring")
@roles_required("student")
def submit_wiring():
    body = json_object({"session_id", "session_version", "task_version", "request_key"})
    for name in ("session_id", "session_version", "task_version"):
        integer(body.get(name), name)
    request_key = key(body.get("request_key"))
    s = db_session()
    user = current_user()
    sig = fingerprint(dict(body, mode="wiring"))
    old = s.scalar(
        select(LabAttempt).where(
            LabAttempt.student_id == user.id, LabAttempt.request_key == request_key
        )
    )
    if old:
        if old.request_hash != sig:
            raise ApiError("STATE_CONFLICT", "同一请求键不能用于不同实验提交")
        return success(attempt_public(old, True))
    row = session_access(body["session_id"], True)
    if row.kind != "practice" or row.owner_id != user.id:
        raise ApiError("FORBIDDEN", "演示不能作为学生成绩提交")
    if row.version != body["session_version"]:
        raise ApiError("VERSION_CONFLICT", "过程已变化，请刷新")
    t = task_access(row.task_id, body["task_version"])
    snapshot = session_public(row)
    tests = json.loads(t.private_suite_json)
    task_json = dump(public_task(t))
    suite_json = t.private_suite_json
    s.rollback()  # never keep SQLite transaction open during simulation
    try:
        result = grade_wiring(json.loads(task_json), snapshot["board"], tests)
    except LabError as exc:
        raise ApiError(
            exc.code,
            str(exc),
            status=503 if exc.code == "LAB_SIMULATION_TIMEOUT" else 422,
        ) from exc
    # Revalidate all changing references after computation, inside a short write.
    row = session_access(body["session_id"], True)
    t = task_access(row.task_id, body["task_version"])
    if row.version != body["session_version"]:
        raise ApiError("VERSION_CONFLICT", "判分期间过程已变化，请重新提交")
    # Acquire SQLite's write serialization with a conditional no-op; this
    # closes the gap between the last version read and saving the grade.
    locked = s.execute(
        update(LabSession)
        .where(LabSession.id == row.id, LabSession.version == body["session_version"])
        .values(version=LabSession.version)
    ).rowcount
    if locked != 1:
        s.rollback()
        raise ApiError("VERSION_CONFLICT", "判分期间过程已变化")
    s.refresh(t)
    if t.version != body["task_version"] or not t.published:
        s.rollback()
        raise ApiError("VERSION_CONFLICT", "判分期间任务已变化")
    attempt = LabAttempt(
        task_id=t.id,
        student_id=user.id,
        class_id=row.class_id,
        mode="wiring",
        session_id=row.id,
        request_key=request_key,
        request_hash=sig,
        task_snapshot_json=task_json,
        suite_snapshot_json=suite_json,
        suite_version=t.suite_version,
        engine_version="ttl-engine-1",
        session_snapshot_json=dump(snapshot),
        status="done",
        score=result["score"],
        passed=int(result["passed"]),
        result_json=dump(result),
        finished_at=now_utc(),
    )
    s.add(attempt)
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        attempt = s.scalar(
            select(LabAttempt).where(
                LabAttempt.student_id == user.id, LabAttempt.request_key == request_key
            )
        )
        if attempt is None or attempt.request_hash != sig:
            raise ApiError("STATE_CONFLICT", "请求键冲突")
        return success(attempt_public(attempt, True))
    return success(attempt_public(attempt, True), 201)


@bp.get("/lab-attempts")
@roles_required("student", "teacher")
def attempts():
    user = current_user()
    stmt = select(LabAttempt)
    if user.role == "student":
        if "student_id" in request.args or "class_id" in request.args:
            raise ApiError("VALIDATION_ERROR", "学生只能读取本人实验记录")
        stmt = stmt.where(LabAttempt.student_id == user.id)
    else:
        try:
            class_id = int(request.args.get("class_id", ""))
        except ValueError:
            raise ApiError("VALIDATION_ERROR", "请选择班级")
        class_access(class_id)
        stmt = stmt.where(LabAttempt.class_id == class_id)
    for name in ("task_id", "student_id"):
        if name in request.args:
            try:
                value = int(request.args[name])
            except ValueError:
                raise ApiError("VALIDATION_ERROR", "筛选编号必须为整数")
            integer(value, name)
            stmt = stmt.where(getattr(LabAttempt, name) == value)
    for name, allowed in [
        ("mode", ("wiring", "circ")),
        ("status", ("queued", "running", "done", "error")),
    ]:
        if name in request.args:
            value = request.args[name]
            if value not in allowed:
                raise ApiError("VALIDATION_ERROR", "筛选值不合法")
            stmt = stmt.where(getattr(LabAttempt, name) == value)
    return paged(
        stmt.order_by(LabAttempt.created_at.desc(), LabAttempt.id.desc()),
        attempt_public,
    )


@bp.post("/lab-attempts/circ")
@roles_required("student")
def upload_circ():
    required = {"task_id", "task_version", "class_id", "request_key"}
    if (
        set(request.form) != required
        or set(request.files) != {"file"}
        or any(len(request.form.getlist(k)) != 1 for k in required)
        or len(request.files.getlist("file")) != 1
    ):
        raise ApiError(
            "VALIDATION_ERROR", "仅接受任务、版本、班级、请求键和一个电路文件"
        )
    body = dict(request.form)
    for name in ("task_id", "task_version", "class_id"):
        if not re.fullmatch(r"[1-9][0-9]{0,9}", body[name]):
            raise ApiError("VALIDATION_ERROR", "编号必须是正整数")
        body[name] = int(body[name])
    request_key = key(body["request_key"])
    file = request.files["file"]
    filename = file.filename or ""
    if not filename.lower().endswith(".circ"):
        raise ApiError("FILE_TYPE_UNSUPPORTED", "只支持.circ电路文件")
    filename = filename.replace("\\", "/").split("/")[-1]
    if len(filename) > 120 or any(ord(c) < 32 for c in filename):
        raise ApiError("VALIDATION_ERROR", "文件名过长或不合法")
    content = file.stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ApiError("FILE_TOO_LARGE", "电路文件不能超过2MiB")
    digest = hashlib.sha256(content).hexdigest()
    sig = fingerprint(dict(body, sha256=digest, mode="circ"))
    s = db_session()
    user = current_user()

    def existing():
        old = s.scalar(
            select(LabAttempt).where(
                LabAttempt.student_id == user.id, LabAttempt.request_key == request_key
            )
        )
        if old and old.request_hash != sig:
            raise ApiError("STATE_CONFLICT", "同一请求键不能用于不同文件或任务")
        return old

    old = existing()
    if old:
        return success(attempt_public(old, True))
    class_access(body["class_id"], True)
    t = task_access(body["task_id"], body["task_version"])
    task = public_task(t)
    try:
        validate_circ(content, task)
    except LabError as exc:
        raise ApiError(
            exc.code, str(exc), status=413 if exc.code == "FILE_TOO_LARGE" else 422
        ) from exc
    if not worker_available(current_app.config):
        raise ApiError(
            "LAB_ENGINE_UNAVAILABLE",
            "测评服务未就绪，请联系教师启动worker后重试",
            status=503,
        )
    # A user-row write serializes the capacity/rate check across simultaneous uploads.
    s.execute(update(User).where(User.id == user.id).values(version=User.version))
    old = existing()
    if old:
        s.rollback()
        return success(attempt_public(old, True))
    pending = s.scalar(
        select(func.count())
        .select_from(LabAttempt)
        .where(
            LabAttempt.student_id == user.id,
            LabAttempt.mode == "circ",
            LabAttempt.status.in_(("queued", "running")),
        )
    )
    if pending >= 2:
        raise ApiError(
            "RATE_LIMITED", "最多同时等待2个测评任务", headers={"Retry-After": "10"}
        )
    latest = s.scalar(
        select(LabAttempt)
        .where(LabAttempt.student_id == user.id, LabAttempt.mode == "circ")
        .order_by(LabAttempt.created_at.desc(), LabAttempt.id.desc())
        .limit(1)
    )
    if (
        latest
        and (
            datetime.now(timezone.utc)
            - datetime.fromisoformat(latest.created_at.replace("Z", "+00:00"))
        ).total_seconds()
        < 10
    ):
        raise ApiError(
            "RATE_LIMITED", "两次上传至少间隔10秒", headers={"Retry-After": "10"}
        )
    s.refresh(t)
    if t.version != body["task_version"] or not t.published:
        raise ApiError("VERSION_CONFLICT", "任务已更新，请重新进入")
    storage_key = uuid.uuid4().hex + ".circ"
    root = storage_root(current_app.config)
    root.mkdir(parents=True, exist_ok=True)
    path = root / storage_key
    row = LabAttempt(
        task_id=t.id,
        student_id=user.id,
        class_id=body["class_id"],
        mode="circ",
        request_key=request_key,
        request_hash=sig,
        task_snapshot_json=dump(task),
        suite_snapshot_json=t.private_suite_json,
        suite_version=t.suite_version,
        engine_version=ENGINE_VERSION,
        storage_key=storage_key,
        original_name=filename,
        size_bytes=len(content),
        sha256=digest,
        status="queued",
    )
    try:
        with path.open("xb") as stream:
            stream.write(content)
        s.add(row)
        s.commit()
    except Exception:
        s.rollback()
        path.unlink(missing_ok=True)
        raise
    return success(attempt_public(row, True), 202)


@bp.get("/lab-attempts/<int:id>")
@roles_required("student", "teacher")
def get_attempt(id):
    row = attempt_access(id)
    payload = attempt_public(row, True)
    if "at_seq" in request.args:
        snapshot = payload["session_snapshot"]
        if snapshot is None:
            raise ApiError("VALIDATION_ERROR", "文件记录不包含接线过程")
        events = snapshot["events"][: sequence(len(snapshot["events"]))]
        board, state = simulation(payload["task"], events)
        payload["session_snapshot"] = dict(
            snapshot, events=events, board=board, state=state
        )
    return success(payload)


@bp.get("/lab-attempts/<int:id>/file")
@roles_required("student", "teacher")
def download_circ(id):
    row = attempt_access(id)
    if row.mode != "circ":
        raise ApiError("NOT_FOUND", "该记录没有电路文件")
    if not re.fullmatch(r"[a-f0-9]{32}\.circ", row.storage_key or ""):
        raise ApiError("ARTIFACT_UNAVAILABLE", "附件记录无效", status=503)
    path = storage_root(current_app.config) / row.storage_key
    try:
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != row.sha256:
            raise ApiError(
                "ARTIFACT_UNAVAILABLE", "附件校验失败，请恢复备份", status=503
            )
    except OSError:
        raise ApiError("ARTIFACT_UNAVAILABLE", "附件不可读取，请恢复备份", status=503)
    import io

    return send_file(
        io.BytesIO(content),
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=row.original_name,
        max_age=0,
    )


@bp.get("/analytics/labs")
@roles_required("teacher")
def summary():
    try:
        class_id = int(request.args.get("class_id", ""))
    except ValueError:
        raise ApiError("VALIDATION_ERROR", "请选择班级")
    class_access(class_id)
    s = db_session()
    task_id = request.args.get("task_id")
    tasks = s.scalars(select(LabTask).order_by(LabTask.code)).all()
    if task_id:
        try:
            tid = int(task_id)
        except ValueError:
            raise ApiError("VALIDATION_ERROR", "任务编号错误")
        tasks = [t for t in tasks if t.id == tid]
    active = set(
        s.scalars(
            select(Enrollment.student_id)
            .join(User, Enrollment.student_id == User.id)
            .where(
                Enrollment.class_id == class_id,
                Enrollment.active == 1,
                User.active == 1,
                User.role == "student",
            )
        ).all()
    )
    rows = s.scalars(select(LabAttempt).where(LabAttempt.class_id == class_id)).all()
    items = []
    for t in tasks:
        for mode in ("wiring", "circ"):
            records = [
                r
                for r in rows
                if r.task_id == t.id and r.mode == mode and r.student_id in active
            ]
            done = [r for r in records if r.status == "done"]
            participants = {r.student_id for r in done}
            passed = {r.student_id for r in done if r.passed}
            items.append(
                dict(
                    task_id=t.id,
                    mode=mode,
                    participant_count=len(participants),
                    attempt_count=len(done),
                    passed_student_count=len(passed),
                    pass_rate=len(passed) / len(participants) if participants else None,
                    queued_count=sum(r.status == "queued" for r in records),
                    running_count=sum(r.status == "running" for r in records),
                    error_count=sum(r.status == "error" for r in records),
                )
            )
    return success(dict(class_id=class_id, tasks=items))
