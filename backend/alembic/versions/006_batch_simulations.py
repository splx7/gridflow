"""Add batch simulation tables.

Revision ID: 006_batch_simulations
Revises: 005_annotations
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006_batch_simulations"
down_revision = "005_annotations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batch_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("sweep_config", postgresql.JSONB, nullable=False),
        sa.Column("results_summary", postgresql.JSONB, nullable=True),
        sa.Column("total_runs", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_runs", sa.Integer, nullable=False, server_default="0"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_batch_runs_project_id", "batch_runs", ["project_id"])

    op.add_column(
        "simulations",
        sa.Column(
            "batch_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("batch_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("simulations", "batch_run_id")
    op.drop_index("ix_batch_runs_project_id")
    op.drop_table("batch_runs")
