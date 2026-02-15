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


class GenerateLoadProfileRequest(BaseModel):
    scenario: str = Field(
        description="One of: residential_small, residential_large, commercial_office, "
        "commercial_retail, industrial_light, industrial_heavy, agricultural"
    )
    annual_kwh: float | None = Field(
        default=None,
        description="Override annual energy consumption in kWh. If omitted, uses scenario default.",
    )
