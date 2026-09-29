"""SPEC-002 数据模型：attendance_tasks、attendance_records、leave_requests。

字段、可空性、唯一键与索引以 DBD 第 4 节为准；表由迁移 0003 创建，
不在启动时建表。公开字段映射见本文件末尾，code_hash 永不进入响应。
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import now_utc

RECORD_PENDING = "pending"
RECORD_PRESENT = "present"
RECORD_LATE = "late"
RECORD_LEAVE = "leave"
RECORD_ABSENT = "absent"
RECORD_STATUSES = (RECORD_PENDING, RECORD_PRESENT, RECORD_LATE, RECORD_LEAVE, RECORD_ABSENT)
# 已发生签到的状态：不能被结算或请假审批覆盖
SIGNED_STATUSES = (RECORD_PRESENT, RECORD_LATE)

LEAVE_PENDING = "pending"
LEAVE_APPROVED = "approved"
LEAVE_REJECTED = "rejected"
LEAVE_STATUSES = (LEAVE_PENDING, LEAVE_APPROVED, LEAVE_REJECTED)


class AttendanceTask(Base):
    __tablename__ = "attendance_tasks"
    __table_args__ = (
        CheckConstraint(
            "opens_at <= late_at AND late_at < closes_at", name="ck_attendance_tasks_window"
        ),
        Index("ix_attendance_tasks_class_opens", "class_id", "opens_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    opens_at: Mapped[str] = mapped_column(Text, nullable=False)
    late_at: Mapped[str] = mapped_column(Text, nullable=False)
    closes_at: Mapped[str] = mapped_column(Text, nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    settled_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class AttendanceRecord(Base):
    """每任务每学生一行；发布时按有效名单生成 pending，签到只更新这一行。"""

    __tablename__ = "attendance_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','present','late','leave','absent')",
            name="ck_attendance_records_status",
        ),
        UniqueConstraint("task_id", "student_id", name="uq_attendance_records_task_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    signed_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected')", name="ck_leave_requests_status"
        ),
        UniqueConstraint("task_id", "student_id", name="uq_leave_requests_task_student"),
        Index("ix_leave_requests_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---- 公开字段映射（APIC 第 2、4 节字段模型）----
#
# student_display_name / student_no 是本模块的只读联表字段：教师查看签到名单和
# 请假申请时必须能认出学生，而 GET /users 仅管理员可用，教师无法据此解析学号。
# 该字段为增量读取模型，不改变表结构，登记见 CHG-RB.md。

def attendance_task_public(task: AttendanceTask) -> dict:
    """不含 code_hash；明文 code 只在创建与重置响应中由接口直接附加。"""
    return {
        "id": task.id,
        "class_id": task.class_id,
        "title": task.title,
        "opens_at": task.opens_at,
        "late_at": task.late_at,
        "closes_at": task.closes_at,
        "settled_at": task.settled_at,
        "version": task.version,
    }


def attendance_record_public(record: AttendanceRecord, student=None) -> dict:
    return {
        "id": record.id,
        "task_id": record.task_id,
        "student_id": record.student_id,
        "student_display_name": student.display_name if student else None,
        "student_no": student.student_no if student else None,
        "status": record.status,
        "signed_at": record.signed_at,
    }


def leave_request_public(leave: LeaveRequest, student=None) -> dict:
    return {
        "id": leave.id,
        "task_id": leave.task_id,
        "student_id": leave.student_id,
        "student_display_name": student.display_name if student else None,
        "student_no": student.student_no if student else None,
        "reason": leave.reason,
        "status": leave.status,
        "review_note": leave.review_note,
        "reviewed_at": leave.reviewed_at,
        "version": leave.version,
    }
