"""CRUD endpoints for project annotations/notes."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.project import Project
from app.models.annotation import Annotation
from app.models.user import User
from app.schemas.annotation import AnnotationCreate, AnnotationUpdate, AnnotationResponse

router = APIRouter()


@router.get(
    "/{project_id}/annotations",
    response_model=list[AnnotationResponse],
    summary="List project annotations",
    description="Get all annotations/notes for a project, newest first.",
)
async def list_annotations(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await db.execute(
        select(Annotation)
        .where(Annotation.project_id == project_id)
        .order_by(Annotation.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/{project_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create annotation",
    description="Add a note, decision, or issue annotation to a project.",
)
async def create_annotation(
    project_id: uuid.UUID,
    body: AnnotationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    annotation = Annotation(
        project_id=project_id,
        author_id=user.id,
        text=body.text,
        annotation_type=body.annotation_type,
        metadata_json=body.metadata_json,
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)
    return annotation


@router.patch(
    "/{project_id}/annotations/{annotation_id}",
    response_model=AnnotationResponse,
    summary="Update annotation",
    description="Update an existing annotation's text or type.",
)
async def update_annotation(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    body: AnnotationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Annotation)
        .join(Project)
        .where(
            Annotation.id == annotation_id,
            Annotation.project_id == project_id,
            Project.user_id == user.id,
        )
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(annotation, field, value)

    await db.commit()
    await db.refresh(annotation)
    return annotation


@router.delete(
    "/{project_id}/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete annotation",
    description="Remove an annotation from a project.",
)
async def delete_annotation(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Annotation)
        .join(Project)
        .where(
            Annotation.id == annotation_id,
            Annotation.project_id == project_id,
            Project.user_id == user.id,
        )
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotation not found")

    await db.delete(annotation)
    await db.commit()
