"""SPEC-001 业务表：users、sessions、classes、enrollments。

Revision ID: 0002_spec001
Revises: 0001_baseline
Create Date: 2026-09-28

字段与约束见 DBD 第 1、2 节。关联表 enrollments 无独立 id/version；
学生「最多一个有效班级」由部分唯一索引 uq_enrollments_active_student 保证。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_spec001"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("login_name", sa.String(32), nullable=False),
        sa.Column("student_no", sa.String(20), nullable=True),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("role IN ('student','teacher','admin')", name="ck_users_role"),
        sa.CheckConstraint("active IN (0,1)", name="ck_users_active"),
        sa.UniqueConstraint("login_name", name="uq_users_login_name"),
        sa.UniqueConstraint("student_no", name="uq_users_student_no"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column(
            "teacher_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("active", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("active IN (0,1)", name="ck_classes_active"),
    )
    op.create_index("ix_classes_teacher_active", "classes", ["teacher_id", "active"])

    op.create_table(
        "enrollments",
        sa.Column(
            "class_id",
            sa.Integer(),
            sa.ForeignKey("classes.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("active", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("joined_at", sa.Text(), nullable=False),
        sa.Column("left_at", sa.Text(), nullable=True),
        sa.CheckConstraint("active IN (0,1)", name="ck_enrollments_active"),
        sa.UniqueConstraint("class_id", "student_id", name="uq_enrollments_class_student"),
    )
    # 学生最多一个有效班级：部分唯一索引
    op.create_index(
        "uq_enrollments_active_student",
        "enrollments",
        ["student_id"],
        unique=True,
        sqlite_where=sa.text("active = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_enrollments_active_student", table_name="enrollments")
    op.drop_table("enrollments")
    op.drop_index("ix_classes_teacher_active", table_name="classes")
    op.drop_table("classes")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
