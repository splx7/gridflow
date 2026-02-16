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
    scenario: str | None = Field(
        default=None,
        description="Single scenario key. Required if 'scenarios' is not provided.",
    )
    scenarios: list[str] | None = Field(
        default=None,
        description="Multiple scenario keys for composite load profile. "
        "If provided, profiles are combined with annual_kwh weighting.",
    )
    annual_kwh: float | None = Field(
        default=None,
        description="Override annual energy consumption in kWh. If omitted, uses scenario default(s).",
    )
