"""SPEC-004 数据模型：warning_snapshots。

字段、可空性、索引以 DBD 第 7 节为准；表由迁移 0009 创建，不在启动时建表。
一次显式生成写入一个批次：同 class_id、同窗口、同 generated_at，批次号与
证据一起存进 evidence_json，因此后续数据变化必须再次生成，旧快照不被当作实时数据。
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import now_utc

LEVELS = ("insufficient", "low", "medium", "high")


class WarningSnapshot(Base):
    __tablename__ = "warning_snapshots"
    __table_args__ = (
        CheckConstraint(
            "level IN ('insufficient','low','medium','high')",
            name="ck_warning_snapshots_level",
        ),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_warning_snapshots_score",
        ),
        CheckConstraint(
            "cluster_label IS NULL OR cluster_label IN (0,1,2)",
            name="ck_warning_snapshots_cluster",
        ),
        Index("ix_warning_snapshots_class_generated", "class_id", "generated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    window_start: Mapped[str] = mapped_column(Text, nullable=False)
    window_end: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    cluster_label: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
