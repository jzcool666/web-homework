"""E006—E010：管理员账号管理、班级管理与入班关系（SPEC-001）。

权限要点：
- 集合写操作仅管理员；教师只能读本人任教班级（其他班级一律 404）。
- teacher_id 改变即时影响教学数据权限，因为权限始终由 classes.teacher_id 现算。
"""

from __future__ import annotations

from flask import Blueprint, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .auth import current_user, invalidate_user_sessions, login_required, roles_required
from .errors import ApiError, success
from .models import (
    ROLES,
    Enrollment,
    SchoolClass,
    User,
    class_public,
    enrollment_public,
    now_utc,
    user_public,
)
from .security import hash_password
from .store import db_session
from .validation import (
    display_name,
    json_object,
    login_name,
    pagination,
    password,
    student_no,
    text_field,
)

bp = Blueprint("admin", __name__)


def _int_field(body: dict, name: str, *, minimum: int = 1) -> int:
    value = body.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: "必须是正整数"}})
    return value


def _bool_field(body: dict, name: str) -> bool:
    value = body.get(name)
    if not isinstance(value, bool):
        raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {name: "必须是布尔值"}})
    return value


def _paginate(session, stmt, page: int, page_size: int):
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return rows, total


def _require_class_access(school_class: SchoolClass | None) -> SchoolClass:
    """管理员可访问任意班级；教师仅本人任教班级，其余按 404 处理。"""
    user = current_user()
    if school_class is None:
        raise ApiError("NOT_FOUND", "班级不存在")
    if user.role != "admin" and school_class.teacher_id != user.id:
        raise ApiError("NOT_FOUND", "班级不存在")
    return school_class


# ---- E006 /users ----

@bp.get("/users")
@roles_required("admin")
def list_users():
    page, page_size = pagination()
    session = db_session()
    stmt = select(User)

    role = request.args.get("role")
    if role is not None:
        if role not in ROLES:
            raise ApiError("INVALID_REQUEST", "role 取值不合法", {"allowed": list(ROLES)})
        stmt = stmt.where(User.role == role)

    active = request.args.get("active")
    if active is not None:
        if active not in {"true", "false", "1", "0"}:
            raise ApiError("INVALID_REQUEST", "active 取值不合法", {"allowed": ["true", "false"]})
        stmt = stmt.where(User.active == (1 if active in {"true", "1"} else 0))

    stmt = stmt.order_by(User.created_at.desc(), User.id.desc())
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [user_public(u) for u in rows], page=page, page_size=page_size, total=total
    )


@bp.post("/users")
@roles_required("admin")
def create_user():
    body = json_object(["login_name", "student_no", "display_name", "password", "role"])
    role = body.get("role")
    if role not in ROLES:
        raise ApiError("VALIDATION_ERROR", "role 取值不合法", {"fields": {"role": "student/teacher/admin"}})

    data = {
        "login_name": login_name(body),
        "display_name": display_name(body),
        "password": password(body),
    }
    if role == "student":
        data["student_no"] = student_no(body)
    else:
        raw = body.get("student_no")
        if raw is not None:
            raise ApiError(
                "VALIDATION_ERROR", "教师和管理员不应提供学号", {"fields": {"student_no": "不适用"}}
            )
        data["student_no"] = None

    session = db_session()
    if session.scalar(select(User.id).where(User.login_name == data["login_name"])):
        raise ApiError("DUPLICATE", "登录名已被占用", {"fields": {"login_name": "已存在"}})
    if data["student_no"] and session.scalar(
        select(User.id).where(User.student_no == data["student_no"])
    ):
        raise ApiError("DUPLICATE", "学号已被占用", {"fields": {"student_no": "已存在"}})

    user = User(
        login_name=data["login_name"],
        student_no=data["student_no"],
        display_name=data["display_name"],
        password_hash=hash_password(data["password"]),
        role=role,
        active=1,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiError("DUPLICATE", "登录名或学号已被占用")

    return success(user_public(user), 201)


# ---- E007 /users/{id} ----

@bp.patch("/users/<int:user_id>")
@roles_required("admin")
def patch_user(user_id: int):
    body = json_object(["version", "active", "role"])
    session = db_session()
    target = session.get(User, user_id)
    if target is None:
        raise ApiError("NOT_FOUND", "用户不存在")

    version = body.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ApiError("VALIDATION_ERROR", "version 必须是整数", {"fields": {"version": "必填"}})
    if version != target.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "用户已被修改，请刷新后重试",
            {"expected_version": version, "current_version": target.version},
        )

    new_role = body.get("role", target.role)
    if new_role not in ROLES:
        raise ApiError("VALIDATION_ERROR", "role 取值不合法", {"fields": {"role": "student/teacher/admin"}})
    new_active = body.get("active", bool(target.active))
    if not isinstance(new_active, bool):
        raise ApiError("VALIDATION_ERROR", "active 必须是布尔值", {"fields": {"active": "布尔值"}})

    loses_admin = target.role == "admin" and (new_role != "admin" or not new_active)
    if loses_admin:
        active_admins = session.scalar(
            select(func.count()).select_from(User).where(User.role == "admin", User.active == 1)
        )
        if (active_admins or 0) <= 1:
            raise ApiError(
                "STATE_CONFLICT",
                "不能禁用或降级最后一名有效管理员",
                {"active_admins": active_admins or 0},
            )

    role_changed = new_role != target.role
    deactivated = bool(target.active) and not new_active
    if role_changed:
        # 班级与入班关系以角色为前提；先处理关联关系，避免留下无教师班级
        # 或非学生的有效入班记录。
        if target.role == "teacher" and session.scalar(
            select(SchoolClass.id).where(SchoolClass.teacher_id == target.id).limit(1)
        ) is not None:
            raise ApiError("STATE_CONFLICT", "请先将该教师任教的班级转交其他教师")
        if target.role == "student" and session.scalar(
            select(Enrollment.student_id).where(
                Enrollment.student_id == target.id, Enrollment.active == 1
            ).limit(1)
        ) is not None:
            raise ApiError("STATE_CONFLICT", "请先将该学生移出当前班级")
        if new_role == "student" and not target.student_no:
            raise ApiError("STATE_CONFLICT", "没有学号的账号不能改为学生")
    target.role = new_role
    target.active = 1 if new_active else 0
    target.version += 1

    if role_changed or deactivated:
        session.flush()
        # 角色变更或停用后旧会话立即失效（DBD 第 2 节）
        invalidate_user_sessions(target.id)

    session.commit()
    return success(user_public(target))


# ---- E008 /classes ----

@bp.get("/classes")
@login_required
def list_classes():
    page, page_size = pagination()
    session = db_session()
    user = current_user()
    stmt = select(SchoolClass)

    if user.role == "teacher":
        stmt = stmt.where(SchoolClass.teacher_id == user.id)
    elif user.role == "student":
        stmt = stmt.join(Enrollment, Enrollment.class_id == SchoolClass.id).where(
            Enrollment.student_id == user.id, Enrollment.active == 1
        )
    # admin：全部班级

    stmt = stmt.order_by(SchoolClass.created_at.desc(), SchoolClass.id.desc())
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [class_public(c) for c in rows], page=page, page_size=page_size, total=total
    )


@bp.post("/classes")
@roles_required("admin")
def create_class():
    body = json_object(["name", "teacher_id"])
    name = text_field(body, "name", rule="1—80 个字符", min_len=1, max_len=80).strip()
    if not name:
        raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {"name": "1—80 个字符"}})
    teacher_id = _int_field(body, "teacher_id")

    session = db_session()
    teacher = session.get(User, teacher_id)
    if teacher is None or teacher.role != "teacher" or not teacher.active:
        raise ApiError(
            "VALIDATION_ERROR",
            "任课教师必须是有效的教师账号",
            {"fields": {"teacher_id": "不存在或不是有效教师"}},
        )

    school_class = SchoolClass(name=name, teacher_id=teacher_id, active=1)
    session.add(school_class)
    session.commit()
    return success(class_public(school_class), 201)


# ---- E009 /classes/{id} ----

@bp.patch("/classes/<int:class_id>")
@roles_required("admin")
def patch_class(class_id: int):
    body = json_object(["version", "name", "teacher_id", "active"])
    session = db_session()
    school_class = session.get(SchoolClass, class_id)
    if school_class is None:
        raise ApiError("NOT_FOUND", "班级不存在")

    version = body.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ApiError("VALIDATION_ERROR", "version 必须是整数", {"fields": {"version": "必填"}})
    if version != school_class.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "班级已被修改，请刷新后重试",
            {"expected_version": version, "current_version": school_class.version},
        )

    if "name" in body:
        name = text_field(body, "name", rule="1—80 个字符", min_len=1, max_len=80).strip()
        if not name:
            raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {"name": "1—80 个字符"}})
        school_class.name = name

    if "teacher_id" in body:
        teacher_id = _int_field(body, "teacher_id")
        teacher = session.get(User, teacher_id)
        if teacher is None or teacher.role != "teacher" or not teacher.active:
            raise ApiError(
                "VALIDATION_ERROR",
                "任课教师必须是有效的教师账号",
                {"fields": {"teacher_id": "不存在或不是有效教师"}},
            )
        # 换教师后，权限随 teacher_id 立即变化（无需额外迁移动作）
        school_class.teacher_id = teacher_id

    if "active" in body:
        school_class.active = 1 if _bool_field(body, "active") else 0

    if not {"name", "teacher_id", "active"} & set(body):
        raise ApiError("VALIDATION_ERROR", "没有可更新的字段")

    school_class.version += 1
    session.commit()
    return success(class_public(school_class))


# ---- E010 /classes/{id}/enrollments ----

@bp.get("/classes/<int:class_id>/enrollments")
@roles_required("admin", "teacher")
def list_enrollments(class_id: int):
    """名单读取限管理员与任课教师；学生不在允许集合内，按 403 处理。"""
    page, page_size = pagination()
    session = db_session()
    school_class = _require_class_access(session.get(SchoolClass, class_id))

    stmt = (
        select(Enrollment)
        .where(Enrollment.class_id == school_class.id)
        .order_by(Enrollment.joined_at.desc(), Enrollment.student_id.desc())
    )
    rows, total = _paginate(session, stmt, page, page_size)
    return success(
        [enrollment_public(e) for e in rows], page=page, page_size=page_size, total=total
    )


@bp.put("/classes/<int:class_id>/enrollments")
@roles_required("admin")
def set_enrollment(class_id: int):
    body = json_object(["student_id", "active"])
    student_id = _int_field(body, "student_id")
    active = _bool_field(body, "active")

    session = db_session()
    school_class = session.get(SchoolClass, class_id)
    if school_class is None:
        raise ApiError("NOT_FOUND", "班级不存在")

    student = session.get(User, student_id)
    if student is None or student.role != "student":
        raise ApiError(
            "VALIDATION_ERROR", "只能把学生加入班级", {"fields": {"student_id": "不是学生账号"}}
        )

    enrollment = session.get(Enrollment, (class_id, student_id))

    if active:
        if not school_class.active:
            raise ApiError("STATE_CONFLICT", "已停用的班级不能加入学生")
        if not student.active:
            raise ApiError("STATE_CONFLICT", "已停用的学生不能加入班级")
        # 学生最多一个有效班级：已在别的班级有效则冲突
        other = session.scalar(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.active == 1,
                Enrollment.class_id != class_id,
            )
        )
        if other is not None:
            raise ApiError(
                "DUPLICATE",
                "学生已在其他班级，需先退出原班级",
                {"current_class_id": other.class_id},
            )
        if enrollment is None:
            enrollment = Enrollment(
                class_id=class_id, student_id=student_id, active=1, joined_at=now_utc()
            )
            session.add(enrollment)
        else:
            enrollment.active = 1
            enrollment.left_at = None
    else:
        if enrollment is None or not enrollment.active:
            # 幂等：已经是离开状态
            if enrollment is None:
                raise ApiError("NOT_FOUND", "入班记录不存在")
        enrollment.active = 0
        enrollment.left_at = now_utc()

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiError("DUPLICATE", "学生已有有效班级")

    return success(enrollment_public(enrollment))
