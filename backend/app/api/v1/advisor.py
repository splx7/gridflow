import uuid
import zlib

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.load_profile import LoadProfile
from app.models.project import Project
from app.models.simulation import Simulation, SimulationResult
from app.models.user import User
from app.schemas.advisor import (
    AdvisorRequest,
    AdvisorResponse,
    SystemEvaluateRequest,
    SystemHealthResponse,
)
from app.schemas.bess_sizing import BESSRecommendationResponse

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


@router.get(
    "/{project_id}/advisor/bess-recommendation",
    response_model=BESSRecommendationResponse,
)
async def get_bess_recommendation(
    project_id: uuid.UUID,
    simulation_id: uuid.UUID = Query(..., description="Simulation ID to analyze"),
    max_unmet_fraction: float = Query(0.05, ge=0.0, le=1.0, description="Max unmet load fraction target"),
    min_re_fraction: float = Query(0.80, ge=0.0, le=1.0, description="Min renewable fraction target"),
    max_capacity_kwh: float | None = Query(None, gt=0, description="Upper limit for battery capacity"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recommend BESS sizing based on completed simulation results.

    Analyzes the hourly surplus/deficit from an existing simulation to
    determine optimal battery capacity and power rating that meets the
    specified unmet load and renewable fraction targets.
    """
    await _get_user_project(project_id, user, db)

    # Load simulation with results
    sim_result = await db.execute(
        select(Simulation)
        .where(
            Simulation.id == simulation_id,
            Simulation.project_id == project_id,
        )
        .options(selectinload(Simulation.results))
    )
    simulation = sim_result.scalar_one_or_none()
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )
    if simulation.status != "completed" or simulation.results is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Simulation must be completed with results to generate BESS recommendation",
        )

    sr = simulation.results

    # Decompress time-series data
    def _decompress_ts(data: bytes | None) -> np.ndarray:
        if data is None:
            return np.zeros(8760, dtype=np.float64)
        return np.frombuffer(zlib.decompress(data), dtype=np.float64)

    load_kw = _decompress_ts(sr.ts_load)
    pv_kw = _decompress_ts(sr.ts_pv_output)
    wind_kw = _decompress_ts(sr.ts_wind_output)
    gen_kw = _decompress_ts(sr.ts_generator_output)
    grid_import_kw = _decompress_ts(sr.ts_grid_import)

    re_output_kw = pv_kw + wind_kw

    from engine.advisor.bess_sizing import recommend_bess

    bess_result = recommend_bess(
        load_kw=load_kw,
        re_output_kw=re_output_kw,
        generator_kw=gen_kw,
        grid_import_kw=grid_import_kw,
        max_unmet_fraction=max_unmet_fraction,
        min_re_fraction=min_re_fraction,
        max_capacity_kwh=max_capacity_kwh,
    )

    return BESSRecommendationResponse(**bess_result.to_dict())
