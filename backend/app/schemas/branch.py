import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BranchCreate(BaseModel):
    from_bus_id: uuid.UUID
    to_bus_id: uuid.UUID
    branch_type: str = Field(pattern="^(cable|line|transformer)$")
    name: str = Field(max_length=255)
    config: dict = Field(default_factory=dict)


class BranchUpdate(BaseModel):
    from_bus_id: uuid.UUID | None = None
    to_bus_id: uuid.UUID | None = None
    branch_type: str | None = Field(default=None, pattern="^(cable|line|transformer)$")
    name: str | None = Field(default=None, max_length=255)
    config: dict | None = None


class BranchResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    from_bus_id: uuid.UUID
    to_bus_id: uuid.UUID
    branch_type: str
    name: str
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
