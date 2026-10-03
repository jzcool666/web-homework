"""SPEC-005 数据模型：章节、知识点、先修关系、资源与资源版本、收藏、进度、资源事件。

字段、可空性、唯一键与索引以 DBD 第 3 节为准；表由迁移 0003 创建，不在启动时建表。
本模块同时提供「模型 → 接口响应」的公开字段映射，保证 storage_key、sha256 等
内部字段永不进入响应（APIC 第 2 节 ResourceVersion 明确「无 storage_key」）。
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
from .models import now_utc


def utc_day() -> str:
    """资源事件的去重粒度：UTC 整日（DBD 第 3 节）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


RESOURCE_CATEGORIES = ("slides", "guide", "reference", "video")
RESOURCE_VERSION_KINDS = ("file", "link")
RESOURCE_EVENT_KINDS = ("open", "download")

BODY_MD_MAX = 20000
TITLE_MAX = 100
NOTE_MAX = 200
SOURCE_URL_MAX = 500

MAX_KNOWLEDGE_EDGES = 1000  # DBD 第 3 节：最多 1000 条边


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="ck_chapters_sort_order"),
        CheckConstraint("published IN (0,1)", name="ck_chapters_published"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    title: Mapped[str] = mapped_column(String(TITLE_MAX), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="ck_knowledge_points_sort_order"),
        CheckConstraint("published IN (0,1)", name="ck_knowledge_points_published"),
        Index("ix_knowledge_points_chapter_published", "chapter_id", "published"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(TITLE_MAX), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class KnowledgeEdge(Base):
    """先修关系：prerequisite_id → target_id（先修指向后继）。

    关联表，无 id/created_at（DBD 第 1 节）。写入只由课程种子完成并做无环校验，
    读取投影属于 SPEC-016。
    """

    __tablename__ = "knowledge_edges"
    __table_args__ = (
        CheckConstraint("prerequisite_id <> target_id", name="ck_knowledge_edges_distinct"),
    )

    prerequisite_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), primary_key=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), primary_key=True
    )


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint(
            "category IN ('slides','guide','reference','video')", name="ck_resources_category"
        ),
        CheckConstraint("published IN (0,1)", name="ck_resources_published"),
        Index("ix_resources_category_published", "category", "published"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    title: Mapped[str] = mapped_column(String(TITLE_MAX), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    knowledge_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), nullable=True
    )
    published: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class ResourceVersion(Base):
    """资源版本：追加后不可修改（DBD 第 3 节）。

    不设 updated_at/version —— 本表只追加、不改写；历史版本的下载内容因此恒定。
    """

    __tablename__ = "resource_versions"
    __table_args__ = (
        CheckConstraint("version_no >= 1", name="ck_resource_versions_version_no"),
        CheckConstraint("kind IN ('file','link')", name="ck_resource_versions_kind"),
        # 文件类必须有文件字段，链接类必须有 URL（DBD 第 3 节）；
        # 表达式与迁移 0003 中的同名约束逐字一致，便于 autogenerate 对照。
        CheckConstraint(
            "(kind = 'file' AND storage_key IS NOT NULL AND original_name IS NOT NULL"
            " AND mime IS NOT NULL AND size_bytes IS NOT NULL AND sha256 IS NOT NULL"
            " AND external_url IS NULL) OR (kind = 'link' AND external_url IS NOT NULL"
            " AND storage_key IS NULL)",
            name="ck_resource_versions_shape",
        ),
        UniqueConstraint("resource_id", "version_no", name="uq_resource_versions_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="RESTRICT"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str] = mapped_column(String(NOTE_MAX), nullable=False, default="")


class Favorite(Base):
    """收藏：关联表，允许物理删除（DBD 第 3 节）。"""

    __tablename__ = "favorites"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    knowledge_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), primary_key=True
    )


class LearningProgress(Base):
    """学习进度：完成为学生自报记录，不存「掌握分」（DBD 第 3 节）。"""

    __tablename__ = "learning_progress"
    __table_args__ = (
        CheckConstraint("completed IN (0,1)", name="ck_learning_progress_completed"),
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    knowledge_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), primary_key=True
    )
    completed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResourceEvent(Base):
    """资源访问事件：按 学生 + 版本 + 类型 + UTC 日 去重（DBD 第 3 节）。"""

    __tablename__ = "resource_events"
    __table_args__ = (
        CheckConstraint(
            "event_kind IN ('open','download')", name="ck_resource_events_kind"
        ),
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    resource_version_id: Mapped[int] = mapped_column(
        ForeignKey("resource_versions.id", ondelete="RESTRICT"), primary_key=True
    )
    event_kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    event_day: Mapped[str] = mapped_column(String(10), primary_key=True)


# ---- 公开字段映射（APIC 第 2 节字段模型）----

def chapter_public(chapter: Chapter) -> dict:
    return {
        "id": chapter.id,
        "title": chapter.title,
        "sort_order": chapter.sort_order,
        "published": bool(chapter.published),
        "owner_id": chapter.owner_id,
        "version": chapter.version,
    }


def knowledge_public(point: KnowledgePoint) -> dict:
    return {
        "id": point.id,
        "chapter_id": point.chapter_id,
        "title": point.title,
        "body_md": point.body_md,
        "source_url": point.source_url,
        "sort_order": point.sort_order,
        "published": bool(point.published),
        "owner_id": point.owner_id,
        "version": point.version,
    }


def resource_version_public(version: ResourceVersion) -> dict:
    """不含 storage_key 与 sha256：磁盘定位与校验值只在服务端使用。"""
    return {
        "id": version.id,
        "version_no": version.version_no,
        "kind": version.kind,
        "original_name": version.original_name,
        "mime": version.mime,
        "size_bytes": version.size_bytes,
        "external_url": version.external_url,
        "note": version.note,
        "created_at": version.created_at,
    }


def resource_public(resource: Resource, versions: list[ResourceVersion]) -> dict:
    return {
        "id": resource.id,
        "title": resource.title,
        "category": resource.category,
        "knowledge_id": resource.knowledge_id,
        "published": bool(resource.published),
        "owner_id": resource.owner_id,
        "version": resource.version,
        "versions": [resource_version_public(v) for v in versions],
    }


def progress_public(progress: LearningProgress) -> dict:
    return {
        "knowledge_id": progress.knowledge_id,
        "completed": bool(progress.completed),
        "completed_at": progress.completed_at,
    }
