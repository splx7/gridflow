import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LoadAllocationCreate(BaseModel):
    load_profile_id: uuid.UUID
    bus_id: uuid.UUID
    name: str = Field(max_length=255)
    fraction: float = Field(default=1.0, ge=0.0, le=1.0)
    power_factor: float = Field(default=0.85, ge=0.0, le=1.0)


class LoadAllocationUpdate(BaseModel):
    load_profile_id: uuid.UUID | None = None
    bus_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=255)
    fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    power_factor: float | None = Field(default=None, ge=0.0, le=1.0)


class LoadAllocationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    load_profile_id: uuid.UUID
    bus_id: uuid.UUID
    name: str
    fraction: float
    power_factor: float
    created_at: datetime

    model_config = {"from_attributes": True}
