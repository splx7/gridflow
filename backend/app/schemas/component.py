import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# Component config schemas (JSONB validation)
class SolarPVConfig(BaseModel):
    type: Literal["solar_pv"] = "solar_pv"
    capacity_kwp: float = Field(gt=0)
    tilt_deg: float = Field(ge=0, le=90)
    azimuth_deg: float = Field(ge=0, le=360)
    module_type: str = "mono-si"
    inverter_efficiency: float = Field(default=0.96, ge=0, le=1)
    system_losses: float = Field(default=0.14, ge=0, le=1)
    capital_cost_per_kw: float = Field(default=1000, ge=0)
    om_cost_per_kw_year: float = Field(default=15, ge=0)
    lifetime_years: int = Field(default=25, ge=1)
    derating_factor: float = Field(default=0.005, ge=0, le=0.05)


class WindTurbineConfig(BaseModel):
    type: Literal["wind_turbine"] = "wind_turbine"
    rated_power_kw: float = Field(gt=0)
    hub_height_m: float = Field(gt=0)
    rotor_diameter_m: float = Field(gt=0)
    cut_in_speed: float = Field(default=3.0, ge=0)
    cut_out_speed: float = Field(default=25.0, ge=0)
    rated_speed: float = Field(default=12.0, ge=0)
    power_curve: list[list[float]] | None = None  # [[speed, power], ...]
    quantity: int = Field(default=1, ge=1)
    capital_cost_per_kw: float = Field(default=1500, ge=0)
    om_cost_per_kw_year: float = Field(default=30, ge=0)
    lifetime_years: int = Field(default=20, ge=1)


class BatteryConfig(BaseModel):
    type: Literal["battery"] = "battery"
    capacity_kwh: float = Field(gt=0)
    max_charge_rate_kw: float = Field(gt=0)
    max_discharge_rate_kw: float = Field(gt=0)
    round_trip_efficiency: float = Field(default=0.90, ge=0, le=1)
    min_soc: float = Field(default=0.20, ge=0, le=1)
    max_soc: float = Field(default=1.0, ge=0, le=1)
    initial_soc: float = Field(default=0.50, ge=0, le=1)
    chemistry: str = "nmc"
    cycle_life: int = Field(default=5000, ge=100)
    capital_cost_per_kwh: float = Field(default=300, ge=0)
    replacement_cost_per_kwh: float = Field(default=200, ge=0)
    om_cost_per_kwh_year: float = Field(default=5, ge=0)
    lifetime_years: int = Field(default=10, ge=1)


class DieselGeneratorConfig(BaseModel):
    type: Literal["diesel_generator"] = "diesel_generator"
    rated_power_kw: float = Field(gt=0)
    min_load_ratio: float = Field(default=0.25, ge=0, le=1)
    fuel_curve_a0: float = Field(default=0.246, ge=0)  # L/hr intercept per kW rated
    fuel_curve_a1: float = Field(default=0.08145, ge=0)  # L/hr slope per kW output
    fuel_price_per_liter: float = Field(default=1.0, ge=0)
    capital_cost_per_kw: float = Field(default=500, ge=0)
    om_cost_per_hour: float = Field(default=2.0, ge=0)
    lifetime_hours: int = Field(default=15000, ge=1000)
    start_cost: float = Field(default=5.0, ge=0)


class GridConnectionConfig(BaseModel):
    type: Literal["grid_connection"] = "grid_connection"
    max_import_kw: float = Field(default=1e6, ge=0)
    max_export_kw: float = Field(default=1e6, ge=0)
    sell_back_enabled: bool = True
    net_metering: bool = False
    buy_rate: float = Field(default=0.12, ge=0)  # $/kWh flat rate
    sell_rate: float = Field(default=0.05, ge=0)  # $/kWh
    demand_charge: float = Field(default=0.0, ge=0)  # $/kW/month
    tou_schedule: dict | None = None  # {period_name: {rate, hours: [0-23], months: [1-12]}}


ComponentConfig = SolarPVConfig | WindTurbineConfig | BatteryConfig | DieselGeneratorConfig | GridConnectionConfig


class ComponentCreate(BaseModel):
    component_type: str
    name: str = Field(max_length=255)
    config: dict


class ComponentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    config: dict | None = None
    bus_id: uuid.UUID | None = None


class ComponentResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    component_type: str
    name: str
    config: dict
    bus_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
