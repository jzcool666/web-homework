"""数据库引擎、会话与 SQLite 连接级设置。

SQLite 的外键与锁等待是**每连接**生效的，因此在这里挂 connect 事件，
而不是在启动时执行一次 PRAGMA。迁移（Alembic）与应用共用同一个建引擎函数，
保证两条路径拿到的连接设置一致。
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# DBD「公共约定」要求：外键开启、busy_timeout 5 秒
SQLITE_PRAGMAS = (
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
)

# 供健康检查使用的轻量查询，不依赖任何业务表
HEALTHCHECK_SQL = text("SELECT 1")


class Base(DeclarativeBase):
    """所有模型声明的基类。

    本 Spec 不创建业务表；各模块用自己的迁移追加，见 SPEC-000 第 3 节。
    """


def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        for statement in SQLITE_PRAGMAS:
            cursor.execute(statement)
    finally:
        cursor.close()


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    """按 URL 建引擎；SQLite 连接建立时立即设置外键与 busy_timeout。"""
    engine = create_engine(database_url, echo=echo, future=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _apply_sqlite_pragmas)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]):
    """提交/回滚成对出现的会话上下文，供后续模块复用。"""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def read_sqlite_setting(engine: Engine, pragma: str) -> object:
    """读取 SQLite 连接级设置，用于验收证据（例如 foreign_keys、busy_timeout）。

    这里重新开一条连接，读到的是 connect 事件之后的真实值。
    """
    if engine.dialect.name != "sqlite":
        raise ValueError("read_sqlite_setting 只适用于 SQLite")
    with engine.connect() as connection:
        return connection.exec_driver_sql(f"PRAGMA {pragma}").scalar()
