import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.component import Component
from app.models.project import Project
from app.models.user import User
from app.schemas.component import ComponentCreate, ComponentResponse, ComponentUpdate

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
    "/{project_id}/components",
    response_model=ComponentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_component(
    project_id: uuid.UUID,
    body: ComponentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    component = Component(project_id=project_id, **body.model_dump())
    db.add(component)
    await db.commit()
    await db.refresh(component)
    return component


@router.get("/{project_id}/components", response_model=list[ComponentResponse])
async def list_components(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Component).where(Component.project_id == project_id)
    )
    return result.scalars().all()


@router.get("/{project_id}/components/{component_id}", response_model=ComponentResponse)
async def get_component(
    project_id: uuid.UUID,
    component_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Component).where(
            Component.id == component_id, Component.project_id == project_id
        )
    )
    component = result.scalar_one_or_none()
    if not component:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")
    return component


@router.patch("/{project_id}/components/{component_id}", response_model=ComponentResponse)
async def update_component(
    project_id: uuid.UUID,
    component_id: uuid.UUID,
    body: ComponentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Component).where(
            Component.id == component_id, Component.project_id == project_id
        )
    )
    component = result.scalar_one_or_none()
    if not component:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(component, field, value)

    await db.commit()
    await db.refresh(component)
    return component


@router.delete(
    "/{project_id}/components/{component_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_component(
    project_id: uuid.UUID,
    component_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(Component).where(
            Component.id == component_id, Component.project_id == project_id
        )
    )
    component = result.scalar_one_or_none()
    if not component:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")

    await db.delete(component)
    await db.commit()
