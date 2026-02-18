import uuid
from datetime import datetime

from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    lifetime_years: Mapped[int] = mapped_column(Integer, default=25)
    discount_rate: Mapped[float] = mapped_column(Float, default=0.08)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    network_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="single_bus"
    )  # single_bus, multi_bus
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="projects")  # noqa: F821
    components: Mapped[list["Component"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete"
    )
    weather_datasets: Mapped[list["WeatherDataset"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete"
    )
    load_profiles: Mapped[list["LoadProfile"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete"
    )
    simulations: Mapped[list["Simulation"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete"
    )
    buses: Mapped[list["Bus"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete"
    )
    branches: Mapped[list["Branch"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete"
    )
    load_allocations: Mapped[list["LoadAllocation"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete"
    )
    annotations: Mapped[list["Annotation"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete"
    )
