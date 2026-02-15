import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    lifetime_years: int = Field(default=25, ge=1, le=50)
    discount_rate: float = Field(default=0.08, ge=0, le=1)
    currency: str = Field(default="USD", max_length=3)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    lifetime_years: int | None = Field(default=None, ge=1, le=50)
    discount_rate: float | None = Field(default=None, ge=0, le=1)
    currency: str | None = Field(default=None, max_length=3)


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    latitude: float
    longitude: float
    lifetime_years: int
    discount_rate: float
    currency: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
