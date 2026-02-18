"""Project templates API."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "engine" / "data" / "project_templates"
_cache: list[dict] | None = None


def _load_templates() -> list[dict]:
    global _cache
    if _cache is None:
        _cache = []
        if _TEMPLATES_DIR.exists():
            for f in sorted(_TEMPLATES_DIR.glob("*.json")):
                with open(f) as fh:
                    _cache.append(json.load(fh))
    return _cache


@router.get(
    "/project-templates",
    summary="List project templates",
    description="Return all available project templates with summaries, categories, and component counts.",
)
async def list_project_templates():
    templates = _load_templates()
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "category": t.get("category", "general"),
            "component_count": len(t.get("components", [])),
            "location": {
                "latitude": t["project"]["latitude"],
                "longitude": t["project"]["longitude"],
            },
        }
        for t in templates
    ]


@router.get(
    "/project-templates/{template_id}",
    summary="Get project template",
    description="Return full template details including project config and component definitions.",
)
async def get_project_template(template_id: str):
    templates = _load_templates()
    for t in templates:
        if t["id"] == template_id:
            return t
    raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
