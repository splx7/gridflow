import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.project import Project
from app.models.component import Component
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter()


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new microgrid project with location and economic parameters.",
)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(user_id=user.id, **body.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get(
    "/",
    response_model=list[ProjectResponse],
    summary="List projects",
    description="Return all projects owned by the current user, ordered by last update.",
)
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.user_id == user.id).order_by(Project.updated_at.desc())
    )
    return result.scalars().all()


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project",
    description="Retrieve a single project by ID.",
)
async def get_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project",
    description="Partially update a project's name, location, or economic parameters.",
)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Permanently delete a project and all associated data.",
)
async def delete_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    await db.delete(project)
    await db.commit()


@router.post(
    "/{project_id}/duplicate",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate project",
    description="Deep-copy a project and its components. Simulations are not copied.",
)
async def duplicate_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    new_project = Project(
        user_id=user.id,
        name=f"{original.name} (copy)",
        description=original.description,
        latitude=original.latitude,
        longitude=original.longitude,
        lifetime_years=original.lifetime_years,
        discount_rate=original.discount_rate,
        currency=original.currency,
    )
    db.add(new_project)
    await db.flush()

    # Copy components
    comp_result = await db.execute(
        select(Component).where(Component.project_id == project_id)
    )
    for comp in comp_result.scalars().all():
        new_comp = Component(
            project_id=new_project.id,
            component_type=comp.component_type,
            name=comp.name,
            config=comp.config,
        )
        db.add(new_comp)

    await db.commit()
    await db.refresh(new_project)
    return new_project


@router.get(
    "/{project_id}/export",
    summary="Export project as JSON",
    description="Export a project's configuration and components as a downloadable JSON bundle.",
)
async def export_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    comp_result = await db.execute(
        select(Component).where(Component.project_id == project_id)
    )
    components = [
        {
            "component_type": c.component_type,
            "name": c.name,
            "config": c.config,
        }
        for c in comp_result.scalars().all()
    ]

    bundle = {
        "version": "1.0",
        "project": {
            "name": project.name,
            "description": project.description,
            "latitude": project.latitude,
            "longitude": project.longitude,
            "lifetime_years": project.lifetime_years,
            "discount_rate": project.discount_rate,
            "currency": project.currency,
        },
        "components": components,
    }
    return JSONResponse(content=bundle)


@router.post(
    "/import",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import project from JSON",
    description="Create a new project from a previously exported JSON bundle, including all components.",
)
async def import_project(
    bundle: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj_data = bundle.get("project")
    if not proj_data or not proj_data.get("name"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bundle: missing project data",
        )

    new_project = Project(
        user_id=user.id,
        name=proj_data["name"],
        description=proj_data.get("description"),
        latitude=proj_data.get("latitude", 0),
        longitude=proj_data.get("longitude", 0),
        lifetime_years=proj_data.get("lifetime_years", 25),
        discount_rate=proj_data.get("discount_rate", 0.08),
        currency=proj_data.get("currency", "USD"),
    )
    db.add(new_project)
    await db.flush()

    for comp_data in bundle.get("components", []):
        comp = Component(
            project_id=new_project.id,
            component_type=comp_data["component_type"],
            name=comp_data.get("name", comp_data["component_type"]),
            config=comp_data.get("config", {}),
        )
        db.add(comp)

    await db.commit()
    await db.refresh(new_project)
    return new_project
