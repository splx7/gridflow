from pydantic import BaseModel, Field


class ContingencyRequest(BaseModel):
    grid_code: str = Field(
        default="iec_default",
        description="Grid code profile: iec_default, fiji, ieee_1547, or 'custom'"
    )
    custom_profile: dict | None = Field(
        default=None,
        description="Custom grid code profile config (used when grid_code='custom')"
    )


class VoltageViolationItem(BaseModel):
    bus_name: str
    bus_index: int
    voltage_pu: float
    limit_type: str
    limit_value: float


class ThermalViolationItem(BaseModel):
    branch_name: str
    branch_index: int
    loading_pct: float
    rating_mva: float
    limit_pct: float


class ContingencyItem(BaseModel):
    branch_name: str
    branch_index: int
    branch_type: str
    passed: bool
    converged: bool
    causes_islanding: bool
    min_voltage_pu: float
    max_voltage_pu: float
    max_loading_pct: float
    voltage_violations: list[VoltageViolationItem]
    thermal_violations: list[ThermalViolationItem]


class ContingencySummary(BaseModel):
    total_contingencies: int
    passed: int
    failed: int
    islanding_cases: int
    worst_voltage_pu: float
    worst_voltage_bus: str
    worst_loading_pct: float
    worst_loading_branch: str
    n1_secure: bool


class ContingencyResponse(BaseModel):
    grid_code: str
    summary: ContingencySummary
    contingencies: list[ContingencyItem]


class GridCodeProfileSummary(BaseModel):
    key: str
    name: str
    standard: str
    voltage_normal: list[float]
    thermal_limit_pct: float
    frequency_nominal_hz: float


class GridCodeListResponse(BaseModel):
    profiles: list[GridCodeProfileSummary]


class GridCodeDetailResponse(BaseModel):
    name: str
    standard: str
    voltage_limits: dict
    thermal_limit_pct: float
    frequency_limits: dict
    fault_level: dict
    power_factor: dict
    reconnection: dict
    max_voltage_unbalance_pct: float
    max_thd_pct: float
    metadata: dict
