"""Add weather correction columns to weather_datasets.

Revision ID: 004_weather_correction
Revises: 003_sensitivity
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_weather_correction"
down_revision = "003_sensitivity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "weather_datasets",
        sa.Column("correction_applied", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "weather_datasets",
        sa.Column("correction_metadata", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("weather_datasets", "correction_metadata")
    op.drop_column("weather_datasets", "correction_applied")
