import uuid
from datetime import datetime

from sqlalchemy import String, Integer, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class BatchRun(Base):
    __tablename__ = "batch_runs"

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
    sweep_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    results_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    completed_runs: Mapped[int] = mapped_column(Integer, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship()  # noqa: F821
    simulations: Mapped[list["Simulation"]] = relationship(  # noqa: F821
        back_populates="batch_run"
    )
