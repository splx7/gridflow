"""Initial schema for GridFlow.

Revision ID: 001_initial
Revises:
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Projects
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("lifetime_years", sa.Integer, default=25),
        sa.Column("discount_rate", sa.Float, default=0.08),
        sa.Column("currency", sa.String(10), default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Components
    op.create_table(
        "components",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("config", postgresql.JSONB, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Weather datasets
    op.create_table(
        "weather_datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(100)),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("ghi", sa.LargeBinary),
        sa.Column("dni", sa.LargeBinary),
        sa.Column("dhi", sa.LargeBinary),
        sa.Column("temperature", sa.LargeBinary),
        sa.Column("wind_speed", sa.LargeBinary),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Load profiles
    op.create_table(
        "load_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("profile_type", sa.String(50)),
        sa.Column("annual_kwh", sa.Float, nullable=False),
        sa.Column("hourly_kw", sa.LargeBinary, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Simulations
    op.create_table(
        "simulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("dispatch_strategy", sa.String(50), nullable=False),
        sa.Column("config_snapshot", postgresql.JSONB, default={}),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("progress", sa.Float, default=0.0),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    # Simulation results
    op.create_table(
        "simulation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("npc", sa.Float),
        sa.Column("lcoe", sa.Float),
        sa.Column("irr", sa.Float),
        sa.Column("payback_years", sa.Float),
        sa.Column("renewable_fraction", sa.Float),
        sa.Column("co2_emissions_kg", sa.Float),
        sa.Column("cost_breakdown", postgresql.JSONB),
        sa.Column("ts_load", sa.LargeBinary),
        sa.Column("ts_pv_output", sa.LargeBinary),
        sa.Column("ts_wind_output", sa.LargeBinary),
        sa.Column("ts_battery_soc", sa.LargeBinary),
        sa.Column("ts_battery_power", sa.LargeBinary),
        sa.Column("ts_generator_output", sa.LargeBinary),
        sa.Column("ts_grid_import", sa.LargeBinary),
        sa.Column("ts_grid_export", sa.LargeBinary),
        sa.Column("ts_excess", sa.LargeBinary),
        sa.Column("ts_unmet", sa.LargeBinary),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("simulation_results")
    op.drop_table("simulations")
    op.drop_table("load_profiles")
    op.drop_table("weather_datasets")
    op.drop_table("components")
    op.drop_table("projects")
    op.drop_table("users")
