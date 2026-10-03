"""SPEC-008 数据模型：备课单、备课条目与预习发布。

字段、可空性、唯一键与索引以 DBD 第 3 节为准；表由迁移 0008 创建，
不在启动时建表。公开字段映射见本文件末尾。

两条不变式：
- 备课条目用四个可空外键表达「恰好一个目标」，接口对外只暴露 target_type/target_id。
- preview_assignments.snapshot_json 是发布时冻结的快照，之后改原计划不改写它。
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

TARGET_KNOWLEDGE = "knowledge"
TARGET_RESOURCE_VERSION = "resource_version"
TARGET_QUESTION = "question"
TARGET_EXPERIMENT = "experiment"
TARGET_TYPES = (TARGET_KNOWLEDGE, TARGET_RESOURCE_VERSION, TARGET_QUESTION, TARGET_EXPERIMENT)

TITLE_MAX = 100
NOTES_MAX = 5000
MAX_ITEMS = 50
# 预习快照里知识点正文的摘要长度，避免把整篇正文复制进快照
EXCERPT_MAX = 200

TARGET_COLUMNS = {
    TARGET_KNOWLEDGE: "knowledge_id",
    TARGET_RESOURCE_VERSION: "resource_version_id",
    TARGET_QUESTION: "question_id",
    TARGET_EXPERIMENT: "experiment_id",
}

EXACTLY_ONE_TARGET = (
    "(CASE WHEN knowledge_id IS NULL THEN 0 ELSE 1 END"
    " + CASE WHEN resource_version_id IS NULL THEN 0 ELSE 1 END"
    " + CASE WHEN question_id IS NULL THEN 0 ELSE 1 END"
    " + CASE WHEN experiment_id IS NULL THEN 0 ELSE 1 END) = 1"
)


class LessonPlan(Base):
    __tablename__ = "lesson_plans"
    __table_args__ = (Index("ix_lesson_plans_owner", "owner_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    title: Mapped[str] = mapped_column(String(TITLE_MAX), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    planned_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class LessonPlanItem(Base):
    """一条备课条目恰好引用一个目标；排序在计划内唯一。"""

    __tablename__ = "lesson_plan_items"
    __table_args__ = (
        CheckConstraint(EXACTLY_ONE_TARGET, name="ck_lesson_plan_items_one_target"),
        CheckConstraint("sort_order >= 1", name="ck_lesson_plan_items_order"),
        UniqueConstraint("plan_id", "sort_order", name="uq_lesson_plan_items_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("lesson_plans.id", ondelete="RESTRICT"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    knowledge_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), nullable=True
    )
    resource_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("resource_versions.id", ondelete="RESTRICT"), nullable=True
    )
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), nullable=True
    )
    experiment_id: Mapped[int | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=True
    )

    @property
    def target_type(self) -> str:
        for target_type, column in TARGET_COLUMNS.items():
            if getattr(self, column) is not None:
                return target_type
        return TARGET_KNOWLEDGE

    @property
    def target_id(self) -> int | None:
        return getattr(self, TARGET_COLUMNS[self.target_type])


class PreviewAssignment(Base):
    """发布到班级的预习。快照不可变，无 version。"""

    __tablename__ = "preview_assignments"
    __table_args__ = (
        Index("ix_preview_assignments_class_created", "class_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("lesson_plans.id", ondelete="RESTRICT"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )
    due_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)


# ---- 公开字段映射（APIC 第 2 节字段模型）----

def plan_item_public(item: LessonPlanItem) -> dict:
    return {
        "sort_order": item.sort_order,
        "target_type": item.target_type,
        "target_id": item.target_id,
    }


def plan_public(plan: LessonPlan, items) -> dict:
    return {
        "id": plan.id,
        "title": plan.title,
        "planned_at": plan.planned_at,
        "notes": plan.notes,
        "items": [plan_item_public(item) for item in items],
        "owner_id": plan.owner_id,
        "version": plan.version,
    }


def preview_public(preview: PreviewAssignment, snapshot: dict) -> dict:
    return {
        "id": preview.id,
        "class_id": preview.class_id,
        "plan_id": preview.plan_id,
        "plan_title": snapshot.get("plan_title", ""),
        "due_at": preview.due_at,
        "items": snapshot.get("items", []),
    }
