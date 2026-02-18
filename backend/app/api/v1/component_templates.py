"""Component templates library API."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter()

_TEMPLATES_PATH = Path(__file__).parent.parent.parent.parent / "engine" / "data" / "component_templates.json"
_cache: dict | None = None


def _load_templates() -> dict:
    global _cache
    if _cache is None:
        with open(_TEMPLATES_PATH) as f:
            _cache = json.load(f)
    return _cache


@router.get("/component-templates")
async def list_component_templates(
    component_type: str | None = Query(None, description="Filter by component type (solar_pv, battery, etc.)"),
):
    """Return pre-configured component templates from the built-in library."""
    templates = _load_templates()
    if component_type:
        return templates.get(component_type, [])
    return templates
