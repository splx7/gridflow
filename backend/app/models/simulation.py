import uuid
from datetime import datetime

from sqlalchemy import String, Float, ForeignKey, DateTime, LargeBinary, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # pending, running, completed, failed
    dispatch_strategy: Mapped[str] = mapped_column(
        String(50), nullable=False, default="load_following"
    )
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship(back_populates="simulations")  # noqa: F821
    results: Mapped["SimulationResult | None"] = relationship(  # noqa: F821
        back_populates="simulation", uselist=False, cascade="all, delete"
    )


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    simulation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Economics
    npc: Mapped[float] = mapped_column(Float, nullable=False)
    lcoe: Mapped[float] = mapped_column(Float, nullable=False)
    irr: Mapped[float | None] = mapped_column(Float)
    payback_years: Mapped[float | None] = mapped_column(Float)
    renewable_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    co2_emissions_kg: Mapped[float] = mapped_column(Float, nullable=False)
    cost_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Time-series (8760 float64 compressed)
    ts_load: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ts_pv_output: Mapped[bytes | None] = mapped_column(LargeBinary)
    ts_wind_output: Mapped[bytes | None] = mapped_column(LargeBinary)
    ts_battery_soc: Mapped[bytes | None] = mapped_column(LargeBinary)
    ts_battery_power: Mapped[bytes | None] = mapped_column(LargeBinary)
    ts_generator_output: Mapped[bytes | None] = mapped_column(LargeBinary)
    ts_grid_import: Mapped[bytes | None] = mapped_column(LargeBinary)
    ts_grid_export: Mapped[bytes | None] = mapped_column(LargeBinary)
    ts_excess: Mapped[bytes | None] = mapped_column(LargeBinary)
    ts_unmet: Mapped[bytes | None] = mapped_column(LargeBinary)

    # Network / power flow results (multi_bus mode)
    power_flow_summary: Mapped[dict | None] = mapped_column(JSONB)
    ts_bus_voltages: Mapped[dict | None] = mapped_column(JSONB)

    # Sensitivity analysis results
    sensitivity_results: Mapped[dict | None] = mapped_column(JSONB)

    simulation: Mapped["Simulation"] = relationship(back_populates="results")
