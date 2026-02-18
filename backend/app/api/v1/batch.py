"""Batch simulation / parametric sweep endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.project import Project
from app.models.batch import BatchRun
from app.models.simulation import Simulation, SimulationResult
from app.models.user import User
from app.schemas.batch import BatchRequest, BatchStatusResponse

router = APIRouter()


@router.post(
    "/{project_id}/batch",
    summary="Create batch sweep",
    description="Launch a parametric sweep that creates multiple simulations varying specified parameters.",
    status_code=status.HTTP_201_CREATED,
)
async def create_batch(
    project_id: uuid.UUID,
    body: BatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Calculate grid size
    import itertools
    import numpy as np

    param_values = {}
    for sp in body.sweep_params:
        vals = list(np.arange(sp.start, sp.end + sp.step * 0.5, sp.step))
        param_values[sp.param_path] = vals

    grid = list(itertools.product(*param_values.values()))
    total_runs = len(grid)

    if total_runs > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parameter grid too large ({total_runs} combinations). Maximum is 100.",
        )

    # Create batch run record
    batch = BatchRun(
        project_id=project_id,
        name=body.name,
        status="pending",
        sweep_config={
            "dispatch_strategy": body.dispatch_strategy,
            "weather_dataset_id": str(body.weather_dataset_id),
            "load_profile_id": str(body.load_profile_id),
            "sweep_params": [sp.model_dump() for sp in body.sweep_params],
        },
        total_runs=total_runs,
        completed_runs=0,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    # Launch Celery task
    from app.worker.batch_task import run_batch_sweep

    task = run_batch_sweep.delay(str(batch.id))
    batch.celery_task_id = task.id
    batch.status = "running"
    await db.commit()

    return {
        "id": str(batch.id),
        "name": batch.name,
        "status": batch.status,
        "total_runs": total_runs,
        "task_id": task.id,
    }


@router.get(
    "/{project_id}/batch",
    summary="List batch runs",
    description="List all batch runs for a project.",
)
async def list_batches(
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
        select(BatchRun)
        .where(BatchRun.project_id == project_id)
        .order_by(BatchRun.created_at.desc())
    )
    batches = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "name": b.name,
            "status": b.status,
            "total_runs": b.total_runs,
            "completed_runs": b.completed_runs,
            "error_message": b.error_message,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "completed_at": b.completed_at.isoformat() if b.completed_at else None,
        }
        for b in batches
    ]


@router.get(
    "/{project_id}/batch/{batch_id}",
    summary="Batch run status",
    description="Get status and results of a batch run.",
)
async def get_batch_status(
    project_id: uuid.UUID,
    batch_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BatchRun)
        .join(Project)
        .where(
            BatchRun.id == batch_id,
            BatchRun.project_id == project_id,
            Project.user_id == user.id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch run not found")

    # Fetch associated simulation results
    sim_result = await db.execute(
        select(Simulation, SimulationResult)
        .outerjoin(SimulationResult, Simulation.id == SimulationResult.simulation_id)
        .where(Simulation.batch_run_id == batch_id)
        .order_by(Simulation.name)
    )
    entries = []
    for sim, sr in sim_result.all():
        entry = {
            "simulation_id": str(sim.id),
            "simulation_name": sim.name,
            "status": sim.status,
            "params": sim.config_snapshot.get("sweep_params", {}),
        }
        if sr:
            entry.update({
                "npc": sr.npc,
                "lcoe": sr.lcoe,
                "irr": sr.irr,
                "payback_years": sr.payback_years,
                "renewable_fraction": sr.renewable_fraction,
                "co2_emissions_kg": sr.co2_emissions_kg,
            })
        entries.append(entry)

    return {
        "id": str(batch.id),
        "name": batch.name,
        "status": batch.status,
        "total_runs": batch.total_runs,
        "completed_runs": batch.completed_runs,
        "error_message": batch.error_message,
        "results_summary": batch.results_summary,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "results": entries,
    }
