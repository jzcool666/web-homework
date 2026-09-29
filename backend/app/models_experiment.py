"""SPEC-012 数据模型：experiments、demo_sessions。

字段、可空性、唯一键与索引以 DBD 第 6 节为准；表由迁移 0005 创建，不在启动时建表。
演示只保存「班级 + 实验 + 配置快照 + 状态 + 事件日志」，不保存学生名单，
也没有学生个人成绩字段（DBD 第 6 节）。
"""

from __future__ import annotations

import json

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import now_utc
from .simulator import SIMULATOR_TYPES

TITLE_MAX = 100
STEPS_MD_MAX = 10000


def dump_json(value) -> str:
    """紧凑 JSON：库里存文本，服务层负责结构校验。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load_json(raw: str | None, fallback):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


class Experiment(Base):
    """预置实验定义。不含期望输出：期望状态由 SPEC-013 按同一套仿真规则计算。"""

    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(
            "simulator_type IN ('d','jk','counter','shift')", name="ck_experiments_type"
        ),
        CheckConstraint("published IN (0,1)", name="ck_experiments_published"),
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
    knowledge_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), nullable=False
    )
    simulator_type: Mapped[str] = mapped_column(String(16), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    steps_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    input_sequence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    published: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class DemoSession(Base):
    """班级共享演示。每班最多一个 active=1（部分唯一索引）。"""

    __tablename__ = "demo_sessions"
    __table_args__ = (
        CheckConstraint("active IN (0,1)", name="ck_demo_sessions_active"),
        CheckConstraint("reveal_next IN (0,1)", name="ck_demo_sessions_reveal"),
        Index(
            "uq_demo_sessions_active_class",
            "class_id",
            unique=True,
            sqlite_where=text("active = 1"),
        ),
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
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    active: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    config_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    state_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    event_log_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    reveal_next: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


# ---- 公开字段映射（APIC 第 2、6 节字段模型）----

def experiment_public(experiment: Experiment) -> dict:
    return {
        "id": experiment.id,
        "title": experiment.title,
        "knowledge_id": experiment.knowledge_id,
        "simulator_type": experiment.simulator_type,
        "config": load_json(experiment.config_json, {}),
        "steps_md": experiment.steps_md,
        "input_sequence": load_json(experiment.input_sequence_json, []),
        "published": bool(experiment.published),
        "owner_id": experiment.owner_id,
        "version": experiment.version,
    }


def experiment_snapshot(experiment: Experiment) -> dict:
    """创建演示时固定的配置快照：实验后续修改不影响进行中的演示。"""
    return {
        "id": experiment.id,
        "title": experiment.title,
        "simulator_type": experiment.simulator_type,
        "config": load_json(experiment.config_json, {}),
        "steps_md": experiment.steps_md,
        "published": bool(experiment.published),
    }


def demo_public(
    demo: DemoSession, *, experiment: dict, reveal_next: bool, next_q: int | None
) -> dict:
    """next_q 为隐藏预测时由调用方传 None，响应里不出现未揭示的下一状态。

    experiment 为创建时固定的快照（含 simulator_type 与 config）：演示响应据此
    自足，学生端不必再读实验定义，实验事后被撤回为草稿也不影响进行中的演示。
    """
    return {
        "id": demo.id,
        "class_id": demo.class_id,
        "experiment_id": demo.experiment_id,
        "active": bool(demo.active),
        "version": demo.version,
        "state": load_json(demo.state_json, {}),
        "history": load_json(demo.event_log_json, []),
        "reveal_next": reveal_next,
        "next_q": next_q,
        "last_updated": demo.updated_at,
        "experiment": experiment,
    }


__all__ = [
    "Experiment",
    "DemoSession",
    "SIMULATOR_TYPES",
    "TITLE_MAX",
    "STEPS_MD_MAX",
    "dump_json",
    "load_json",
    "experiment_public",
    "experiment_snapshot",
    "demo_public",
]
