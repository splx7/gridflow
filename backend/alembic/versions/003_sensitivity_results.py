"""Add sensitivity_results JSONB column to simulation_results.

Revision ID: 003_sensitivity
Revises: 002_network
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_sensitivity"
down_revision = "002_network"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulation_results",
        sa.Column("sensitivity_results", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("simulation_results", "sensitivity_results")
