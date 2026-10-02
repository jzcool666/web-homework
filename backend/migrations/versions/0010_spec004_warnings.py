"""SPEC-004 学习预警表：warning_snapshots。

Revision ID: 0010_spec004
Revises: 0009_spec007
Create Date: 2026-10-02

字段与索引见 DBD 第 7 节。一次生成写入一个批次，批次号存 evidence_json，
列表只读取最近同窗口的完整批次。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_spec004"
down_revision = "0009_spec007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warning_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column(
            "class_id",
            sa.Integer(),
            sa.ForeignKey("classes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("window_start", sa.Text(), nullable=False),
        sa.Column("window_end", sa.Text(), nullable=False),
        sa.Column("algorithm_version", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("cluster_label", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "level IN ('insufficient','low','medium','high')",
            name="ck_warning_snapshots_level",
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_warning_snapshots_score",
        ),
        sa.CheckConstraint(
            "cluster_label IS NULL OR cluster_label IN (0,1,2)",
            name="ck_warning_snapshots_cluster",
        ),
    )
    op.create_index(
        "ix_warning_snapshots_class_generated",
        "warning_snapshots",
        ["class_id", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_warning_snapshots_class_generated", table_name="warning_snapshots")
    op.drop_table("warning_snapshots")
