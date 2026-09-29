"""SPEC-013 实验尝试表：experiment_attempts。

Revision ID: 0007_spec013
Revises: 0006_spec009
Create Date: 2026-09-29

字段与约束见 DBD 第 6 节。要点：
- 尝试记录只追加、不修改，因此没有 updated_at/version（DBD 第 1 节）。
- UNIQUE(student_id, request_key) 保证同一学生的同一次提交重试只落一行；
  同 key 不同内容由服务层判为 409。
- experiment_snapshot_json 固定提交时的实验口径（模型、配置、输入序列、版本），
  实验事后被编辑或撤回都不改变历史判分（ADR-005）。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_spec013"
down_revision = "0006_spec009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiment_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column(
            "experiment_id",
            sa.Integer(),
            sa.ForeignKey("experiments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "experiment_snapshot_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("predictions_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("expected_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("passed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("first_error_index", sa.Integer(), nullable=True),
        sa.Column("request_key", sa.Text(), nullable=False),
        sa.CheckConstraint("passed IN (0,1)", name="ck_experiment_attempts_passed"),
        sa.CheckConstraint(
            "first_error_index IS NULL OR first_error_index >= 0",
            name="ck_experiment_attempts_first_error",
        ),
        sa.UniqueConstraint(
            "student_id", "request_key", name="uq_experiment_attempts_student_key"
        ),
    )
    op.create_index(
        "ix_experiment_attempts_experiment_student",
        "experiment_attempts",
        ["experiment_id", "student_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_experiment_attempts_experiment_student", table_name="experiment_attempts")
    op.drop_table("experiment_attempts")
