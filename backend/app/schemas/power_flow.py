from typing import Any

from pydantic import BaseModel, Field


class PowerFlowRequest(BaseModel):
    mode: str = Field(default="snapshot", pattern="^(snapshot|hourly)$")
    snapshot_hours: list[int] | None = None
    load_profile_id: str | None = None
    weather_dataset_id: str | None = None


class BranchFlowSummary(BaseModel):
    from_kw: float
    to_kw: float
    loss_kw: float
    vd_pct: float
    loading_pct: float


class VoltageViolation(BaseModel):
    bus_id: str
    bus_name: str
    hour: int | None = None
    voltage_pu: float
    limit: str  # "low" or "high"


class ThermalViolation(BaseModel):
    branch_id: str
    branch_name: str
    hour: int | None = None
    loading_pct: float
    rating_mva: float


class ShortCircuitBus(BaseModel):
    i_sc_ka: float
    s_sc_mva: float


class PowerFlowSummary(BaseModel):
    min_voltage_pu: float
    max_voltage_pu: float
    worst_voltage_bus: str
    max_branch_loading_pct: float
    total_losses_pct: float
    total_losses_kw: float


class RecommendationAction(BaseModel):
    type: str
    target_id: str | None = None
    target_name: str
    field: str
    old_value: Any = None
    new_value: Any = None
    description: str
    cable_params: dict[str, Any] | None = None


class Recommendation(BaseModel):
    level: str
    code: str
    message: str
    suggestion: str
    action: RecommendationAction | None = None


class PowerFlowResponse(BaseModel):
    converged: bool
    iterations: int
    bus_voltages: dict[str, float]  # bus_name -> voltage_pu
    branch_flows: dict[str, BranchFlowSummary]  # branch_name -> flow
    voltage_violations: list[VoltageViolation]
    thermal_violations: list[ThermalViolation]
    short_circuit: dict[str, ShortCircuitBus]  # bus_name -> SC result
    summary: PowerFlowSummary
    recommendations: list[Recommendation] = []
