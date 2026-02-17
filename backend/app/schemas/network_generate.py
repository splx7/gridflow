from pydantic import BaseModel, Field

from app.schemas.bus import BusResponse
from app.schemas.branch import BranchResponse
from app.schemas.load_allocation import LoadAllocationResponse


class AutoGenerateRequest(BaseModel):
    mv_voltage_kv: float = Field(default=11.0, gt=0)
    lv_voltage_kv: float = Field(default=0.4, gt=0)
    cable_material: str = Field(default="Cu", pattern="^(Cu|Al)$")
    cable_length_km: float = Field(default=0.05, gt=0)


class NetworkRecommendation(BaseModel):
    level: str  # info, warning, error
    code: str
    message: str
    suggestion: str


class AutoGenerateResponse(BaseModel):
    buses: list[BusResponse]
    branches: list[BranchResponse]
    load_allocations: list[LoadAllocationResponse]
    recommendations: list[NetworkRecommendation]
