"""SPEC-013 数据模型：experiment_attempts。

字段、可空性、唯一键与索引以 DBD 第 6 节为准；表由迁移 0007 创建，不在启动时建表。
尝试记录只追加、不修改：保存提交时的实验快照、学生预测与服务端标准状态，
使实验事后被编辑也不改变历史判分（DBD 第 6 节、ADR-005）。
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .experiment_service import explain, replay_checkpoints
from .models import now_utc
from .models_experiment import load_json


class ExperimentAttempt(Base):
    __tablename__ = "experiment_attempts"
    __table_args__ = (
        # request_key 按学生唯一：同一学生用同一个 key 重试不会新增记录
        UniqueConstraint("student_id", "request_key", name="uq_experiment_attempts_student_key"),
        Index("ix_experiment_attempts_experiment_student", "experiment_id", "student_id"),
        CheckConstraint("passed IN (0,1)", name="ck_experiment_attempts_passed"),
        CheckConstraint(
            "first_error_index IS NULL OR first_error_index >= 0",
            name="ck_experiment_attempts_first_error",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="RESTRICT"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # 提交时的实验快照：模型类型、配置、固定输入序列与当时的版本号
    experiment_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    predictions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    expected_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    passed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    first_error_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_key: Mapped[str] = mapped_column(Text, nullable=False)


def experiment_attempt_snapshot(
    simulator_type: str, config: dict, input_sequence: list, experiment_version: int
) -> dict:
    """提交时固定下来的实验口径；读取历史时据此重算说明文字。"""
    return {
        "simulator_type": simulator_type,
        "config": config,
        "input_sequence": input_sequence,
        "experiment_version": experiment_version,
    }


def attempt_public(attempt: ExperimentAttempt) -> dict:
    """AttemptResult（APIC 第 2、6 节）。

    expected 为服务端标准状态，actual 为学生提交的预测；
    explanations 由提交时的快照重算，因此历史记录不会随实验改动而变化。
    """
    snapshot = load_json(attempt.experiment_snapshot_json, {})
    predictions = load_json(attempt.predictions_json, [])
    expected = load_json(attempt.expected_json, [])
    simulator_type = snapshot.get("simulator_type")
    checkpoints = replay_checkpoints(
        simulator_type, snapshot.get("config", {}), snapshot.get("input_sequence", [])
    )
    return {
        "id": attempt.id,
        "created_at": attempt.created_at,
        "experiment_id": attempt.experiment_id,
        "simulator_type": simulator_type,
        "passed": bool(attempt.passed),
        "first_error_index": attempt.first_error_index,
        "expected": expected,
        "actual": predictions,
        "explanations": explain(simulator_type, checkpoints, predictions),
        "experiment_version": snapshot.get("experiment_version"),
    }


__all__ = ["ExperimentAttempt", "attempt_public", "experiment_attempt_snapshot"]
