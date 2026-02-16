"""Add network topology: buses, branches, load_allocations.

Revision ID: 002_network
Revises: 001_initial
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_network"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add network_mode to projects
    op.add_column(
        "projects",
        sa.Column("network_mode", sa.String(20), nullable=False, server_default="single_bus"),
    )

    # Buses table
    op.create_table(
        "buses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("bus_type", sa.String(20), nullable=False, server_default="pq"),
        sa.Column("nominal_voltage_kv", sa.Float, nullable=False, server_default="0.4"),
        sa.Column("base_mva", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("x_position", sa.Float, nullable=True),
        sa.Column("y_position", sa.Float, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_buses_project_id", "buses", ["project_id"])

    # Branches table
    op.create_table(
        "branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_bus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("buses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_bus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("buses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("branch_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_branches_project_id", "branches", ["project_id"])

    # Load allocations table
    op.create_table(
        "load_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "load_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("load_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("buses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("fraction", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("power_factor", sa.Float, nullable=False, server_default="0.85"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_load_allocations_project_id", "load_allocations", ["project_id"])

    # Add bus_id to components (nullable for single_bus backward compat)
    op.add_column(
        "components",
        sa.Column(
            "bus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("buses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Add power flow results to simulation_results
    op.add_column(
        "simulation_results",
        sa.Column("power_flow_summary", postgresql.JSONB, nullable=True),
    )
    op.add_column(
        "simulation_results",
        sa.Column("ts_bus_voltages", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("simulation_results", "ts_bus_voltages")
    op.drop_column("simulation_results", "power_flow_summary")
    op.drop_column("components", "bus_id")
    op.drop_index("ix_load_allocations_project_id")
    op.drop_table("load_allocations")
    op.drop_index("ix_branches_project_id")
    op.drop_table("branches")
    op.drop_index("ix_buses_project_id")
    op.drop_table("buses")
    op.drop_column("projects", "network_mode")
