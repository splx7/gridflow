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
    GenerateLoadProfileRequest,
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


# ── Synthetic load profile generation ──────────────────────────

_SCENARIO_DEFAULTS: dict[str, dict] = {
    "residential_small": {
        "name": "Residential (Small)",
        "profile_type": "residential",
        "annual_kwh": 5_000,
        # hourly shape: morning + evening peaks, low overnight
        "hourly_shape": [
            0.3, 0.25, 0.2, 0.2, 0.2, 0.25,   # 0-5
            0.5, 0.8, 0.9, 0.7, 0.5, 0.45,     # 6-11
            0.45, 0.4, 0.4, 0.45, 0.55, 0.8,    # 12-17
            1.0, 0.95, 0.85, 0.7, 0.5, 0.35,    # 18-23
        ],
        "weekend_factor": 1.15,
        "seasonal_amp": 0.15,
        "peak_season": "winter",
    },
    "residential_large": {
        "name": "Residential (Large)",
        "profile_type": "residential",
        "annual_kwh": 12_000,
        "hourly_shape": [
            0.35, 0.3, 0.25, 0.25, 0.25, 0.3,
            0.55, 0.85, 0.9, 0.7, 0.55, 0.5,
            0.5, 0.45, 0.45, 0.5, 0.6, 0.85,
            1.0, 0.95, 0.85, 0.7, 0.55, 0.4,
        ],
        "weekend_factor": 1.2,
        "seasonal_amp": 0.2,
        "peak_season": "summer",
    },
    "commercial_office": {
        "name": "Commercial Office",
        "profile_type": "commercial",
        "annual_kwh": 50_000,
        "hourly_shape": [
            0.2, 0.2, 0.2, 0.2, 0.2, 0.2,
            0.3, 0.6, 0.9, 1.0, 1.0, 0.95,
            0.85, 1.0, 1.0, 0.95, 0.9, 0.7,
            0.4, 0.25, 0.2, 0.2, 0.2, 0.2,
        ],
        "weekend_factor": 0.3,
        "seasonal_amp": 0.2,
        "peak_season": "summer",
    },
    "commercial_retail": {
        "name": "Commercial Retail",
        "profile_type": "commercial",
        "annual_kwh": 80_000,
        "hourly_shape": [
            0.15, 0.15, 0.15, 0.15, 0.15, 0.15,
            0.2, 0.3, 0.6, 0.85, 0.95, 1.0,
            1.0, 1.0, 1.0, 0.95, 0.9, 0.85,
            0.8, 0.7, 0.55, 0.35, 0.2, 0.15,
        ],
        "weekend_factor": 1.1,
        "seasonal_amp": 0.15,
        "peak_season": "summer",
    },
    "industrial_light": {
        "name": "Industrial (Light)",
        "profile_type": "industrial",
        "annual_kwh": 200_000,
        "hourly_shape": [
            0.3, 0.3, 0.3, 0.3, 0.3, 0.4,
            0.7, 0.9, 1.0, 1.0, 1.0, 0.95,
            0.85, 1.0, 1.0, 1.0, 0.95, 0.8,
            0.5, 0.35, 0.3, 0.3, 0.3, 0.3,
        ],
        "weekend_factor": 0.4,
        "seasonal_amp": 0.1,
        "peak_season": "summer",
    },
    "industrial_heavy": {
        "name": "Industrial (Heavy)",
        "profile_type": "industrial",
        "annual_kwh": 500_000,
        "hourly_shape": [
            0.85, 0.85, 0.85, 0.85, 0.85, 0.9,
            0.95, 1.0, 1.0, 1.0, 1.0, 1.0,
            0.95, 1.0, 1.0, 1.0, 1.0, 0.95,
            0.9, 0.9, 0.85, 0.85, 0.85, 0.85,
        ],
        "weekend_factor": 0.85,
        "seasonal_amp": 0.05,
        "peak_season": "summer",
    },
    "agricultural": {
        "name": "Agricultural",
        "profile_type": "agricultural",
        "annual_kwh": 30_000,
        "hourly_shape": [
            0.15, 0.15, 0.15, 0.15, 0.15, 0.2,
            0.5, 0.8, 1.0, 1.0, 0.95, 0.9,
            0.85, 0.9, 1.0, 0.95, 0.8, 0.6,
            0.35, 0.2, 0.15, 0.15, 0.15, 0.15,
        ],
        "weekend_factor": 0.6,
        "seasonal_amp": 0.35,
        "peak_season": "summer",
    },
}


def _generate_synthetic_profile(scenario_cfg: dict, annual_kwh: float) -> np.ndarray:
    """Generate an 8760-hour synthetic load profile."""
    rng = np.random.default_rng(42)
    shape = np.array(scenario_cfg["hourly_shape"], dtype=np.float64)
    weekend_factor = scenario_cfg["weekend_factor"]
    seasonal_amp = scenario_cfg["seasonal_amp"]
    peak_summer = scenario_cfg["peak_season"] == "summer"

    hours = np.arange(8760)
    hour_of_day = hours % 24
    day_of_year = hours // 24
    day_of_week = day_of_year % 7  # 0=Mon (approx)

    # Base hourly shape
    profile = shape[hour_of_day]

    # Weekend adjustment
    is_weekend = (day_of_week >= 5)
    profile = np.where(is_weekend, profile * weekend_factor, profile)

    # Seasonal variation (sinusoidal, peak at day ~182 for summer or ~0 for winter)
    phase = 0.0 if peak_summer else np.pi
    seasonal = 1.0 + seasonal_amp * np.sin(2 * np.pi * day_of_year / 365.0 + phase)
    profile *= seasonal

    # Add noise (±5%)
    profile *= 1.0 + rng.normal(0, 0.05, 8760)
    profile = np.clip(profile, 0.01, None)

    # Scale to target annual_kwh
    profile *= annual_kwh / profile.sum()
    return profile


@router.post(
    "/{project_id}/load-profiles/generate",
    response_model=LoadProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_load_profile(
    project_id: uuid.UUID,
    body: GenerateLoadProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)

    scenario_cfg = _SCENARIO_DEFAULTS.get(body.scenario)
    if not scenario_cfg:
        valid = ", ".join(_SCENARIO_DEFAULTS.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown scenario '{body.scenario}'. Valid: {valid}",
        )

    annual_kwh = body.annual_kwh if body.annual_kwh is not None else scenario_cfg["annual_kwh"]
    arr = _generate_synthetic_profile(scenario_cfg, annual_kwh)

    profile = LoadProfile(
        project_id=project_id,
        name=scenario_cfg["name"],
        profile_type=scenario_cfg["profile_type"],
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
