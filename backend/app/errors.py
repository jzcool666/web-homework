"""APIC 第 1 节的统一响应封装与错误处理。

成功响应：{"data": ..., "meta": {"server_time": ...}}
错误响应：{"error": {"code", "message", "details"}, "meta": {"server_time": ...}}

details 只放字段级或结构化约束信息，不放堆栈、SQL、口令或正确答案。
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

# APIC 第 1 节错误码表
ERROR_STATUS = {
    "INVALID_REQUEST": 400,
    "UNAUTHENTICATED": 401,
    "INVALID_CREDENTIALS": 401,
    "FORBIDDEN": 403,
    "CSRF_FAILED": 403,
    "NOT_FOUND": 404,
    "VERSION_CONFLICT": 409,
    "STATE_CONFLICT": 409,
    "DUPLICATE": 409,
    "DEADLINE_PASSED": 409,
    "FILE_TOO_LARGE": 413,
    "FILE_TYPE_UNSUPPORTED": 415,
    "VALIDATION_ERROR": 422,
    "INFEASIBLE_PAPER": 422,
    "RATE_LIMITED": 429,
    "DB_BUSY": 503,
    "SOLVER_TIMEOUT": 503,
    # SPEC-017：识别处理超过配置限时；不保留任务，可重试
    "RECOGNITION_TIMEOUT": 503,
    # SPEC-007：课程检索语料索引重建失败，保留旧索引并让请求显式失败
    "INDEX_UNAVAILABLE": 503,
}


def server_time() -> str:
    """RFC3339 UTC，秒级，带 Z。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def meta(**extra) -> dict:
    payload = {"server_time": server_time()}
    payload.update(extra)
    return payload


def success(data, status: int = 200, **meta_extra):
    return jsonify({"data": data, "meta": meta(**meta_extra)}), status


class ApiError(Exception):
    """业务错误；由 errorhandler 渲染成 APIC 错误封装。"""

    def __init__(
        self,
        code: str,
        message: str,
        details=None,
        status: int | None = None,
        headers: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.status = status or ERROR_STATUS.get(code, 400)
        # 例如 429 的 Retry-After（APIC 第 1 节）
        self.headers = headers or {}


def error_payload(code: str, message: str, details=None) -> dict:
    return {
        "error": {"code": code, "message": message, "details": details},
        "meta": meta(),
    }


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        response = jsonify(error_payload(exc.code, exc.message, exc.details))
        response.status_code = exc.status
        for name, value in exc.headers.items():
            response.headers[name] = value
        return response

    @app.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException):
        code = {
            400: "INVALID_REQUEST",
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "INVALID_REQUEST",
            413: "FILE_TOO_LARGE",
            415: "FILE_TYPE_UNSUPPORTED",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
            503: "DB_BUSY",
        }.get(exc.code or 500, "INVALID_REQUEST")
        return jsonify(error_payload(code, exc.description or exc.name)), exc.code or 500

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):  # pragma: no cover - 兜底路径
        app.logger.exception("未处理异常: %s", type(exc).__name__)
        return jsonify(error_payload("INVALID_REQUEST", "服务器内部错误，请稍后重试")), 500
