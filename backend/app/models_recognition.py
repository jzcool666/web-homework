"""SPEC-017 数据模型：recognition_tasks。

字段、索引以 DBD 第 7 节为准；表由迁移 0011 创建，不在启动时建表。
任务一次生成后不再修改，因此没有 version/updated_at；class_id 固定为创建时的班级，
用于之后按任课关系核对读取权限。
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import now_utc

KIND_STATE_TABLE = "state_table"
KINDS = (KIND_STATE_TABLE,)
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUSES = (STATUS_DONE, STATUS_FAILED)


class RecognitionTask(Base):
    __tablename__ = "recognition_tasks"
    __table_args__ = (
        CheckConstraint("kind IN ('state_table')", name="ck_recognition_tasks_kind"),
        CheckConstraint("status IN ('done','failed')", name="ck_recognition_tasks_status"),
        Index("ix_recognition_tasks_owner_created", "owner_id", "created_at"),
        Index("ix_recognition_tasks_class_created", "class_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False, default=KIND_STATE_TABLE)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # 失败任务只写 error_json，result_json 保持为空
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_json: Mapped[str | None] = mapped_column(Text, nullable=True)
