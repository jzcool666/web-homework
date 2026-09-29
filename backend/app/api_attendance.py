"""E028—E034：考勤与请假（SPEC-002 第 4 节）。

规则要点：
- 签到窗口 [opens_at, closes_at)：now < late_at 记 present，否则记 late；
  时间一律取服务器当前 UTC 时间，不采信客户端提交的任何时间。
- 六位签到码只保存 SHA-256 散列，明文仅在创建与显式重置的响应中出现一次。
- 结算只把仍 pending 的记录改为 absent，已签到（present/late）与已请假（leave）
  不被覆盖；重复结算结果一致。无访问时不结算，未结算的 pending 不显示为缺勤。
- 请假批准把 pending/absent 改成 leave；已签到者审批返回 409，已批准者不能再签到。
- 改码使旧码立即失效；同一人同一任务一分钟内 5 次错误码后 429。
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from .auth import current_user, login_required, roles_required
from .errors import ApiError, success
from .models import Enrollment, SchoolClass, User
from .models_attendance import (
    LEAVE_APPROVED,
    LEAVE_REJECTED,
    LEAVE_STATUSES,
    RECORD_ABSENT,
    RECORD_LATE,
    RECORD_LEAVE,
    RECORD_PENDING,
    RECORD_PRESENT,
    SIGNED_STATUSES,
    AttendanceRecord,
    AttendanceTask,
    LeaveRequest,
    attendance_record_public,
    attendance_task_public,
    leave_request_public,
)
from .store import db_session
from .validation import json_object, pagination, text_field

bp = Blueprint("attendance", __name__)

CODE_RE = re.compile(r"^\d{6}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

CODE_FAIL_LIMIT = 5
CODE_FAIL_WINDOW = timedelta(minutes=1)
# 进程内限流：与 auth.py 的登录限流同构，单实例重启会清空，部署说明中保留该限制。
_code_failures: dict[str, list[datetime]] = {}


# ---- 时间 ----

def now_utc_dt() -> datetime:
    return datetime.now(timezone.utc)


def format_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(TIMESTAMP_FORMAT)


def parse_utc(value: str) -> datetime:
    return datetime.strptime(value, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)


# ---- 签到码 ----

def new_code() -> str:
    """六位数字码，允许前导零。"""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(task_id: int, code: str) -> str:
    """DBD 第 1 节要求签到码只存散列；表未定义盐列，这里用任务号做域分隔。"""
    return hashlib.sha256(f"attendance-task:{task_id}:{code}".encode("utf-8")).hexdigest()


def code_rate_key(user_id: int, task_id: int) -> str:
    return f"{user_id}:{task_id}"


def check_code_rate(key: str) -> None:
    now = now_utc_dt()
    stamps = [t for t in _code_failures.get(key, []) if now - t < CODE_FAIL_WINDOW]
    _code_failures[key] = stamps
    if len(stamps) >= CODE_FAIL_LIMIT:
        retry_after = int((CODE_FAIL_WINDOW - (now - min(stamps))).total_seconds()) + 1
        raise ApiError(
            "RATE_LIMITED",
            "签到码错误次数过多，请稍后再试",
            details={"retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


def record_code_failure(key: str) -> None:
    _code_failures.setdefault(key, []).append(now_utc_dt())


def clear_code_failures(key: str) -> None:
    _code_failures.pop(key, None)


# ---- 字段校验 ----

def _fields_error(name: str, rule: str):
    raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: rule}})


def _int_field(body: dict, name: str, *, minimum: int = 1) -> int:
    value = body.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        _fields_error(name, "必须是正整数")
    return value


def _timestamp_field(body: dict, name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not TIMESTAMP_RE.match(value):
        _fields_error(name, "必须是带 Z 的 UTC 时间，如 2026-09-29T01:00:00Z")
    try:
        parse_utc(value)
    except ValueError:
        _fields_error(name, "不是有效时间")
    return value


def _reason_field(body: dict, name: str = "reason") -> str:
    value = text_field(body, name, rule="1—300 个字符", min_len=1, max_len=300).strip()
    if not value:
        _fields_error(name, "1—300 个字符")
    return value


def _optional_note(body: dict, name: str = "review_note") -> str | None:
    if name not in body:
        return None
    value = body[name]
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 200:
        _fields_error(name, "不超过 200 个字符")
    return value.strip() or None


# ---- 权限与名单 ----

def _task_or_404(session, task_id: int) -> AttendanceTask:
    task = session.get(AttendanceTask, task_id)
    if task is None:
        raise ApiError("NOT_FOUND", "签到任务不存在")
    return task


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


def _require_task_teacher(session, task: AttendanceTask) -> AttendanceTask:
    _require_class_teacher(session, task.class_id)
    return task


def _roster_student_ids(session, class_id: int) -> list[int]:
    """有效班级名单：入班关系有效且学生账号有效（DBD 第 2 节）。"""
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


def _student_map(session, student_ids) -> dict[int, User]:
    ids = {sid for sid in student_ids if sid is not None}
    if not ids:
        return {}
    return {u.id: u for u in session.scalars(select(User).where(User.id.in_(ids)))}


def _settle_task(session, task: AttendanceTask, now: datetime | None = None) -> bool:
    """把已结束任务中仍 pending 的记录结算为 absent；幂等，可重复调用。

    返回是否已到期。settled_at 只记首次结算时间，重复调用结果完全一致。
    """
    now = now or now_utc_dt()
    if parse_utc(task.closes_at) > now:
        return False
    if task.settled_at is None:
        task.settled_at = format_utc(now)
    session.execute(
        update(AttendanceRecord)
        .where(
            AttendanceRecord.task_id == task.id,
            AttendanceRecord.status == RECORD_PENDING,
        )
        .values(status=RECORD_ABSENT)
        .execution_options(synchronize_session=False)
    )
    return True


def _task_counts(session, task_id: int) -> dict:
    rows = session.execute(
        select(AttendanceRecord.status, func.count())
        .where(AttendanceRecord.task_id == task_id)
        .group_by(AttendanceRecord.status)
    ).all()
    counts = {name: 0 for name in (RECORD_PRESENT, RECORD_LATE, RECORD_LEAVE, RECORD_ABSENT)}
    for status, number in rows:
        counts[status] = number
    return counts


def _paginate(session, stmt, page: int, page_size: int):
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return rows, total


def _int_arg(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError("INVALID_REQUEST", f"{name} 必须是正整数")
    if value < 1:
        raise ApiError("INVALID_REQUEST", f"{name} 必须是正整数")
    return value


# ---- E028 /attendance-tasks ----

@bp.get("/attendance-tasks")
@login_required
def list_attendance_tasks():
    page, page_size = pagination()
    raw = request.args.get("class_id")
    if raw is None:
        raise ApiError("INVALID_REQUEST", "缺少必填查询参数 class_id")
    class_id = _int_arg(raw, "class_id")

    session = db_session()
    _require_class_read(session, class_id)
    # 读取可触发结束任务结算（SPEC-002 第 4 节第 3 条）
    pending_settlement = list(
        session.scalars(
            select(AttendanceTask).where(
                AttendanceTask.class_id == class_id, AttendanceTask.settled_at.is_(None)
            )
        )
    )
    for task in pending_settlement:
        _settle_task(session, task)
    session.commit()

    stmt = (
        select(AttendanceTask)
        .where(AttendanceTask.class_id == class_id)
        .order_by(AttendanceTask.created_at.desc(), AttendanceTask.id.desc())
    )
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [attendance_task_public(t) for t in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@bp.post("/attendance-tasks")
@roles_required("teacher")
def create_attendance_task():
    body = json_object(["class_id", "title", "opens_at", "late_at", "closes_at"])
    class_id = _int_field(body, "class_id")
    title = text_field(body, "title", rule="1—100 个字符", min_len=1, max_len=100).strip()
    if not title:
        _fields_error("title", "1—100 个字符")
    opens_at = _timestamp_field(body, "opens_at")
    late_at = _timestamp_field(body, "late_at")
    closes_at = _timestamp_field(body, "closes_at")
    if not (opens_at <= late_at < closes_at):
        _fields_error("late_at", "必须满足 opens_at ≤ late_at < closes_at")

    session = db_session()
    school_class = _require_class_teacher(session, class_id)
    if not school_class.active:
        raise ApiError("STATE_CONFLICT", "已停用的班级不能发布签到任务")

    task = AttendanceTask(
        class_id=class_id,
        title=title,
        opens_at=opens_at,
        late_at=late_at,
        closes_at=closes_at,
        code_hash="",
        settled_at=None,
        owner_id=current_user().id,
    )
    session.add(task)
    session.flush()  # 先取到任务号，签到码散列以任务号为域分隔
    code = new_code()
    task.code_hash = hash_code(task.id, code)

    # 发布时复制有效班级名单为 pending
    for student_id in _roster_student_ids(session, class_id):
        session.add(
            AttendanceRecord(
                task_id=task.id, student_id=student_id, status=RECORD_PENDING, signed_at=None
            )
        )
    session.commit()

    payload = attendance_task_public(task)
    payload["code"] = code  # 明文码只在创建响应中出现一次
    return success(payload, 201)


# ---- E029 /attendance-tasks/{id}/sign-ins ----

@bp.post("/attendance-tasks/<int:task_id>/sign-ins")
@roles_required("student")
def sign_in(task_id: int):
    body = json_object(["code"])
    code = body.get("code")
    if not isinstance(code, str) or not CODE_RE.match(code):
        _fields_error("code", "必须是 6 位数字")

    session = db_session()
    task = _task_or_404(session, task_id)
    user = current_user()
    record = session.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.task_id == task.id, AttendanceRecord.student_id == user.id
        )
    )
    if record is None:
        # 不在本任务名单（含跨班学生）：按跨班对象处理为 404
        raise ApiError("NOT_FOUND", "签到任务不存在")
    school_class = _require_class_read(session, task.class_id)
    if not school_class.active:
        raise ApiError("STATE_CONFLICT", "班级已停用，不能签到")

    now = now_utc_dt()
    if not (parse_utc(task.opens_at) <= now < parse_utc(task.closes_at)):
        raise ApiError("DEADLINE_PASSED", "当前不在签到时间内")

    if record.status == RECORD_LEAVE:
        raise ApiError("STATE_CONFLICT", "已批准的请假不能再签到")

    key = code_rate_key(user.id, task.id)
    check_code_rate(key)
    if hash_code(task.id, code) != task.code_hash:
        record_code_failure(key)
        _fields_error("code", "签到码不正确")
    clear_code_failures(key)

    if record.status in SIGNED_STATUSES:
        # 重复有效签到返回原记录，不刷新 signed_at
        return success(attendance_record_public(record, user))

    status = RECORD_PRESENT if now < parse_utc(task.late_at) else RECORD_LATE
    result = session.execute(
        update(AttendanceRecord)
        .where(AttendanceRecord.id == record.id, AttendanceRecord.status == RECORD_PENDING)
        .values(status=status, signed_at=format_utc(now))
        .execution_options(synchronize_session=False)
    )
    session.commit()

    fresh = session.get(AttendanceRecord, record.id, populate_existing=True)
    if result.rowcount == 0 and fresh.status not in SIGNED_STATUSES:
        # 并发下状态已被改（例如审批改成 leave）：不覆盖既有事实
        raise ApiError("STATE_CONFLICT", "签到状态已变化，请刷新后查看")
    return success(attendance_record_public(fresh, user))


# ---- E030 /attendance-tasks/{id}/settlements ----

@bp.post("/attendance-tasks/<int:task_id>/settlements")
@roles_required("teacher")
def settle_attendance_task(task_id: int):
    json_object([])
    session = db_session()
    task = _require_task_teacher(session, _task_or_404(session, task_id))

    now = now_utc_dt()
    if parse_utc(task.closes_at) > now:
        raise ApiError("DEADLINE_PASSED", "签到尚未结束，不能结算")

    _settle_task(session, task, now)
    counts = _task_counts(session, task.id)
    session.commit()
    return success({"settled_at": task.settled_at, "counts": counts})


# ---- E031 /attendance-tasks/{id}/records ----

@bp.get("/attendance-tasks/<int:task_id>/records")
@login_required
def list_attendance_records(task_id: int):
    page, page_size = pagination()
    session = db_session()
    task = _task_or_404(session, task_id)
    user = current_user()

    stmt = select(AttendanceRecord).where(AttendanceRecord.task_id == task.id)
    if user.role == "teacher":
        _require_task_teacher(session, task)
    elif user.role == "student":
        if session.scalar(
            select(AttendanceRecord.id).where(
                AttendanceRecord.task_id == task.id, AttendanceRecord.student_id == user.id
            )
        ) is None:
            raise ApiError("NOT_FOUND", "签到任务不存在")
        stmt = stmt.where(AttendanceRecord.student_id == user.id)  # 学生仅本人
    else:
        raise ApiError("FORBIDDEN", "管理员不参与课堂教学操作")

    # 读取触发结束任务结算：未结算的 pending 不显示为缺勤，结算后才显示
    if _settle_task(session, task):
        session.commit()

    stmt = stmt.order_by(AttendanceRecord.created_at.desc(), AttendanceRecord.id.desc())
    rows, total = _paginate(session, stmt, page, page_size)
    students = _student_map(session, [r.student_id for r in rows])
    return success(
        [attendance_record_public(r, students.get(r.student_id)) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


# ---- E032 /attendance-tasks/{id}/code-resets ----

@bp.post("/attendance-tasks/<int:task_id>/code-resets")
@roles_required("teacher")
def reset_attendance_code(task_id: int):
    body = json_object(["version"])
    version = _int_field(body, "version")

    session = db_session()
    task = _require_task_teacher(session, _task_or_404(session, task_id))
    if version != task.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "签到任务已被修改，请刷新后重试",
            {"expected_version": version, "current_version": task.version},
        )
    if parse_utc(task.closes_at) <= now_utc_dt():
        raise ApiError("DEADLINE_PASSED", "签到已结束，不能再重置签到码")
    if not session.get(SchoolClass, task.class_id).active:
        raise ApiError("STATE_CONFLICT", "班级已停用，不能重置签到码")

    code = new_code()
    task.code_hash = hash_code(task.id, code)  # 旧码立即失效
    task.version += 1
    session.commit()
    return success({"code": code, "version": task.version})


# ---- E033 /leave-requests ----

@bp.get("/leave-requests")
@login_required
def list_leave_requests():
    page, page_size = pagination()
    session = db_session()
    user = current_user()
    if user.role == "admin":
        raise ApiError("FORBIDDEN", "管理员不参与课堂教学操作")

    raw_class = request.args.get("class_id")
    if raw_class is not None:
        _require_class_read(session, _int_arg(raw_class, "class_id"))

    stmt = select(LeaveRequest)
    if user.role == "teacher":
        stmt = stmt.join(AttendanceTask, AttendanceTask.id == LeaveRequest.task_id).join(
            SchoolClass, SchoolClass.id == AttendanceTask.class_id
        ).where(SchoolClass.teacher_id == user.id)
    else:
        stmt = stmt.where(LeaveRequest.student_id == user.id)

    raw_task = request.args.get("task_id")
    if raw_task is not None:
        stmt = stmt.where(LeaveRequest.task_id == _int_arg(raw_task, "task_id"))
    if raw_class is not None:
        stmt = stmt.where(
            LeaveRequest.task_id.in_(
                select(AttendanceTask.id).where(
                    AttendanceTask.class_id == _int_arg(raw_class, "class_id")
                )
            )
        )
    status = request.args.get("status")
    if status is not None:
        if status not in LEAVE_STATUSES:
            raise ApiError(
                "INVALID_REQUEST", "status 取值不合法", {"allowed": list(LEAVE_STATUSES)}
            )
        stmt = stmt.where(LeaveRequest.status == status)

    stmt = stmt.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc())
    rows, total = _paginate(session, stmt, page, page_size)
    students = _student_map(session, [r.student_id for r in rows])
    return success(
        [leave_request_public(r, students.get(r.student_id)) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@bp.post("/leave-requests")
@roles_required("student")
def create_leave_request():
    body = json_object(["task_id", "reason"])
    task_id = _int_field(body, "task_id")
    reason = _reason_field(body)

    session = db_session()
    task = _task_or_404(session, task_id)
    user = current_user()
    if session.scalar(
        select(AttendanceRecord.id).where(
            AttendanceRecord.task_id == task.id, AttendanceRecord.student_id == user.id
        )
    ) is None:
        raise ApiError("NOT_FOUND", "签到任务不存在")
    school_class = _require_class_read(session, task.class_id)
    if not school_class.active:
        raise ApiError("STATE_CONFLICT", "班级已停用，不能申请请假")

    if parse_utc(task.closes_at) <= now_utc_dt():
        raise ApiError("DEADLINE_PASSED", "签到已结束，不能再申请请假")

    leave = LeaveRequest(
        task_id=task.id,
        student_id=user.id,
        reason=reason,
        status="pending",
        reviewer_id=None,
        review_note=None,
        reviewed_at=None,
    )
    session.add(leave)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiError("DUPLICATE", "已提交过该任务的请假申请")
    return success(leave_request_public(leave, user), 201)


# ---- E034 /leave-requests/{id} ----

@bp.patch("/leave-requests/<int:leave_id>")
@roles_required("teacher")
def review_leave_request(leave_id: int):
    body = json_object(["version", "status", "review_note"])
    version = _int_field(body, "version")
    status = body.get("status")
    if status not in (LEAVE_APPROVED, LEAVE_REJECTED):
        _fields_error("status", "只能是 approved 或 rejected")
    note = _optional_note(body)

    session = db_session()
    leave = session.get(LeaveRequest, leave_id)
    if leave is None:
        raise ApiError("NOT_FOUND", "请假申请不存在")
    task = _require_task_teacher(session, _task_or_404(session, leave.task_id))

    if version != leave.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "请假申请已被处理，请刷新后重试",
            {"expected_version": version, "current_version": leave.version},
        )
    if leave.status != "pending":
        raise ApiError("STATE_CONFLICT", "该请假申请已审批，不能重复处理")

    record = session.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.task_id == task.id, AttendanceRecord.student_id == leave.student_id
        )
    )
    if record is not None and record.status in SIGNED_STATUSES:
        # 先签到后请假：不覆盖已发生的签到事实
        raise ApiError("STATE_CONFLICT", "该学生已签到，不能改判为请假")

    leave.status = status
    leave.reviewer_id = current_user().id
    leave.review_note = note
    leave.reviewed_at = format_utc(now_utc_dt())
    leave.version += 1

    if status == LEAVE_APPROVED and record is not None and record.status in (
        RECORD_PENDING,
        RECORD_ABSENT,
    ):
        record.status = RECORD_LEAVE
    session.commit()

    student = session.get(User, leave.student_id)
    return success(leave_request_public(leave, student))
