import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.bus import Bus
from app.models.load_allocation import LoadAllocation
from app.models.load_profile import LoadProfile
from app.models.project import Project
from app.models.user import User
from app.schemas.load_allocation import (
    LoadAllocationCreate,
    LoadAllocationResponse,
    LoadAllocationUpdate,
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
    "/{project_id}/load-allocations",
    response_model=LoadAllocationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_load_allocation(
    project_id: uuid.UUID,
    body: LoadAllocationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)

    # Validate bus belongs to project
    bus = await db.execute(
        select(Bus).where(Bus.id == body.bus_id, Bus.project_id == project_id)
    )
    if not bus.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bus not found in project")

    # Auto-select load profile if not provided
    load_profile_id = body.load_profile_id
    if load_profile_id is None:
        lp_result = await db.execute(
            select(LoadProfile).where(LoadProfile.project_id == project_id)
            .order_by(LoadProfile.created_at.desc()).limit(1)
        )
        lp = lp_result.scalar_one_or_none()
        if not lp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No load profiles in project. Create one first or provide load_profile_id.",
            )
        load_profile_id = lp.id
    else:
        # Validate load profile belongs to project
        lp = await db.execute(
            select(LoadProfile).where(
                LoadProfile.id == load_profile_id, LoadProfile.project_id == project_id
            )
        )
        if not lp.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Load profile not found in project"
            )

    alloc_data = body.model_dump()
    alloc_data["load_profile_id"] = load_profile_id
    allocation = LoadAllocation(project_id=project_id, **alloc_data)
    db.add(allocation)
    await db.commit()
    await db.refresh(allocation)
    return allocation


@router.get("/{project_id}/load-allocations", response_model=list[LoadAllocationResponse])
async def list_load_allocations(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(LoadAllocation).where(LoadAllocation.project_id == project_id)
    )
    return result.scalars().all()


@router.patch(
    "/{project_id}/load-allocations/{allocation_id}",
    response_model=LoadAllocationResponse,
)
async def update_load_allocation(
    project_id: uuid.UUID,
    allocation_id: uuid.UUID,
    body: LoadAllocationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(LoadAllocation).where(
            LoadAllocation.id == allocation_id, LoadAllocation.project_id == project_id
        )
    )
    allocation = result.scalar_one_or_none()
    if not allocation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load allocation not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(allocation, field, value)

    await db.commit()
    await db.refresh(allocation)
    return allocation


@router.delete(
    "/{project_id}/load-allocations/{allocation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_load_allocation(
    project_id: uuid.UUID,
    allocation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(LoadAllocation).where(
            LoadAllocation.id == allocation_id, LoadAllocation.project_id == project_id
        )
    )
    allocation = result.scalar_one_or_none()
    if not allocation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load allocation not found")

    await db.delete(allocation)
    await db.commit()
