import uuid
import zlib

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.project import Project
from app.models.load_profile import LoadProfile
from app.models.weather import WeatherDataset
from app.models.user import User
from app.schemas.weather import (
    LoadProfileCreate,
    LoadProfileResponse,
    PVGISRequest,
    WeatherDatasetResponse,
)

router = APIRouter()


def _compress_array(arr: np.ndarray) -> bytes:
    return zlib.compress(arr.astype(np.float64).tobytes())


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
    "/{project_id}/weather/pvgis",
    response_model=WeatherDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def fetch_pvgis(
    project_id: uuid.UUID,
    body: PVGISRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_user_project(project_id, user, db)

    from app.services.weather_service import fetch_pvgis_tmy

    weather_data = await fetch_pvgis_tmy(project.latitude, project.longitude)

    dataset = WeatherDataset(
        project_id=project_id,
        name=body.name,
        source="pvgis",
        ghi=_compress_array(weather_data["ghi"]),
        dni=_compress_array(weather_data["dni"]),
        dhi=_compress_array(weather_data["dhi"]),
        temperature=_compress_array(weather_data["temperature"]),
        wind_speed=_compress_array(weather_data["wind_speed"]),
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.post(
    "/{project_id}/weather/upload",
    response_model=WeatherDatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_weather(
    project_id: uuid.UUID,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)

    from app.services.weather_service import parse_tmy_csv

    content = await file.read()
    weather_data = parse_tmy_csv(content.decode("utf-8"))

    dataset = WeatherDataset(
        project_id=project_id,
        name=file.filename or "Uploaded TMY",
        source="upload",
        ghi=_compress_array(weather_data["ghi"]),
        dni=_compress_array(weather_data["dni"]),
        dhi=_compress_array(weather_data["dhi"]),
        temperature=_compress_array(weather_data["temperature"]),
        wind_speed=_compress_array(weather_data["wind_speed"]),
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get("/{project_id}/weather", response_model=list[WeatherDatasetResponse])
async def list_weather(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(WeatherDataset).where(WeatherDataset.project_id == project_id)
    )
    return result.scalars().all()


# Load profiles
@router.post(
    "/{project_id}/load-profiles",
    response_model=LoadProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_load_profile(
    project_id: uuid.UUID,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)

    content = await file.read()
    lines = content.decode("utf-8").strip().split("\n")
    # Expect CSV with one column of hourly kW values (8760 rows)
    values = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            values.append(float(line.split(",")[0]))
        except ValueError:
            continue

    if len(values) != 8760:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected 8760 hourly values, got {len(values)}",
        )

    arr = np.array(values, dtype=np.float64)
    profile = LoadProfile(
        project_id=project_id,
        name=file.filename or "Uploaded Load",
        profile_type="custom",
        annual_kwh=float(arr.sum()),
        hourly_kw=_compress_array(arr),
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/{project_id}/load-profiles", response_model=list[LoadProfileResponse])
async def list_load_profiles(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(LoadProfile).where(LoadProfile.project_id == project_id)
    )
    return result.scalars().all()
