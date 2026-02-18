from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.project import Project
from app.models.simulation import Simulation, SimulationResult
from app.models.user import User
from app.schemas.simulation import ComparisonRequest, ScoringRequest

from engine.economics.scoring import score_scenarios

router = APIRouter()


@router.post(
    "/",
    summary="Compare simulations",
    description="Compare economic and performance metrics across multiple completed simulations.",
)
async def compare_simulations(
    body: ComparisonRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = []
    for sim_id in body.simulation_ids:
        result = await db.execute(
            select(SimulationResult)
            .join(Simulation)
            .join(Project)
            .where(SimulationResult.simulation_id == sim_id, Project.user_id == user.id)
        )
        sr = result.scalar_one_or_none()
        if not sr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Results not found for simulation {sim_id}",
            )

        sim_result = await db.execute(select(Simulation).where(Simulation.id == sim_id))
        sim = sim_result.scalar_one()

        results.append({
            "simulation_id": str(sim_id),
            "simulation_name": sim.name,
            "dispatch_strategy": sim.dispatch_strategy,
            "npc": sr.npc,
            "lcoe": sr.lcoe,
            "irr": sr.irr,
            "payback_years": sr.payback_years,
            "renewable_fraction": sr.renewable_fraction,
            "co2_emissions_kg": sr.co2_emissions_kg,
            "cost_breakdown": sr.cost_breakdown,
        })

    return {"comparisons": results}


@router.post(
    "/score",
    summary="Score and rank simulations",
    description="Apply weighted multi-criteria scoring to rank simulations by composite score.",
)
async def score_simulations_endpoint(
    body: ScoringRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scenarios = []
    for sim_id in body.simulation_ids:
        result = await db.execute(
            select(SimulationResult)
            .join(Simulation)
            .join(Project)
            .where(SimulationResult.simulation_id == sim_id, Project.user_id == user.id)
        )
        sr = result.scalar_one_or_none()
        if not sr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Results not found for simulation {sim_id}",
            )

        sim_result = await db.execute(select(Simulation).where(Simulation.id == sim_id))
        sim = sim_result.scalar_one()

        scenarios.append({
            "simulation_id": str(sim_id),
            "simulation_name": sim.name,
            "npc": sr.npc,
            "lcoe": sr.lcoe,
            "irr": sr.irr,
            "payback_years": sr.payback_years,
            "renewable_fraction": sr.renewable_fraction,
            "co2_emissions_kg": sr.co2_emissions_kg,
        })

    scored = score_scenarios(scenarios, weights=body.weights)
    return {"scored": scored}
