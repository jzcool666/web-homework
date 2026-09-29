"""会话、CSRF 与角色权限（SPEC-001 第 4 节、ADR-004）。

- Cookie 只承载随机会话标识；数据库存 SHA-256 摘要。
- 匿名 CSRF 会话 30 分钟，登录会话绝对 8 小时，登录时轮换标识与 CSRF。
- 所有写方法（POST/PUT/PATCH/DELETE）必须携带 X-CSRF-Token。
- 角色与 active 每次请求重新读取，不信任客户端。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import current_app, g, jsonify, request
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from .errors import ApiError, meta
from .models import AuthSession, User, now_utc
from .security import hash_token
from .store import db_session

SESSION_COOKIE = "sid"
CSRF_HEADER = "X-CSRF-Token"
CSRF_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

ANON_TTL = timedelta(minutes=30)
LOGIN_TTL = timedelta(hours=8)

LOGIN_FAIL_LIMIT = 10
LOGIN_FAIL_WINDOW = timedelta(minutes=15)

_login_failures: dict[str, list[datetime]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rfc(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def expiry_for(ttl: timedelta) -> str:
    """当前时间 + ttl 的 RFC3339 时间戳，用于会话绝对有效期。"""
    return _rfc(_now() + ttl)


def set_session_cookie(response, token: str, ttl: timedelta):
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        samesite="Lax",
        secure=bool(current_app.config.get("COOKIE_SECURE")),
        path="/",
    )
    return response


def clear_session_cookie(response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


def success_with_cookie(data, token: str, ttl: timedelta, status: int = 200):
    response = jsonify({"data": data, "meta": meta()})
    response.status_code = status
    return set_session_cookie(response, token, ttl)


def load_session() -> tuple[AuthSession | None, User | None]:
    """返回当前会话行与用户。失效会话（过期/停用/已删除用户）视为未登录。"""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None, None
    session = db_session()
    row = session.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if row is None:
        return None, None
    if _parse(row.expires_at) <= _now():
        session.delete(row)
        session.commit()
        return None, None
    user = None
    if row.user_id is not None:
        user = session.get(User, row.user_id)
        if user is None or not user.active:
            # 账号被删除或停用：旧会话立即失效
            return None, None
    return row, user


def require_csrf() -> None:
    row: AuthSession | None = getattr(g, "auth_session", None)
    token = request.headers.get(CSRF_HEADER, "")
    if row is None or not token or row.csrf_hash != hash_token(token):
        raise ApiError("CSRF_FAILED", "CSRF 校验失败，请刷新页面后重试")


def current_user() -> User | None:
    return getattr(g, "current_user", None)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            raise ApiError("UNAUTHENTICATED", "请先登录")
        return view(*args, **kwargs)

    return wrapper


def roles_required(*roles: str):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                raise ApiError("UNAUTHENTICATED", "请先登录")
            if user.role not in roles:
                raise ApiError("FORBIDDEN", "当前角色无权执行该操作")
            return view(*args, **kwargs)

        return wrapper

    return decorator


def invalidate_user_sessions(user_id: int) -> None:
    """角色变更、停用、改密码时撤销该用户的全部登录会话。"""
    session = db_session()
    session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


# ---- 登录失败限流（进程内，单实例）----

def login_rate_key(login_name: str) -> str:
    return f"{login_name.strip().lower()}|{request.remote_addr or '-'}"


def check_login_rate(key: str) -> None:
    now = _now()
    stamps = [t for t in _login_failures.get(key, []) if now - t < LOGIN_FAIL_WINDOW]
    _login_failures[key] = stamps
    if len(stamps) >= LOGIN_FAIL_LIMIT:
        retry_after = int((LOGIN_FAIL_WINDOW - (now - min(stamps))).total_seconds()) + 1
        raise ApiError(
            "RATE_LIMITED",
            "登录失败次数过多，请稍后再试",
            details={"retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


def record_login_failure(key: str) -> None:
    _login_failures.setdefault(key, []).append(_now())


def clear_login_failures(key: str) -> None:
    _login_failures.pop(key, None)


def register_session_hooks(app) -> None:
    # 健康检查自行判定数据库可用性，不能被会话读取抢先拦成 503
    skip_endpoints = {"health.health"}

    @app.before_request
    def _load_and_guard():
        if request.endpoint in skip_endpoints:
            g.auth_session, g.current_user = None, None
            return
        try:
            g.auth_session, g.current_user = load_session()
        except SQLAlchemyError as exc:
            app.logger.warning("读取会话失败: %s", type(exc).__name__)
            raise ApiError("DB_BUSY", "数据库暂时不可用，请稍后重试") from exc
        if request.method not in CSRF_SAFE_METHODS:
            require_csrf()
