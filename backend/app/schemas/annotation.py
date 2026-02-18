"""Pydantic schemas for annotations."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AnnotationCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    annotation_type: str = Field(default="note", pattern="^(note|decision|issue)$")
    metadata_json: dict | None = None


class AnnotationUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=5000)
    annotation_type: str | None = Field(default=None, pattern="^(note|decision|issue)$")
    metadata_json: dict | None = None


class AnnotationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    author_id: uuid.UUID | None
    text: str
    annotation_type: str
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
