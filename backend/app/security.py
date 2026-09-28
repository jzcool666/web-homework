"""口令与会话令牌的散列工具（DBD 第 1 节：不保存明文）。

口令用 Werkzeug 的安全散列（默认 scrypt），会话标识与 CSRF 令牌用
SHA-256 摘要入库存档；数据库中任何一行都不包含可直接使用的明文凭据。
"""

from __future__ import annotations

import hashlib
import secrets

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def new_token() -> str:
    """会话 Cookie 值与 CSRF 令牌都用不可预测的随机串。"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
