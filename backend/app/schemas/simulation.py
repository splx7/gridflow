import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SimulationCreate(BaseModel):
    name: str = Field(max_length=255)
    dispatch_strategy: str = Field(default="load_following")
    weather_dataset_id: uuid.UUID
    load_profile_id: uuid.UUID


class SimulationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    status: str
    dispatch_strategy: str
    progress: float
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class SimulationStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    progress: float
    error_message: str | None

    model_config = {"from_attributes": True}


class EconomicsResponse(BaseModel):
    npc: float
    lcoe: float
    irr: float | None
    payback_years: float | None
    renewable_fraction: float
    co2_emissions_kg: float
    cost_breakdown: dict

    model_config = {"from_attributes": True}


class ComparisonRequest(BaseModel):
    simulation_ids: list[uuid.UUID] = Field(min_length=2, max_length=10)
