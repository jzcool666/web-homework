"""SPEC-008 备课与预习表：lesson_plans、lesson_plan_items、preview_assignments。

Revision ID: 0008_spec008
Revises: 0007_spec013
Create Date: 2026-09-29

字段与约束见 DBD 第 3 节。要点：
- lesson_plan_items 用四个可空外键表达 PlanItem 的 target_type/target_id，
  并由 CHECK 保证每条恰好一个目标；UNIQUE(plan_id, sort_order) 保证条目顺序唯一。
- preview_assignments.snapshot_json 保存发布时冻结的备课条目与内容摘要，
  之后编辑原计划不改写已发布的预习。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_spec008"
down_revision = "0007_spec013"
branch_labels = None
depends_on = None

EXACTLY_ONE_TARGET = (
    "(CASE WHEN knowledge_id IS NULL THEN 0 ELSE 1 END"
    " + CASE WHEN resource_version_id IS NULL THEN 0 ELSE 1 END"
    " + CASE WHEN question_id IS NULL THEN 0 ELSE 1 END"
    " + CASE WHEN experiment_id IS NULL THEN 0 ELSE 1 END) = 1"
)


def upgrade() -> None:
    op.create_table(
        "lesson_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("planned_at", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.create_index("ix_lesson_plans_owner", "lesson_plans", ["owner_id"])

    op.create_table(
        "lesson_plan_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("lesson_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "knowledge_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "resource_version_id",
            sa.Integer(),
            sa.ForeignKey("resource_versions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "experiment_id",
            sa.Integer(),
            sa.ForeignKey("experiments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint(EXACTLY_ONE_TARGET, name="ck_lesson_plan_items_one_target"),
        sa.CheckConstraint("sort_order >= 1", name="ck_lesson_plan_items_order"),
        sa.UniqueConstraint("plan_id", "sort_order", name="uq_lesson_plan_items_order"),
    )

    op.create_table(
        "preview_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("lesson_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "class_id",
            sa.Integer(),
            sa.ForeignKey("classes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("due_at", sa.Text(), nullable=True),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_preview_assignments_class_created", "preview_assignments", ["class_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_preview_assignments_class_created", table_name="preview_assignments")
    op.drop_table("preview_assignments")
    op.drop_table("lesson_plan_items")
    op.drop_index("ix_lesson_plans_owner", table_name="lesson_plans")
    op.drop_table("lesson_plans")
