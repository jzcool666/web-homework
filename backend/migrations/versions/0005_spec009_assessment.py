"""SPEC-009 题库与测评表。

Revision ID: 0005_spec009
Revises: 0004_spec002
Create Date: 2026-09-29

字段与约束见 DBD 第 5 节。要点：
- questions 的选项与答案是 JSON TEXT，结构由服务层校验（选项 key 唯一、
  单选一个答案、多选≥2、判断 true/false），表只约束题型与难度的取值域。
- assessment_items.snapshot_json 保存发布时的完整题目版本与答案，判分只读快照，
  不回写题目表的后续修改。
- submissions 以 UNIQUE(assessment_id, student_id) 保证同测评同学生只有一份提交，
  并发开始不需要额外锁。
- assessment_roster 与 submission_answers 是关联表，用复合主键，不带 id/created_at。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_spec009"
down_revision = "0004_spec002"
branch_labels = None
depends_on = None

QUESTION_TYPES = "('single','multiple','boolean')"
ASSESSMENT_KINDS = "('practice','quiz','homework','exam')"
ASSESSMENT_STATES = "('draft','published','closed')"
SUBMISSION_STATUSES = "('draft','submitted')"
SUBMIT_REASONS = "('manual','timeout')"
ORIGINS = "('manual','generated')"


def upgrade() -> None:
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("stem_md", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("answer_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("explanation_md", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("published", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint(f"type IN {QUESTION_TYPES}", name="ck_questions_type"),
        sa.CheckConstraint("difficulty IN (1,2,3)", name="ck_questions_difficulty"),
        sa.CheckConstraint("published IN (0,1)", name="ck_questions_published"),
    )

    op.create_table(
        "question_knowledge",
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "knowledge_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "class_id",
            sa.Integer(),
            sa.ForeignKey("classes.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("starts_at", sa.Text(), nullable=True),
        sa.Column("ends_at", sa.Text(), nullable=True),
        sa.Column("feedback_released", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("origin", sa.String(16), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("generation_json", sa.Text(), nullable=True),
        sa.CheckConstraint(f"kind IN {ASSESSMENT_KINDS}", name="ck_assessments_kind"),
        sa.CheckConstraint(f"state IN {ASSESSMENT_STATES}", name="ck_assessments_state"),
        sa.CheckConstraint(f"origin IN {ORIGINS}", name="ck_assessments_origin"),
        sa.CheckConstraint("feedback_released IN (0,1)", name="ck_assessments_feedback"),
        sa.CheckConstraint("total_score >= 0", name="ck_assessments_total_score"),
    )
    op.create_index(
        "ix_assessments_class_state_ends", "assessments", ["class_id", "state", "ends_at"]
    )

    op.create_table(
        "assessment_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column(
            "assessment_id",
            sa.Integer(),
            sa.ForeignKey("assessments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.CheckConstraint("points BETWEEN 1 AND 100", name="ck_assessment_items_points"),
        sa.CheckConstraint("position >= 1", name="ck_assessment_items_position"),
        sa.UniqueConstraint("assessment_id", "position", name="uq_assessment_items_position"),
        sa.UniqueConstraint("assessment_id", "question_id", name="uq_assessment_items_question"),
    )

    op.create_table(
        "assessment_roster",
        sa.Column(
            "assessment_id",
            sa.Integer(),
            sa.ForeignKey("assessments.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "assessment_id",
            sa.Integer(),
            sa.ForeignKey("assessments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.Text(), nullable=True),
        sa.Column("submit_reason", sa.String(16), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("final_request_hash", sa.Text(), nullable=True),
        sa.CheckConstraint(f"status IN {SUBMISSION_STATUSES}", name="ck_submissions_status"),
        sa.CheckConstraint(
            f"submit_reason IS NULL OR submit_reason IN {SUBMIT_REASONS}",
            name="ck_submissions_reason",
        ),
        sa.CheckConstraint("score IS NULL OR score >= 0", name="ck_submissions_score"),
        sa.UniqueConstraint("assessment_id", "student_id", name="uq_submissions_assessment_student"),
    )
    op.create_index("ix_submissions_student_submitted", "submissions", ["student_id", "submitted_at"])

    op.create_table(
        "submission_answers",
        sa.Column(
            "submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("assessment_items.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("selected_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("correct", sa.Integer(), nullable=True),
        sa.Column("awarded_points", sa.Integer(), nullable=True),
        sa.CheckConstraint("correct IS NULL OR correct IN (0,1)", name="ck_submission_answers_correct"),
    )


def downgrade() -> None:
    op.drop_table("submission_answers")
    op.drop_index("ix_submissions_student_submitted", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("assessment_roster")
    op.drop_table("assessment_items")
    op.drop_index("ix_assessments_class_state_ends", table_name="assessments")
    op.drop_table("assessments")
    op.drop_table("question_knowledge")
    op.drop_table("questions")
