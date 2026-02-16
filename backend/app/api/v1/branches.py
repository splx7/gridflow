import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.branch import Branch
from app.models.bus import Bus
from app.models.project import Project
from app.models.user import User
from app.schemas.branch import BranchCreate, BranchResponse, BranchUpdate

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


async def _validate_bus(bus_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(Bus.id).where(Bus.id == bus_id, Bus.project_id == project_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bus {bus_id} not found in project",
        )


@router.post(
    "/{project_id}/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_branch(
    project_id: uuid.UUID,
    body: BranchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    await _validate_bus(body.from_bus_id, project_id, db)
    await _validate_bus(body.to_bus_id, project_id, db)

    branch = Branch(project_id=project_id, **body.model_dump())
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return branch


@router.get("/{project_id}/branches", response_model=list[BranchResponse])
async def list_branches(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Branch).where(Branch.project_id == project_id)
    )
    return result.scalars().all()


@router.patch("/{project_id}/branches/{branch_id}", response_model=BranchResponse)
async def update_branch(
    project_id: uuid.UUID,
    branch_id: uuid.UUID,
    body: BranchUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id, Branch.project_id == project_id)
    )
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    updates = body.model_dump(exclude_unset=True)
    if "from_bus_id" in updates:
        await _validate_bus(updates["from_bus_id"], project_id, db)
    if "to_bus_id" in updates:
        await _validate_bus(updates["to_bus_id"], project_id, db)

    for field, value in updates.items():
        setattr(branch, field, value)

    await db.commit()
    await db.refresh(branch)
    return branch


@router.delete("/{project_id}/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(
    project_id: uuid.UUID,
    branch_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id, Branch.project_id == project_id)
    )
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    await db.delete(branch)
    await db.commit()
