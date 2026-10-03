"""SPEC-018/019 persistent facts. Tables are created only by Alembic."""

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    Float,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import now_utc


class LabCommon:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, default=now_utc)
    updated_at: Mapped[str] = mapped_column(Text, default=now_utc, onupdate=now_utc)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class LabTask(LabCommon, Base):
    __tablename__ = "lab_tasks"
    __table_args__ = (
        CheckConstraint("published IN (0,1)", name="ck_lab_task_published"),
    )
    code: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    knowledge_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT")
    )
    published: Mapped[int] = mapped_column(Integer, default=1)
    catalog_version: Mapped[str] = mapped_column(Text)
    suite_version: Mapped[str] = mapped_column(Text)
    engine_contract_version: Mapped[str] = mapped_column(Text)
    public_profile_json: Mapped[str] = mapped_column(Text)
    private_suite_json: Mapped[str] = mapped_column(Text)
    template_key: Mapped[str] = mapped_column(Text)


class LabSession(LabCommon, Base):
    __tablename__ = "lab_sessions"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_key", name="uq_lab_session_request"),
        Index("ix_lab_session_class_owner", "class_id", "owner_id"),
        CheckConstraint("kind IN ('practice','demo')", name="ck_lab_session_kind"),
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("lab_tasks.id", ondelete="RESTRICT")
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(Text)
    task_version: Mapped[int] = mapped_column(Integer)
    task_snapshot_json: Mapped[str] = mapped_column(Text)
    board_json: Mapped[str] = mapped_column(Text)
    event_log_json: Mapped[str] = mapped_column(Text)
    request_key: Mapped[str] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(Text)
    saved_at: Mapped[str] = mapped_column(Text, default=now_utc)


class LabAttempt(LabCommon, Base):
    __tablename__ = "lab_attempts"
    __table_args__ = (
        UniqueConstraint("student_id", "request_key", name="uq_lab_attempt_request"),
        Index("ix_lab_attempt_queue", "status", "created_at"),
        Index("ix_lab_attempt_class_task_student", "class_id", "task_id", "student_id"),
        Index("ix_lab_attempt_lease", "lease_until"),
        CheckConstraint("mode IN ('wiring','circ')", name="ck_lab_attempt_mode"),
        CheckConstraint(
            "status IN ('queued','running','done','error')",
            name="ck_lab_attempt_status",
        ),
        CheckConstraint(
            "(mode='wiring' AND session_id IS NOT NULL AND session_snapshot_json IS NOT NULL AND storage_key IS NULL) OR (mode='circ' AND session_id IS NULL AND storage_key IS NOT NULL AND original_name IS NOT NULL AND size_bytes IS NOT NULL AND sha256 IS NOT NULL)",
            name="ck_lab_attempt_artifact",
        ),
        CheckConstraint(
            "(status='done' AND score IS NOT NULL AND score BETWEEN 0 AND 100 AND passed IS NOT NULL AND passed IN (0,1) AND result_json IS NOT NULL) OR (status<>'done' AND score IS NULL AND passed IS NULL)",
            name="ck_lab_attempt_grade",
        ),
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("lab_tasks.id", ondelete="RESTRICT")
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"))
    mode: Mapped[str] = mapped_column(Text)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("lab_sessions.id", ondelete="RESTRICT"), nullable=True
    )
    request_key: Mapped[str] = mapped_column(Text)
    request_hash: Mapped[str] = mapped_column(Text)
    task_snapshot_json: Mapped[str] = mapped_column(Text)
    suite_snapshot_json: Mapped[str] = mapped_column(Text)
    suite_version: Mapped[str] = mapped_column(Text)
    engine_version: Mapped[str] = mapped_column(Text)
    session_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_until: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_json: Mapped[str | None] = mapped_column(Text, nullable=True)
