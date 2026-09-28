"""工程基线：建立 Alembic 版本锚点。

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-28

SPEC-000 不创建业务表——DBD 中的表由各模块的迁移追加（SPEC-000 第 3 节）。
本版本的作用是建立迁移链起点与 alembic_version 记录，使后续模块有可依赖的
down_revision，同时让 upgrade/downgrade 在本阶段就可被验收。
"""

from __future__ import annotations

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """本阶段无表变更；后续模块在此之上追加版本。"""


def downgrade() -> None:
    """与 upgrade 对称：本阶段无表需要回退。"""
