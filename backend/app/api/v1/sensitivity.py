import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rate_limit import sensitivity_limiter
from app.models.database import get_db
from app.models.project import Project
from app.models.simulation import Simulation, SimulationResult
from app.models.user import User

router = APIRouter()


class SensitivityVariable(BaseModel):
    name: str
    param_path: str
    range: list[float] = Field(min_length=2, max_length=2)
    points: int = Field(default=9, ge=2, le=25)


class SensitivityRequest(BaseModel):
    variables: list[SensitivityVariable] = Field(min_length=1, max_length=10)


@router.post(
    "/simulations/{simulation_id}/sensitivity",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run sensitivity analysis",
    description="Queue an OAT sensitivity sweep for a completed simulation. Returns a Celery task ID for polling.",
)
async def run_sensitivity(
    simulation_id: uuid.UUID,
    body: SensitivityRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sensitivity_limiter.check(request)
    result = await db.execute(
        select(Simulation)
        .join(Project)
        .where(Simulation.id == simulation_id, Project.user_id == user.id)
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )
    if sim.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Simulation must be completed before running sensitivity analysis",
        )

    from app.worker.sensitivity_task import run_sensitivity as sensitivity_task

    variables_raw = [v.model_dump() for v in body.variables]
    task = sensitivity_task.delay(str(simulation_id), variables_raw)

    return {"task_id": task.id, "status": "queued"}


@router.get(
    "/simulations/{simulation_id}/sensitivity",
    summary="Get sensitivity results",
    description="Retrieve the sensitivity analysis results (spider/tornado data) for a simulation.",
)
async def get_sensitivity_results(
    simulation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimulationResult)
        .join(Simulation)
        .join(Project)
        .where(
            SimulationResult.simulation_id == simulation_id,
            Project.user_id == user.id,
        )
    )
    sr = result.scalar_one_or_none()
    if not sr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation results not found",
        )

    if not sr.sensitivity_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sensitivity results — run analysis first",
        )

    return sr.sensitivity_results
