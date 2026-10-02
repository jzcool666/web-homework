"""SPEC-007 问答语料表：qa_entries。

Revision ID: 0009_spec007
Revises: 0008_spec008
Create Date: 2026-10-02

字段与约束见 DBD 第 7 节。要点：
- 每条问答挂在一个知识点上（knowledge_id 非空），检索命中按知识点归并；
- 可编辑实体，因此带 updated_at 与 version；version 递增同时驱动语料指纹变化，
  使下一次查询重建索引（SPEC-007 第 3、4 节）；
- 没有物理删除接口：停用用 published=0，与 DBD 第 1 节「软停用代替删除」一致。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_spec007"
down_revision = "0008_spec008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qa_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "knowledge_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("question", sa.String(200), nullable=False),
        sa.Column("answer_md", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("published", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint("published IN (0,1)", name="ck_qa_entries_published"),
    )


def downgrade() -> None:
    op.drop_table("qa_entries")
