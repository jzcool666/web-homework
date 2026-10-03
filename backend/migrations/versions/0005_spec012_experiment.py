"""SPEC-012 实验与演示表：experiments、demo_sessions。

Revision ID: 0005_spec012
Revises: 0004_spec002
Create Date: 2026-09-29

字段与约束见 DBD 第 6 节。要点：
- experiments 只存配置与输入序列，不存期望输出；期望状态由 SPEC-013 用同一套
  仿真规则计算，避免两处定义漂移。
- demo_sessions 的 config_snapshot_json 在创建时固定实验配置，实验事后修改不
  影响进行中的演示；每班最多一个 active=1 由部分唯一索引保证。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_spec012"
down_revision = "0004_spec002"
branch_labels = None
depends_on = None

SIMULATOR_TYPES = "('d','jk','counter','shift')"


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column(
            "knowledge_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("simulator_type", sa.String(16), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("steps_md", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "input_sequence_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")
        ),
        sa.Column("published", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint(f"simulator_type IN {SIMULATOR_TYPES}", name="ck_experiments_type"),
        sa.CheckConstraint("published IN (0,1)", name="ck_experiments_published"),
    )

    op.create_table(
        "demo_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "class_id",
            sa.Integer(),
            sa.ForeignKey("classes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            sa.Integer(),
            sa.ForeignKey("experiments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("active", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "config_snapshot_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("state_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "event_log_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")
        ),
        sa.Column("reveal_next", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint("active IN (0,1)", name="ck_demo_sessions_active"),
        sa.CheckConstraint("reveal_next IN (0,1)", name="ck_demo_sessions_reveal"),
    )
    # 每班最多一个进行中的演示（DBD 第 6 节）
    op.create_index(
        "uq_demo_sessions_active_class",
        "demo_sessions",
        ["class_id"],
        unique=True,
        sqlite_where=sa.text("active = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_demo_sessions_active_class", table_name="demo_sessions")
    op.drop_table("demo_sessions")
    op.drop_table("experiments")
