"""Pydantic schemas for batch/parametric sweep simulations."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SweepParam(BaseModel):
    name: str = Field(description="Display name for the parameter")
    param_path: str = Field(description="Dot-separated config path, e.g. 'solar_pv.capacity_kw'")
    start: float
    end: float
    step: float = Field(gt=0)


class BatchRequest(BaseModel):
    name: str = Field(max_length=255)
    dispatch_strategy: str = Field(default="load_following")
    weather_dataset_id: uuid.UUID
    load_profile_id: uuid.UUID
    sweep_params: list[SweepParam] = Field(min_length=1, max_length=3)


class BatchStatusResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    total_runs: int
    completed_runs: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class BatchResultEntry(BaseModel):
    simulation_id: uuid.UUID
    simulation_name: str
    params: dict[str, float]
    npc: float | None
    lcoe: float | None
    irr: float | None
    payback_years: float | None
    renewable_fraction: float | None
    co2_emissions_kg: float | None
