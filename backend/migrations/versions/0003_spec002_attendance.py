"""SPEC-002 考勤表：attendance_tasks、attendance_records、leave_requests。

Revision ID: 0003_spec002
Revises: 0002_spec001
Create Date: 2026-09-29

字段与约束见 DBD 第 4 节。要点：
- 时间统一为 UTC ISO 8601 TEXT，因此窗口约束用字符串比较即可（同格式同长度）。
- attendance_tasks.code_hash 只保存散列，明文只在创建/重置响应中出现一次。
- attendance_records 与 leave_requests 都以 UNIQUE(task_id, student_id) 保证
  「每任务每学生唯一」，并发签到不需要插入新行。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_spec002"
down_revision = "0002_spec001"
branch_labels = None
depends_on = None

RECORD_STATUSES = "('pending','present','late','leave','absent')"
LEAVE_STATUSES = "('pending','approved','rejected')"


def upgrade() -> None:
    op.create_table(
        "attendance_tasks",
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
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("opens_at", sa.Text(), nullable=False),
        sa.Column("late_at", sa.Text(), nullable=False),
        sa.Column("closes_at", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("settled_at", sa.Text(), nullable=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "opens_at <= late_at AND late_at < closes_at", name="ck_attendance_tasks_window"
        ),
    )
    op.create_index(
        "ix_attendance_tasks_class_opens", "attendance_tasks", ["class_id", "opens_at"]
    )

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("attendance_tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("signed_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"status IN {RECORD_STATUSES}", name="ck_attendance_records_status"
        ),
        sa.UniqueConstraint("task_id", "student_id", name="uq_attendance_records_task_student"),
    )

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("attendance_tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "reviewer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("review_note", sa.String(200), nullable=True),
        sa.Column("reviewed_at", sa.Text(), nullable=True),
        sa.CheckConstraint(f"status IN {LEAVE_STATUSES}", name="ck_leave_requests_status"),
        sa.UniqueConstraint("task_id", "student_id", name="uq_leave_requests_task_student"),
    )
    op.create_index("ix_leave_requests_status", "leave_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_leave_requests_status", table_name="leave_requests")
    op.drop_table("leave_requests")
    op.drop_table("attendance_records")
    op.drop_index("ix_attendance_tasks_class_opens", table_name="attendance_tasks")
    op.drop_table("attendance_tasks")
