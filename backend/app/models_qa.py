"""SPEC-007 数据模型：qa_entries。

字段、可空性、唯一键与索引以 DBD 第 7 节为准；表由迁移 0009 创建，不在启动时建表。
问答条目是教师维护的课程语料：每条挂在一个知识点上，供检索时作为来源。
向量索引不落库，是按语料指纹重建的内存数据（SPEC-007 第 3 节）。
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import now_utc

QUESTION_MAX = 200
ANSWER_MD_MAX = 10000


class QAEntry(Base):
    __tablename__ = "qa_entries"
    __table_args__ = (
        CheckConstraint("published IN (0,1)", name="ck_qa_entries_published"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    knowledge_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), nullable=False
    )
    question: Mapped[str] = mapped_column(String(QUESTION_MAX), nullable=False)
    answer_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


# ---- 公开字段映射（APIC 第 2、7 节字段模型）----

def qa_entry_public(entry: QAEntry) -> dict:
    return {
        "id": entry.id,
        "knowledge_id": entry.knowledge_id,
        "question": entry.question,
        "answer_md": entry.answer_md,
        "source_url": entry.source_url,
        "published": bool(entry.published),
        "owner_id": entry.owner_id,
        "version": entry.version,
    }
