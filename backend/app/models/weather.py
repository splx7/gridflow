import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, ForeignKey, DateTime, LargeBinary, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class WeatherDataset(Base):
    __tablename__ = "weather_datasets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # pvgis, upload
    ghi: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # 8760 float64 compressed
    dni: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dhi: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    temperature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wind_speed: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    correction_applied: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    correction_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="weather_datasets")  # noqa: F821
