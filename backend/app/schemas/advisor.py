from pydantic import BaseModel, Field


class GoalWeights(BaseModel):
    cost: int = Field(default=3, ge=1, le=5)
    renewables: int = Field(default=3, ge=1, le=5)
    reliability: int = Field(default=3, ge=1, le=5)
    roi: int = Field(default=3, ge=1, le=5)


class AdvisorRequest(BaseModel):
    load_profile_id: str | None = None
    scenario: str | None = None
    annual_kwh: float | None = Field(default=None, gt=0)
    peak_kw: float | None = Field(default=None, gt=0)
    daytime_fraction: float | None = Field(default=None, ge=0, le=1)
    goals: GoalWeights = Field(default_factory=GoalWeights)
    grid_available: bool = True
    budget_ceiling: float | None = Field(default=None, gt=0)


class ComponentSpecResponse(BaseModel):
    component_type: str
    name: str
    config: dict


class EstimatesResponse(BaseModel):
    estimated_npc: float
    estimated_lcoe: float
    estimated_renewable_fraction: float
    estimated_payback_years: float | None
    estimated_capital_cost: float
    estimated_co2_reduction_pct: float


class GoalScoresResponse(BaseModel):
    cost: float
    renewables: float
    reliability: float
    roi: float


class RecommendationResponse(BaseModel):
    name: str
    description: str
    best_for: str
    components: list[ComponentSpecResponse]
    estimates: EstimatesResponse
    goal_scores: GoalScoresResponse


class LoadSummaryResponse(BaseModel):
    annual_kwh: float
    peak_kw: float
    daytime_fraction: float


class SolarResourceResponse(BaseModel):
    peak_sun_hours: float
    estimated_cf: float


class AdvisorResponse(BaseModel):
    recommendations: list[RecommendationResponse]
    load_summary: LoadSummaryResponse
    solar_resource: SolarResourceResponse


# --- System Evaluate ---

class EvaluateComponentInput(BaseModel):
    component_type: str
    config: dict


class SystemEvaluateRequest(BaseModel):
    components: list[EvaluateComponentInput]
    load_summary: LoadSummaryResponse
    solar_resource: SolarResourceResponse


class WarningResponse(BaseModel):
    level: str
    code: str
    message: str
    detail: str


class SystemHealthResponse(BaseModel):
    estimates: EstimatesResponse
    warnings: list[WarningResponse]
