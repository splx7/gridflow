import math
import uuid
import zlib

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rate_limit import simulation_limiter
from app.models.database import get_db
from app.models.project import Project
from app.models.simulation import Simulation, SimulationResult
from app.models.user import User
from app.schemas.simulation import (
    EconomicsResponse,
    SimulationCreate,
    SimulationResponse,
    SimulationStatusResponse,
)

router = APIRouter()


def _decompress_timeseries(data: bytes | None) -> list[float] | None:
    if data is None:
        return None
    arr = np.frombuffer(zlib.decompress(data), dtype=np.float64)
    return [0.0 if (math.isinf(v) or math.isnan(v)) else v for v in arr.tolist()]


def _safe_float(value: float | None) -> float | None:
    """Convert inf/nan to None for JSON-safe serialization."""
    if value is None:
        return None
    if math.isinf(value) or math.isnan(value):
        return None
    return value


@router.post(
    "/projects/{project_id}/simulations",
    response_model=SimulationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run simulation",
    description="Create a new simulation for a project and dispatch the Celery task for execution.",
)
async def create_simulation(
    project_id: uuid.UUID,
    body: SimulationCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    simulation_limiter.check(request)
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    simulation = Simulation(
        project_id=project_id,
        name=body.name,
        dispatch_strategy=body.dispatch_strategy,
        config_snapshot={
            "weather_dataset_id": str(body.weather_dataset_id),
            "load_profile_id": str(body.load_profile_id),
        },
    )
    db.add(simulation)
    await db.commit()
    await db.refresh(simulation)

    # Dispatch celery task
    from app.worker.tasks import run_simulation

    task = run_simulation.delay(str(simulation.id))
    simulation.celery_task_id = task.id
    await db.commit()

    return simulation


@router.get(
    "/projects/{project_id}/simulations",
    response_model=list[SimulationResponse],
    summary="List simulations",
    description="Return all simulations for a project, ordered by creation date descending.",
)
async def list_simulations(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await db.execute(
        select(Simulation)
        .where(Simulation.project_id == project_id)
        .order_by(Simulation.created_at.desc())
    )
    return result.scalars().all()


@router.delete(
    "/projects/{project_id}/simulations/{simulation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete simulation",
    description="Delete a simulation and its associated results.",
)
async def delete_simulation(
    project_id: uuid.UUID,
    simulation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Simulation)
        .join(Project)
        .where(
            Simulation.id == simulation_id,
            Simulation.project_id == project_id,
            Project.user_id == user.id,
        )
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    # Delete associated results first
    result = await db.execute(
        select(SimulationResult).where(SimulationResult.simulation_id == simulation_id)
    )
    for sr in result.scalars().all():
        await db.delete(sr)

    await db.delete(sim)
    await db.commit()


@router.get(
    "/simulations/{simulation_id}/status",
    response_model=SimulationStatusResponse,
    summary="Get simulation status",
    description="Check the current status of a simulation (pending, running, completed, or failed).",
)
async def get_simulation_status(
    simulation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Simulation)
        .join(Project)
        .where(Simulation.id == simulation_id, Project.user_id == user.id)
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    return sim


@router.get(
    "/simulations/{simulation_id}/results/economics",
    response_model=EconomicsResponse,
    summary="Get economic results",
    description="Return NPC, LCOE, IRR, payback period, and cost breakdown for a completed simulation.",
)
async def get_economics(
    simulation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimulationResult)
        .join(Simulation)
        .join(Project)
        .where(SimulationResult.simulation_id == simulation_id, Project.user_id == user.id)
    )
    sr = result.scalar_one_or_none()
    if not sr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Results not found")

    # Sanitize inf/nan values that break JSON serialization
    return {
        "npc": _safe_float(sr.npc) or 0.0,
        "lcoe": _safe_float(sr.lcoe) or 0.0,
        "irr": _safe_float(sr.irr),
        "payback_years": _safe_float(sr.payback_years),
        "renewable_fraction": _safe_float(sr.renewable_fraction) or 0.0,
        "co2_emissions_kg": _safe_float(sr.co2_emissions_kg) or 0.0,
        "cost_breakdown": {
            k: (_safe_float(v) or 0.0) if isinstance(v, float) else v
            for k, v in (sr.cost_breakdown or {}).items()
        },
    }


@router.get(
    "/simulations/{simulation_id}/results/timeseries",
    summary="Get time-series results",
    description="Return 8760-hour time-series arrays for load, PV, wind, battery, generator, and grid flows.",
)
async def get_timeseries(
    simulation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimulationResult)
        .join(Simulation)
        .join(Project)
        .where(SimulationResult.simulation_id == simulation_id, Project.user_id == user.id)
    )
    sr = result.scalar_one_or_none()
    if not sr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Results not found")

    return {
        "load": _decompress_timeseries(sr.ts_load),
        "pv_output": _decompress_timeseries(sr.ts_pv_output),
        "wind_output": _decompress_timeseries(sr.ts_wind_output),
        "battery_soc": _decompress_timeseries(sr.ts_battery_soc),
        "battery_power": _decompress_timeseries(sr.ts_battery_power),
        "generator_output": _decompress_timeseries(sr.ts_generator_output),
        "grid_import": _decompress_timeseries(sr.ts_grid_import),
        "grid_export": _decompress_timeseries(sr.ts_grid_export),
        "excess": _decompress_timeseries(sr.ts_excess),
        "unmet": _decompress_timeseries(sr.ts_unmet),
    }


@router.get(
    "/simulations/{simulation_id}/results/network",
    summary="Get network results",
    description="Return power flow summary and bus voltage time-series for a multi-bus simulation.",
)
async def get_network_results(
    simulation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimulationResult)
        .join(Simulation)
        .join(Project)
        .where(SimulationResult.simulation_id == simulation_id, Project.user_id == user.id)
    )
    sr = result.scalar_one_or_none()
    if not sr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Results not found")

    if not sr.power_flow_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No network results — simulation was run in single_bus mode",
        )

    return {
        "power_flow_summary": sr.power_flow_summary,
        "ts_bus_voltages": sr.ts_bus_voltages,
    }


@router.get(
    "/admin/celery-status",
    summary="Celery worker status",
    description="Return active, reserved, and scheduled tasks from all Celery workers. Requires authentication.",
)
async def celery_status(
    user: User = Depends(get_current_user),
):
    from app.worker.celery_app import celery_app

    inspect = celery_app.control.inspect(timeout=2.0)
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    scheduled = inspect.scheduled() or {}

    workers = {}
    for worker_name in set(list(active) + list(reserved) + list(scheduled)):
        workers[worker_name] = {
            "active": len(active.get(worker_name, [])),
            "reserved": len(reserved.get(worker_name, [])),
            "scheduled": len(scheduled.get(worker_name, [])),
        }

    return {
        "workers": workers,
        "total_active": sum(w["active"] for w in workers.values()),
        "total_reserved": sum(w["reserved"] for w in workers.values()),
        "worker_count": len(workers),
    }
