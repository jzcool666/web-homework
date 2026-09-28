"""E000 GET /api/v1/health。

公开接口：不校验登录，也不回显环境变量、文件路径或凭据。
数据库不可用时返回 503 的 APIC 错误封装，并给出可读原因。
"""

from __future__ import annotations

import re

from flask import Blueprint, current_app, jsonify

from .db import HEALTHCHECK_SQL
from .errors import ApiError, meta

bp = Blueprint("health", __name__)

# 绝对路径（Windows 盘符、UNC 或 POSIX）一律替换掉，避免通过健康接口泄露路径
_ABS_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\)[^\s\"']*|/(?:[^\s\"']*/)+[^\s\"']*")


def _safe_reason(exc: Exception) -> str:
    """把驱动异常压成一句可读且不含路径的原因。"""
    text = str(exc).splitlines()[0].strip() if str(exc).strip() else ""
    text = _ABS_PATH.sub("<path>", text)
    text = " ".join(text.split())
    if len(text) > 200:
        text = text[:197] + "..."
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


@bp.get("/health")
def health():
    engine = current_app.extensions["db_engine"]
    try:
        with engine.connect() as connection:
            connection.execute(HEALTHCHECK_SQL)
    except Exception as exc:  # 驱动异常种类较多，这里统一转成 503
        current_app.logger.warning("健康检查数据库不可用: %s", type(exc).__name__)
        raise ApiError(
            "DB_BUSY",
            "数据库不可用，服务暂时无法响应",
            details={"reason": _safe_reason(exc)},
            status=503,
        ) from exc
    return jsonify({"data": {"status": "ok", "version": current_app.config["APP_VERSION"]}, "meta": meta()})
