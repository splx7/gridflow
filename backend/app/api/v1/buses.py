import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.bus import Bus
from app.models.project import Project
from app.models.user import User
from app.schemas.bus import BusCreate, BusResponse, BusUpdate

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
    "/{project_id}/buses",
    response_model=BusResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bus(
    project_id: uuid.UUID,
    body: BusCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    bus = Bus(project_id=project_id, **body.model_dump())
    db.add(bus)
    await db.commit()
    await db.refresh(bus)
    return bus


@router.get("/{project_id}/buses", response_model=list[BusResponse])
async def list_buses(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(select(Bus).where(Bus.project_id == project_id))
    return result.scalars().all()


@router.get("/{project_id}/buses/{bus_id}", response_model=BusResponse)
async def get_bus(
    project_id: uuid.UUID,
    bus_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Bus).where(Bus.id == bus_id, Bus.project_id == project_id)
    )
    bus = result.scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bus not found")
    return bus


@router.patch("/{project_id}/buses/{bus_id}", response_model=BusResponse)
async def update_bus(
    project_id: uuid.UUID,
    bus_id: uuid.UUID,
    body: BusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Bus).where(Bus.id == bus_id, Bus.project_id == project_id)
    )
    bus = result.scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bus not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(bus, field, value)

    await db.commit()
    await db.refresh(bus)
    return bus


@router.delete("/{project_id}/buses/{bus_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bus(
    project_id: uuid.UUID,
    bus_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Bus).where(Bus.id == bus_id, Bus.project_id == project_id)
    )
    bus = result.scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bus not found")

    await db.delete(bus)
    await db.commit()
