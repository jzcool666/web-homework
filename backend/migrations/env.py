"""Alembic 运行环境。

迁移连接复用 app.db.create_db_engine，因此迁移过程中的连接同样带
`PRAGMA foreign_keys=ON` 与 `PRAGMA busy_timeout=5000`（SPEC-000 第 4 节第 4 条）。
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

# 让 migrations/ 之外的本目录可导入 app 包
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import Base, create_db_engine  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 各模块把模型挂到 Base 之后，autogenerate 才能看到它们
target_metadata = Base.metadata


def get_url() -> str:
    """优先取运行期注入的 URL，其次取环境变量。"""
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("未提供数据库 URL：请通过 `flask db` 命令或 DATABASE_URL 指定")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_db_engine(get_url())
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite 的 ALTER 能力有限，批次模式让后续模块的迁移可用
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
