"""SPEC-017 识别任务表：recognition_tasks。

Revision ID: 0011_spec017
Revises: 0010_spec004
Create Date: 2026-10-02

字段与索引见 DBD 第 7 节：图片按 ADR-008 以随机 storage_key 保存，
任务不可变，因此没有 version/updated_at；失败任务不保留有效 result。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_spec017"
down_revision = "0010_spec004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recognition_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "class_id",
            sa.Integer(),
            sa.ForeignKey("classes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=True),
        sa.Column("mime", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_json", sa.Text(), nullable=True),
        sa.CheckConstraint("kind IN ('state_table')", name="ck_recognition_tasks_kind"),
        sa.CheckConstraint("status IN ('done','failed')", name="ck_recognition_tasks_status"),
    )
    op.create_index(
        "ix_recognition_tasks_owner_created",
        "recognition_tasks",
        ["owner_id", "created_at"],
    )
    op.create_index(
        "ix_recognition_tasks_class_created",
        "recognition_tasks",
        ["class_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_recognition_tasks_class_created", table_name="recognition_tasks")
    op.drop_index("ix_recognition_tasks_owner_created", table_name="recognition_tasks")
    op.drop_table("recognition_tasks")
