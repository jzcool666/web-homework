"""E001—E005：注册、登录、退出与个人资料（SPEC-001）。"""

from __future__ import annotations

from flask import Blueprint, g, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .auth import (
    ANON_TTL,
    LOGIN_TTL,
    check_login_rate,
    clear_login_failures,
    clear_session_cookie,
    current_user,
    expiry_for,
    invalidate_user_sessions,
    login_rate_key,
    login_required,
    record_login_failure,
    success_with_cookie,
)
from .errors import ApiError, meta, success
from .models import AuthSession, User, now_utc, user_public
from .security import hash_password, hash_token, new_token, verify_password
from .store import db_session
from .validation import display_name, json_object, login_name, password, student_no

bp = Blueprint("auth", __name__)


@bp.get("/auth/csrf")
def issue_csrf():
    """初次创建短时匿名会话；已有会话则轮换其 CSRF 令牌，不改变登录状态。"""
    session = db_session()
    token = new_token()
    row: AuthSession | None = g.auth_session
    if row is not None:
        row.csrf_hash = hash_token(token)
        row.last_seen_at = now_utc()
        session.commit()
        return success({"csrf_token": token})

    sid = new_token()
    session.add(
        AuthSession(
            token_hash=hash_token(sid),
            user_id=None,
            csrf_hash=hash_token(token),
            expires_at=expiry_for(ANON_TTL),
            last_seen_at=now_utc(),
        )
    )
    session.commit()
    return success_with_cookie({"csrf_token": token}, sid, ANON_TTL)


@bp.post("/auth/register")
def register():
    """公开注册只允许学生；携带 role/active 等未知字段一律拒绝。"""
    body = json_object(["login_name", "student_no", "display_name", "password"])
    data = {
        "login_name": login_name(body),
        "student_no": student_no(body),
        "display_name": display_name(body),
        "password": password(body),
    }

    session = db_session()
    if session.scalar(select(User.id).where(User.login_name == data["login_name"])):
        raise ApiError("DUPLICATE", "登录名已被占用", {"fields": {"login_name": "已存在"}})
    if session.scalar(select(User.id).where(User.student_no == data["student_no"])):
        raise ApiError("DUPLICATE", "学号已被占用", {"fields": {"student_no": "已存在"}})

    user = User(
        login_name=data["login_name"],
        student_no=data["student_no"],
        display_name=data["display_name"],
        password_hash=hash_password(data["password"]),
        role="student",
        active=1,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiError("DUPLICATE", "登录名或学号已被占用")

    return success(user_public(user), 201)


@bp.post("/auth/login")
def login():
    body = json_object(["login_name", "password"])
    name = body.get("login_name")
    secret = body.get("password")
    if not isinstance(name, str) or not isinstance(secret, str):
        raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": {"login_name": "必填", "password": "必填"}})

    key = login_rate_key(name)
    check_login_rate(key)

    session = db_session()
    user = session.scalar(select(User).where(User.login_name == name))
    if user is None or not user.active or not verify_password(user.password_hash, secret):
        record_login_failure(key)
        raise ApiError("INVALID_CREDENTIALS", "登录名或密码不正确")

    clear_login_failures(key)

    # 轮换会话标识与 CSRF 令牌（ADR-004：登录成功轮换）
    sid = new_token()
    csrf = new_token()
    row: AuthSession | None = g.auth_session
    if row is None:
        row = AuthSession(
            token_hash=hash_token(sid),
            csrf_hash=hash_token(csrf),
            expires_at=expiry_for(LOGIN_TTL),
            last_seen_at=now_utc(),
        )
        session.add(row)
    else:
        row.token_hash = hash_token(sid)
        row.csrf_hash = hash_token(csrf)
        row.expires_at = expiry_for(LOGIN_TTL)
        row.last_seen_at = now_utc()
    row.user_id = user.id
    session.commit()

    return success_with_cookie(
        {"user": user_public(user), "csrf_token": csrf}, sid, LOGIN_TTL
    )


@bp.post("/auth/logout")
@login_required
def logout():
    session = db_session()
    row: AuthSession | None = g.auth_session
    if row is not None:
        session.delete(row)
        session.commit()
    response = jsonify({"data": {"logged_out": True}, "meta": meta()})
    return clear_session_cookie(response)


@bp.get("/me")
@login_required
def get_me():
    return success(user_public(current_user()))


@bp.patch("/me")
@login_required
def patch_me():
    body = json_object(["version", "display_name", "current_password", "new_password"])
    user = current_user()
    session = db_session()

    version = body.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ApiError("VALIDATION_ERROR", "version 必须是整数", {"fields": {"version": "必填"}})
    if version != user.version:
        raise ApiError(
            "VERSION_CONFLICT",
            "资料已被修改，请刷新后重试",
            {"expected_version": version, "current_version": user.version},
        )

    if "display_name" in body:
        user.display_name = display_name(body)

    if "new_password" in body:
        if "current_password" not in body:
            raise ApiError(
                "VALIDATION_ERROR",
                "修改密码需要提供当前密码",
                {"fields": {"current_password": "必填"}},
            )
        if not verify_password(user.password_hash, body.get("current_password") or ""):
            raise ApiError("INVALID_CREDENTIALS", "当前密码不正确")
        user.password_hash = hash_password(password(body, "new_password"))
        user.version += 1
        session.flush()
        # 改密码后作废全部会话，包括当前会话（SPEC-001 第 4 节第 1 条）
        invalidate_user_sessions(user.id)
        session.commit()
        response = jsonify({"data": user_public(user), "meta": meta()})
        return clear_session_cookie(response)

    if "display_name" not in body:
        raise ApiError("VALIDATION_ERROR", "没有可更新的字段")

    user.version += 1
    session.commit()
    return success(user_public(user))
