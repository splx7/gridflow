import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Component(Base):
    __tablename__ = "components"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    component_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # solar_pv, wind_turbine, battery, diesel_generator, grid_connection
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="components")  # noqa: F821
