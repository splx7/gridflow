import uuid
import zlib

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
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
    return np.frombuffer(zlib.decompress(data), dtype=np.float64).tolist()


@router.post(
    "/projects/{project_id}/simulations",
    response_model=SimulationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_simulation(
    project_id: uuid.UUID,
    body: SimulationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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


@router.get("/projects/{project_id}/simulations", response_model=list[SimulationResponse])
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


@router.get("/simulations/{simulation_id}/status", response_model=SimulationStatusResponse)
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


@router.get("/simulations/{simulation_id}/results/economics", response_model=EconomicsResponse)
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
    return sr


@router.get("/simulations/{simulation_id}/results/timeseries")
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
