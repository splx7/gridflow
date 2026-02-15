import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WeatherDatasetResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PVGISRequest(BaseModel):
    name: str = Field(default="PVGIS TMY", max_length=255)


class LoadProfileResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    profile_type: str
    annual_kwh: float
    created_at: datetime

    model_config = {"from_attributes": True}


class LoadProfileCreate(BaseModel):
    name: str = Field(max_length=255)
    profile_type: str = Field(default="custom")
