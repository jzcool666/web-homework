"""SPEC-005 课程内容表：chapters、knowledge_points、knowledge_edges、resources、
resource_versions、favorites、learning_progress、resource_events。

Revision ID: 0003_spec005
Revises: 0002_spec001
Create Date: 2026-09-29

字段、可空性、唯一键与索引以 DBD 第 3 节为准。关联表（knowledge_edges、
favorites、learning_progress、resource_events）按 DBD 第 1 节「除关联表外，
各表均有 id、created_at」的约定不带 id，以复合主键保证唯一。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_spec005"
down_revision = "0002_spec001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("published", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_chapters_sort_order"),
        sa.CheckConstraint("published IN (0,1)", name="ck_chapters_published"),
    )

    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("published", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_knowledge_points_sort_order"),
        sa.CheckConstraint("published IN (0,1)", name="ck_knowledge_points_published"),
    )
    op.create_index(
        "ix_knowledge_points_chapter_published",
        "knowledge_points",
        ["chapter_id", "published"],
    )

    op.create_table(
        "knowledge_edges",
        sa.Column(
            "prerequisite_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "target_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.CheckConstraint("prerequisite_id <> target_id", name="ck_knowledge_edges_distinct"),
    )

    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column(
            "knowledge_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("published", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('slides','guide','reference','video')",
            name="ck_resources_category",
        ),
        sa.CheckConstraint("published IN (0,1)", name="ck_resources_published"),
    )
    op.create_index("ix_resources_category_published", "resources", ["category", "published"])

    op.create_table(
        "resource_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column(
            "resource_id",
            sa.Integer(),
            sa.ForeignKey("resources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("original_name", sa.Text(), nullable=True),
        sa.Column("mime", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("note", sa.String(200), nullable=False, server_default=sa.text("''")),
        sa.CheckConstraint("version_no >= 1", name="ck_resource_versions_version_no"),
        sa.CheckConstraint("kind IN ('file','link')", name="ck_resource_versions_kind"),
        # 文件类必须有文件字段，链接类必须有 URL（DBD 第 3 节）；
        # 表达式与 models_content.py 中的同名约束逐字一致，便于 autogenerate 对照。
        sa.CheckConstraint(
            "(kind = 'file' AND storage_key IS NOT NULL AND original_name IS NOT NULL"
            " AND mime IS NOT NULL AND size_bytes IS NOT NULL AND sha256 IS NOT NULL"
            " AND external_url IS NULL) OR (kind = 'link' AND external_url IS NOT NULL"
            " AND storage_key IS NULL)",
            name="ck_resource_versions_shape",
        ),
        sa.UniqueConstraint("resource_id", "version_no", name="uq_resource_versions_no"),
    )

    op.create_table(
        "favorites",
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "knowledge_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    op.create_table(
        "learning_progress",
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "knowledge_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_points.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("completed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.CheckConstraint("completed IN (0,1)", name="ck_learning_progress_completed"),
        # 取消完成必须清空 completed_at，不允许出现「未完成但有完成时间」
        sa.CheckConstraint(
            "completed = 1 OR completed_at IS NULL",
            name="ck_learning_progress_completed_at",
        ),
    )

    op.create_table(
        "resource_events",
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "resource_version_id",
            sa.Integer(),
            sa.ForeignKey("resource_versions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("event_kind", sa.String(8), primary_key=True),
        sa.Column("event_day", sa.String(10), primary_key=True),
        sa.CheckConstraint(
            "event_kind IN ('open','download')", name="ck_resource_events_kind"
        ),
    )


def downgrade() -> None:
    op.drop_table("resource_events")
    op.drop_table("learning_progress")
    op.drop_table("favorites")
    op.drop_table("resource_versions")
    op.drop_index("ix_resources_category_published", table_name="resources")
    op.drop_table("resources")
    op.drop_table("knowledge_edges")
    op.drop_index("ix_knowledge_points_chapter_published", table_name="knowledge_points")
    op.drop_table("knowledge_points")
    op.drop_table("chapters")
