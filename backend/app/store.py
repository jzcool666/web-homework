"""请求级数据库会话。

每个请求/应用上下文复用一个 Session，请求结束时关闭；不引入全局长事务。
"""

from __future__ import annotations

from flask import current_app, g
from sqlalchemy.orm import Session


def db_session() -> Session:
    if "db_session" not in g:
        g.db_session = current_app.extensions["db_session"]()
    return g.db_session


def close_db_session(_exc: BaseException | None = None) -> None:
    session: Session | None = g.pop("db_session", None)
    if session is not None:
        session.close()
