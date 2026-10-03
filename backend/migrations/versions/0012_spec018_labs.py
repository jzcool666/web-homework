"""Physical wiring and Logisim grading facts; no runtime table creation."""

import sqlalchemy as sa
from alembic import op

revision = "0012_spec018"
down_revision = "0011_spec017"
branch_labels = None
depends_on = None


def common():
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ]


def fk(name, target, nullable=False):
    return sa.Column(
        name,
        sa.Integer(),
        sa.ForeignKey(target, ondelete="RESTRICT"),
        nullable=nullable,
    )


def txt(name, nullable=False):
    return sa.Column(name, sa.Text(), nullable=nullable)


def upgrade():
    op.create_table(
        "lab_tasks",
        *common(),
        txt("code"),
        txt("title"),
        fk("knowledge_id", "knowledge_points.id"),
        sa.Column("published", sa.Integer(), nullable=False),
        txt("catalog_version"),
        txt("suite_version"),
        txt("engine_contract_version"),
        txt("public_profile_json"),
        txt("private_suite_json"),
        txt("template_key"),
        sa.UniqueConstraint("code"),
        sa.CheckConstraint("published IN (0,1)", name="ck_lab_task_published"),
    )
    op.create_table(
        "lab_sessions",
        *common(),
        fk("task_id", "lab_tasks.id"),
        fk("owner_id", "users.id"),
        fk("class_id", "classes.id"),
        txt("kind"),
        sa.Column("task_version", sa.Integer(), nullable=False),
        txt("task_snapshot_json"),
        txt("board_json"),
        txt("event_log_json"),
        txt("request_key"),
        txt("request_hash"),
        txt("saved_at"),
        sa.UniqueConstraint("owner_id", "request_key", name="uq_lab_session_request"),
        sa.CheckConstraint("kind IN ('practice','demo')", name="ck_lab_session_kind"),
    )
    op.create_index(
        "ix_lab_session_class_owner", "lab_sessions", ["class_id", "owner_id"]
    )
    op.create_table(
        "lab_attempts",
        *common(),
        fk("task_id", "lab_tasks.id"),
        fk("student_id", "users.id"),
        fk("class_id", "classes.id"),
        txt("mode"),
        fk("session_id", "lab_sessions.id", True),
        txt("request_key"),
        txt("request_hash"),
        txt("task_snapshot_json"),
        txt("suite_snapshot_json"),
        txt("suite_version"),
        txt("engine_version"),
        txt("session_snapshot_json", True),
        txt("storage_key", True),
        txt("original_name", True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        txt("sha256", True),
        txt("status"),
        txt("started_at", True),
        txt("finished_at", True),
        txt("lease_until", True),
        txt("worker_token", True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Integer(), nullable=True),
        txt("result_json", True),
        txt("error_json", True),
        sa.UniqueConstraint("student_id", "request_key", name="uq_lab_attempt_request"),
        sa.CheckConstraint("mode IN ('wiring','circ')", name="ck_lab_attempt_mode"),
        sa.CheckConstraint(
            "status IN ('queued','running','done','error')",
            name="ck_lab_attempt_status",
        ),
        sa.CheckConstraint(
            "(mode='wiring' AND session_id IS NOT NULL AND session_snapshot_json IS NOT NULL AND storage_key IS NULL) OR (mode='circ' AND session_id IS NULL AND storage_key IS NOT NULL AND original_name IS NOT NULL AND size_bytes IS NOT NULL AND sha256 IS NOT NULL)",
            name="ck_lab_attempt_artifact",
        ),
        sa.CheckConstraint(
            "(status='done' AND score IS NOT NULL AND score BETWEEN 0 AND 100 AND passed IS NOT NULL AND passed IN (0,1) AND result_json IS NOT NULL) OR (status<>'done' AND score IS NULL AND passed IS NULL)",
            name="ck_lab_attempt_grade",
        ),
    )
    for name, cols in [
        ("ix_lab_attempt_queue", ["status", "created_at"]),
        ("ix_lab_attempt_class_task_student", ["class_id", "task_id", "student_id"]),
        ("ix_lab_attempt_lease", ["lease_until"]),
    ]:
        op.create_index(name, "lab_attempts", cols)


def downgrade():
    op.drop_table("lab_attempts")
    op.drop_table("lab_sessions")
    op.drop_table("lab_tasks")
