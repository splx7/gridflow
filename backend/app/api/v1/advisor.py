import uuid
import zlib

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.load_profile import LoadProfile
from app.models.project import Project
from app.models.user import User
from app.schemas.advisor import (
    AdvisorRequest,
    AdvisorResponse,
    SystemEvaluateRequest,
    SystemHealthResponse,
)

from engine.advisor.sizing import (
    GoalWeights,
    SCENARIO_DEFAULTS,
    analyze_load_profile,
    generate_recommendations,
)

router = APIRouter()


async def _get_user_project(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post(
    "/{project_id}/advisor/recommend",
    response_model=AdvisorResponse,
)
async def get_recommendations(
    project_id: uuid.UUID,
    body: AdvisorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(project_id, user, db)

    annual_kwh: float
    peak_kw: float
    daytime_fraction: float

    # Resolve load data: load_profile_id → hourly analysis, or scenario defaults
    if body.load_profile_id:
        result = await db.execute(
            select(LoadProfile).where(
                LoadProfile.id == uuid.UUID(body.load_profile_id),
                LoadProfile.project_id == project_id,
            )
        )
        lp = result.scalar_one_or_none()
        if not lp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Load profile not found",
            )
        hourly_kw = np.frombuffer(zlib.decompress(lp.hourly_kw), dtype=np.float64).tolist()
        annual_kwh, peak_kw, daytime_fraction = analyze_load_profile(hourly_kw)
        # Allow annual_kwh override
        if body.annual_kwh:
            scale = body.annual_kwh / annual_kwh if annual_kwh > 0 else 1
            annual_kwh = body.annual_kwh
            peak_kw *= scale
        if body.peak_kw is not None:
            peak_kw = body.peak_kw
        if body.daytime_fraction is not None:
            daytime_fraction = body.daytime_fraction
    elif body.scenario and body.scenario in SCENARIO_DEFAULTS:
        annual_kwh, peak_kw, daytime_fraction = SCENARIO_DEFAULTS[body.scenario]
        if body.annual_kwh:
            scale = body.annual_kwh / annual_kwh if annual_kwh > 0 else 1
            annual_kwh = body.annual_kwh
            peak_kw *= scale
        if body.peak_kw is not None:
            peak_kw = body.peak_kw
        if body.daytime_fraction is not None:
            daytime_fraction = body.daytime_fraction
    elif body.annual_kwh:
        # No load profile, no scenario — use annual_kwh with generic profile
        annual_kwh = body.annual_kwh
        peak_kw = annual_kwh / 8760 * 3  # assume peak = 3× average
        daytime_fraction = 0.5
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide load_profile_id, scenario, or annual_kwh",
        )

    goals = GoalWeights(
        cost=body.goals.cost,
        renewables=body.goals.renewables,
        reliability=body.goals.reliability,
        roi=body.goals.roi,
    )

    result = generate_recommendations(
        annual_kwh=annual_kwh,
        peak_kw=peak_kw,
        daytime_fraction=daytime_fraction,
        latitude=project.latitude,
        goals=goals,
        grid_available=body.grid_available,
        budget_ceiling=body.budget_ceiling,
    )

    # Convert dataclasses to response dicts
    return AdvisorResponse(
        recommendations=[
            {
                "name": r.name,
                "description": r.description,
                "best_for": r.best_for,
                "components": [
                    {"component_type": c.component_type, "name": c.name, "config": c.config}
                    for c in r.components
                ],
                "estimates": {
                    "estimated_npc": r.estimates.estimated_npc,
                    "estimated_lcoe": r.estimates.estimated_lcoe,
                    "estimated_renewable_fraction": r.estimates.estimated_renewable_fraction,
                    "estimated_payback_years": r.estimates.estimated_payback_years,
                    "estimated_capital_cost": r.estimates.estimated_capital_cost,
                    "estimated_co2_reduction_pct": r.estimates.estimated_co2_reduction_pct,
                },
                "goal_scores": {
                    "cost": r.goal_scores.cost,
                    "renewables": r.goal_scores.renewables,
                    "reliability": r.goal_scores.reliability,
                    "roi": r.goal_scores.roi,
                },
            }
            for r in result.recommendations
        ],
        load_summary={
            "annual_kwh": result.load_summary.annual_kwh,
            "peak_kw": result.load_summary.peak_kw,
            "daytime_fraction": result.load_summary.daytime_fraction,
        },
        solar_resource={
            "peak_sun_hours": result.solar_resource.peak_sun_hours,
            "estimated_cf": result.solar_resource.estimated_cf,
        },
    )


@router.post(
    "/{project_id}/advisor/evaluate",
    response_model=SystemHealthResponse,
)
async def evaluate_system_health(
    project_id: uuid.UUID,
    body: SystemEvaluateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)

    from engine.advisor.evaluator import evaluate_system

    result = evaluate_system(
        components=[
            {"component_type": c.component_type, "config": c.config}
            for c in body.components
        ],
        annual_kwh=body.load_summary.annual_kwh,
        peak_kw=body.load_summary.peak_kw,
        daytime_fraction=body.load_summary.daytime_fraction,
        peak_sun_hours=body.solar_resource.peak_sun_hours,
    )

    return SystemHealthResponse(
        estimates={
            "estimated_npc": result.estimates.estimated_npc,
            "estimated_lcoe": result.estimates.estimated_lcoe,
            "estimated_renewable_fraction": result.estimates.estimated_renewable_fraction,
            "estimated_payback_years": result.estimates.estimated_payback_years,
            "estimated_capital_cost": result.estimates.estimated_capital_cost,
            "estimated_co2_reduction_pct": result.estimates.estimated_co2_reduction_pct,
        },
        warnings=[
            {
                "level": w.level,
                "code": w.code,
                "message": w.message,
                "detail": w.detail,
            }
            for w in result.warnings
        ],
    )
