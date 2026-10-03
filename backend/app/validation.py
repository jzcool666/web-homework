"""请求载荷校验：拒绝未知字段，字段级错误统一为 422 VALIDATION_ERROR。"""

from __future__ import annotations

import re
from typing import Iterable, Mapping

from flask import request

from .errors import ApiError

LOGIN_NAME_RE = re.compile(r"^[A-Za-z0-9_]{4,32}$")
STUDENT_NO_RE = re.compile(r"^\d{6,20}$")

LOGIN_NAME_RULE = "4—32 位字母、数字或下划线"
STUDENT_NO_RULE = "6—20 位数字"
PASSWORD_RULE = "10—128 个字符"
DISPLAY_NAME_RULE = "1—50 个字符"


def _fail(fields: Mapping[str, str]):
    raise ApiError("VALIDATION_ERROR", "请求字段不合法", {"fields": dict(fields)})


def json_object(allowed: Iterable[str]) -> dict:
    """读取 JSON 对象并拒绝未声明的业务字段（APIC 第 1 节）。"""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError("INVALID_REQUEST", "请求体必须是 JSON 对象")
    allowed_set = set(allowed)
    unknown = sorted(set(body) - allowed_set)
    if unknown:
        raise ApiError(
            "VALIDATION_ERROR",
            "请求包含未支持的字段",
            {"unknown_fields": unknown},
        )
    return body


def text_field(body: dict, name: str, *, rule: str, min_len: int, max_len: int) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not (min_len <= len(value) <= max_len):
        _fail({name: rule})
    return value


def login_name(body: dict, name: str = "login_name") -> str:
    value = body.get(name)
    if not isinstance(value, str) or not LOGIN_NAME_RE.match(value):
        _fail({name: LOGIN_NAME_RULE})
    return value


def student_no(body: dict, name: str = "student_no") -> str:
    value = body.get(name)
    if not isinstance(value, str) or not STUDENT_NO_RE.match(value):
        _fail({name: STUDENT_NO_RULE})
    return value


def display_name(body: dict, name: str = "display_name") -> str:
    value = body.get(name)
    if not isinstance(value, str):
        _fail({name: DISPLAY_NAME_RULE})
    value = value.strip()
    if not (1 <= len(value) <= 50):
        _fail({name: DISPLAY_NAME_RULE})
    return value


def password(body: dict, name: str = "password") -> str:
    value = body.get(name)
    if not isinstance(value, str) or not (10 <= len(value) <= 128):
        _fail({name: PASSWORD_RULE})
    return value


def pagination() -> tuple[int, int]:
    """page/page_size；非法值 400 INVALID_REQUEST（APIC 第 1 节）。"""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except (TypeError, ValueError):
        raise ApiError("INVALID_REQUEST", "分页参数必须是整数")
    if page < 1 or not (1 <= page_size <= 100):
        raise ApiError("INVALID_REQUEST", "page 必须≥1，page_size 必须在 1—100 之间")
    return page, page_size
