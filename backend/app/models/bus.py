import uuid
from datetime import datetime

from sqlalchemy import String, Float, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Bus(Base):
    __tablename__ = "buses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bus_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pq"
    )  # slack, pv, pq
    nominal_voltage_kv: Mapped[float] = mapped_column(Float, nullable=False, default=0.4)
    base_mva: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    x_position: Mapped[float | None] = mapped_column(Float)
    y_position: Mapped[float | None] = mapped_column(Float)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="buses")  # noqa: F821
    components: Mapped[list["Component"]] = relationship(back_populates="bus")  # noqa: F821
    from_branches: Mapped[list["Branch"]] = relationship(  # noqa: F821
        back_populates="from_bus", foreign_keys="Branch.from_bus_id"
    )
    to_branches: Mapped[list["Branch"]] = relationship(  # noqa: F821
        back_populates="to_bus", foreign_keys="Branch.to_bus_id"
    )
    load_allocations: Mapped[list["LoadAllocation"]] = relationship(  # noqa: F821
        back_populates="bus", cascade="all, delete"
    )
