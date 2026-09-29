"""SPEC-001 数据模型：users、sessions、classes、enrollments。

字段、可空性、唯一键与索引以 DBD 第 1、2 节为准；表由迁移 0002 创建，
不在启动时建表。这里同时提供「模型 → 接口响应」的公开字段映射，
保证 password_hash、token_hash 等内部字段永不进入响应。
"""

from __future__ import annotations

from datetime import datetime, timezone

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

ROLES = ("student", "teacher", "admin")
ROLE_STUDENT = "student"
ROLE_TEACHER = "teacher"
ROLE_ADMIN = "admin"


def now_utc() -> str:
    """RFC3339 UTC 秒级，带 Z，与 APIC 时间格式一致。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('student','teacher','admin')", name="ck_users_role"),
        CheckConstraint("role <> 'student' OR student_no IS NOT NULL", name="ck_users_student_no"),
        CheckConstraint("active IN (0,1)", name="ck_users_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    login_name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    student_no: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class AuthSession(Base):
    """登录/匿名会话。表名 sessions；类名避开 sqlalchemy.orm.Session。"""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_expires_at", "expires_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)


class SchoolClass(Base):
    __tablename__ = "classes"
    __table_args__ = (
        CheckConstraint("active IN (0,1)", name="ck_classes_active"),
        Index("ix_classes_teacher_active", "teacher_id", "active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    active: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class Enrollment(Base):
    """关联表：无独立 id/version（DBD 第 1 节）。"""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_enrollments_class_student"),
        # 学生最多一个有效班级（部分唯一索引）
        Index(
            "uq_enrollments_active_student",
            "student_id",
            unique=True,
            sqlite_where=text("active = 1"),
        ),
        CheckConstraint("active IN (0,1)", name="ck_enrollments_active"),
    )

    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), primary_key=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    active: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    joined_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    left_at: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---- 公开字段映射（APIC 第 2 节字段模型）----

def user_public(user: User) -> dict:
    return {
        "id": user.id,
        "login_name": user.login_name,
        "student_no": user.student_no,
        "display_name": user.display_name,
        "role": user.role,
        "active": bool(user.active),
        "version": user.version,
    }


def class_public(school_class: SchoolClass) -> dict:
    return {
        "id": school_class.id,
        "name": school_class.name,
        "teacher_id": school_class.teacher_id,
        "active": bool(school_class.active),
        "version": school_class.version,
    }


def enrollment_public(enrollment: Enrollment) -> dict:
    return {
        "class_id": enrollment.class_id,
        "student_id": enrollment.student_id,
        "active": bool(enrollment.active),
        "joined_at": enrollment.joined_at,
        "left_at": enrollment.left_at,
    }
