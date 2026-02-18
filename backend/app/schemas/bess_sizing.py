from pydantic import BaseModel, Field


class BESSRecommendation(BaseModel):
    capacity_kwh: float
    max_power_kw: float
    max_charge_kw: float
    max_discharge_kw: float


class BESSProjectedPerformance(BaseModel):
    unmet_fraction: float
    re_fraction: float
    shifted_kwh: float


class BESSLoadGenAnalysis(BaseModel):
    annual_load_kwh: float
    annual_re_kwh: float
    annual_surplus_kwh: float
    annual_deficit_kwh: float
    peak_surplus_kw: float
    peak_deficit_kw: float
    max_consecutive_deficit_hours: int


class BESSRecommendationResponse(BaseModel):
    recommendation: BESSRecommendation
    projected_performance: BESSProjectedPerformance
    load_generation_analysis: BESSLoadGenAnalysis
    sizing_notes: list[str]
