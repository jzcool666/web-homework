"""SPEC-009 数据模型：题库与测评。

字段、可空性、唯一键与索引以 DBD 第 5 节为准；表由迁移 0005 创建，
不在启动时建表。公开字段映射见本文件末尾。

两条不变式贯穿本模块：
- 选项与答案以 JSON TEXT 保存在 questions，结构由服务层校验；表只约束取值域。
- 判分只读 assessment_items.snapshot_json（发布时冻结），题目表的后续修改
  不会改变已发布测评的题目、答案或已有成绩。
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
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import now_utc

TYPE_SINGLE = "single"
TYPE_MULTIPLE = "multiple"
TYPE_BOOLEAN = "boolean"
QUESTION_TYPES = (TYPE_SINGLE, TYPE_MULTIPLE, TYPE_BOOLEAN)
DIFFICULTIES = (1, 2, 3)

KIND_PRACTICE = "practice"
KIND_QUIZ = "quiz"
KIND_HOMEWORK = "homework"
KIND_EXAM = "exam"
# E037 只创建课堂测评；自练由 E042 生成
CLASS_KINDS = (KIND_QUIZ, KIND_HOMEWORK, KIND_EXAM)
ASSESSMENT_KINDS = (KIND_PRACTICE,) + CLASS_KINDS

STATE_DRAFT = "draft"
STATE_PUBLISHED = "published"
STATE_CLOSED = "closed"
ASSESSMENT_STATES = (STATE_DRAFT, STATE_PUBLISHED, STATE_CLOSED)

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"

REASON_MANUAL = "manual"
REASON_TIMEOUT = "timeout"

PRACTICE_HOURS = 24
MAX_ITEMS = 30
MIN_ITEMS = 1
POINTS_MIN = 1
POINTS_MAX = 100


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def from_json(raw: str | None, default=None):
    if not raw:
        return default if default is not None else []
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default if default is not None else []


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("type IN ('single','multiple','boolean')", name="ck_questions_type"),
        CheckConstraint("difficulty IN (1,2,3)", name="ck_questions_difficulty"),
        CheckConstraint("published IN (0,1)", name="ck_questions_published"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    stem_md: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    answer_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    explanation_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    published: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    @property
    def options(self) -> list[dict]:
        return from_json(self.options_json)

    @property
    def answer(self) -> list[str]:
        return from_json(self.answer_json)

    @property
    def option_keys(self) -> list[str]:
        return [option.get("key") for option in self.options]


class QuestionKnowledge(Base):
    """关联表：无独立 id/version（DBD 第 1 节）。"""

    __tablename__ = "question_knowledge"

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), primary_key=True
    )
    knowledge_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), primary_key=True
    )


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('practice','quiz','homework','exam')", name="ck_assessments_kind"
        ),
        CheckConstraint(
            "state IN ('draft','published','closed')", name="ck_assessments_state"
        ),
        CheckConstraint("origin IN ('manual','generated')", name="ck_assessments_origin"),
        CheckConstraint("feedback_released IN (0,1)", name="ck_assessments_feedback"),
        CheckConstraint("total_score >= 0", name="ck_assessments_total_score"),
        Index("ix_assessments_class_state_ends", "class_id", "state", "ends_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    class_id: Mapped[int | None] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=True
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    starts_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    ends_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_released: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    generation_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssessmentItem(Base):
    __tablename__ = "assessment_items"
    __table_args__ = (
        CheckConstraint("points BETWEEN 1 AND 100", name="ck_assessment_items_points"),
        CheckConstraint("position >= 1", name="ck_assessment_items_position"),
        UniqueConstraint("assessment_id", "position", name="uq_assessment_items_position"),
        UniqueConstraint("assessment_id", "question_id", name="uq_assessment_items_question"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    @property
    def snapshot(self) -> dict:
        return from_json(self.snapshot_json, default={})


class AssessmentRoster(Base):
    """关联表：发布时固定的名单（practice 只有创建学生）。"""

    __tablename__ = "assessment_roster"

    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT"), primary_key=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        CheckConstraint("status IN ('draft','submitted')", name="ck_submissions_status"),
        CheckConstraint(
            "submit_reason IS NULL OR submit_reason IN ('manual','timeout')",
            name="ck_submissions_reason",
        ),
        CheckConstraint("score IS NULL OR score >= 0", name="ck_submissions_score"),
        UniqueConstraint("assessment_id", "student_id", name="uq_submissions_assessment_student"),
        Index("ix_submissions_student_submitted", "student_id", "submitted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=now_utc)
    updated_at: Mapped[str] = mapped_column(
        Text, nullable=False, default=now_utc, onupdate=now_utc
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    submit_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)


class SubmissionAnswer(Base):
    """关联表：一名学生对一个测评条目的作答。"""

    __tablename__ = "submission_answers"
    __table_args__ = (
        CheckConstraint(
            "correct IS NULL OR correct IN (0,1)", name="ck_submission_answers_correct"
        ),
    )

    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="RESTRICT"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_items.id", ondelete="RESTRICT"), primary_key=True
    )
    selected_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    correct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    awarded_points: Mapped[int | None] = mapped_column(Integer, nullable=True)

    @property
    def selected(self) -> list[str]:
        return from_json(self.selected_json)


# ---- 公开字段映射（APIC 第 2、5 节字段模型）----

def question_public(question: Question, knowledge_ids=None) -> dict:
    """Question 模型：仅题库管理接口返回完整答案与解析。"""
    return {
        "id": question.id,
        "type": question.type,
        "stem_md": question.stem_md,
        "options": question.options,
        "answer": question.answer,
        "explanation_md": question.explanation_md,
        "difficulty": question.difficulty,
        "knowledge_ids": list(knowledge_ids or []),
        "published": bool(question.published),
        "owner_id": question.owner_id,
        "version": question.version,
    }


def student_item_public(item: AssessmentItem) -> dict:
    """StudentItem 模型：服务器投影掉 answer/explanation/difficulty。"""
    snapshot = item.snapshot
    return {
        "id": item.id,
        "question_id": item.question_id,
        "position": item.position,
        "points": item.points,
        "type": snapshot.get("type"),
        "stem_md": snapshot.get("stem_md"),
        "options": snapshot.get("options", []),
        "knowledge_ids": snapshot.get("knowledge_ids", []),
    }


def effective_state(assessment: Assessment, now_iso: str) -> str:
    """按服务器当前时间计算展示状态；draft 与 closed 直接沿用落库状态。"""
    if assessment.state == STATE_DRAFT:
        return "draft"
    if assessment.state == STATE_CLOSED:
        return "closed"
    if assessment.starts_at and now_iso < assessment.starts_at:
        return "upcoming"
    if assessment.ends_at and now_iso >= assessment.ends_at:
        return "closed"
    return "open"


def assessment_public(assessment: Assessment, items=None, my_submission_id=None, now_iso=None) -> dict:
    payload = {
        "id": assessment.id,
        "class_id": assessment.class_id,
        "kind": assessment.kind,
        "title": assessment.title,
        "state": assessment.state,
        "effective_state": effective_state(assessment, now_iso) if now_iso else assessment.state,
        "starts_at": assessment.starts_at,
        "ends_at": assessment.ends_at,
        "feedback_released": bool(assessment.feedback_released),
        "total_score": assessment.total_score,
        "version": assessment.version,
        "my_submission_id": my_submission_id,
        "items": [],
    }
    if items is not None:
        payload["items"] = [student_item_public(item) for item in items]
    return payload


def submission_public(submission: Submission, answers=None, show_score: bool = True) -> dict:
    """Submission 模型。

    show_score=False 时把 score 投影为 null：班级测评的分数属于反馈策略的一部分，
    未公开反馈前返回分数等于提前泄露对错，与 E046 的裁剪一致。
    """
    payload = {
        "id": submission.id,
        "assessment_id": submission.assessment_id,
        "student_id": submission.student_id,
        "status": submission.status,
        "answers": [],
        "version": submission.version,
        "saved_at": submission.updated_at,
        "submitted_at": submission.submitted_at,
        "score": submission.score if show_score else None,
    }
    if answers is not None:
        payload["answers"] = [
            {"item_id": answer.item_id, "selected": answer.selected} for answer in answers
        ]
    return payload
