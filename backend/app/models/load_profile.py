import uuid
from datetime import datetime

from sqlalchemy import String, Float, ForeignKey, DateTime, LargeBinary, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class LoadProfile(Base):
    __tablename__ = "load_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # residential, commercial, industrial, custom
    annual_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    hourly_kw: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # 8760 float64 compressed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="load_profiles")  # noqa: F821
