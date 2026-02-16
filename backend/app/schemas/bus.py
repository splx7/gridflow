import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BusCreate(BaseModel):
    name: str = Field(max_length=255)
    bus_type: str = Field(default="pq", pattern="^(slack|pv|pq)$")
    nominal_voltage_kv: float = Field(default=0.4, gt=0)
    base_mva: float = Field(default=1.0, gt=0)
    x_position: float | None = None
    y_position: float | None = None
    config: dict = Field(default_factory=dict)


class BusUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    bus_type: str | None = Field(default=None, pattern="^(slack|pv|pq)$")
    nominal_voltage_kv: float | None = Field(default=None, gt=0)
    base_mva: float | None = Field(default=None, gt=0)
    x_position: float | None = None
    y_position: float | None = None
    config: dict | None = None


class BusResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    bus_type: str
    nominal_voltage_kv: float
    base_mva: float
    x_position: float | None
    y_position: float | None
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
