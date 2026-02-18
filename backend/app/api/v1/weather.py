import uuid
import zlib

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rate_limit import weather_limiter
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
    summary="Fetch PVGIS weather data",
    description="Download a Typical Meteorological Year dataset from the PVGIS API for the project location.",
)
async def fetch_pvgis(
    project_id: uuid.UUID,
    body: PVGISRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    weather_limiter.check(request)
    project = await _get_user_project(project_id, user, db)

    correction_applied = False
    correction_metadata = None

    if body.apply_correction:
        from app.services.weather_service import fetch_pvgis_tmy_corrected

        weather_data, correction_metadata = await fetch_pvgis_tmy_corrected(
            project.latitude, project.longitude, inject_extreme=body.inject_extreme_weather
        )
        correction_applied = correction_metadata.get("correction_source") != "none"
    else:
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
        correction_applied=correction_applied,
        correction_metadata=correction_metadata,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.post(
    "/{project_id}/weather/upload",
    response_model=WeatherDatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload weather CSV",
    description="Upload a TMY weather dataset from a CSV file with GHI, DNI, DHI, temperature, and wind speed.",
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


@router.get(
    "/{project_id}/weather",
    response_model=list[WeatherDatasetResponse],
    summary="List weather datasets",
    description="Return all weather datasets associated with a project.",
)
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
    # ── Developing-country scenarios ──────────────────────────────
    "village_microgrid": {
        "name": "Village Microgrid",
        "profile_type": "village",
        "annual_kwh": 80_000,
        "hourly_shape": [
            0.2, 0.15, 0.15, 0.15, 0.15, 0.2,
            0.35, 0.5, 0.55, 0.5, 0.45, 0.4,
            0.4, 0.45, 0.45, 0.5, 0.6, 0.75,
            1.0, 0.95, 0.85, 0.65, 0.4, 0.25,
        ],
        "weekend_factor": 1.1,
        "seasonal_amp": 0.1,
        "peak_season": "summer",
    },
    "health_clinic": {
        "name": "Health Clinic",
        "profile_type": "health",
        "annual_kwh": 15_000,
        "hourly_shape": [
            0.4, 0.4, 0.4, 0.4, 0.4, 0.45,
            0.6, 0.8, 0.9, 1.0, 1.0, 0.95,
            0.85, 0.9, 0.95, 0.9, 0.8, 0.65,
            0.5, 0.45, 0.4, 0.4, 0.4, 0.4,
        ],
        "weekend_factor": 0.7,
        "seasonal_amp": 0.1,
        "peak_season": "summer",
    },
    "school_campus": {
        "name": "School Campus",
        "profile_type": "school",
        "annual_kwh": 25_000,
        "hourly_shape": [
            0.1, 0.1, 0.1, 0.1, 0.1, 0.15,
            0.3, 0.6, 0.9, 1.0, 1.0, 0.95,
            0.8, 0.95, 1.0, 0.9, 0.7, 0.4,
            0.2, 0.15, 0.1, 0.1, 0.1, 0.1,
        ],
        "weekend_factor": 0.2,
        "seasonal_amp": 0.25,
        "peak_season": "winter",
    },
    "telecom_tower": {
        "name": "Telecom Tower",
        "profile_type": "telecom",
        "annual_kwh": 18_000,
        "hourly_shape": [
            0.9, 0.88, 0.87, 0.87, 0.88, 0.9,
            0.92, 0.95, 0.98, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 0.98, 0.97, 0.95,
            0.95, 0.93, 0.92, 0.91, 0.9, 0.9,
        ],
        "weekend_factor": 1.0,
        "seasonal_amp": 0.03,
        "peak_season": "summer",
    },
    "small_enterprise": {
        "name": "Small Enterprise",
        "profile_type": "commercial",
        "annual_kwh": 22_000,
        "hourly_shape": [
            0.1, 0.1, 0.1, 0.1, 0.1, 0.15,
            0.3, 0.6, 0.85, 0.95, 1.0, 1.0,
            0.9, 0.95, 1.0, 0.95, 0.85, 0.7,
            0.5, 0.3, 0.15, 0.1, 0.1, 0.1,
        ],
        "weekend_factor": 0.5,
        "seasonal_amp": 0.1,
        "peak_season": "summer",
    },
    "water_pumping": {
        "name": "Water Pumping",
        "profile_type": "agricultural",
        "annual_kwh": 35_000,
        "hourly_shape": [
            0.0, 0.0, 0.0, 0.0, 0.0, 0.05,
            0.3, 0.7, 0.9, 1.0, 1.0, 1.0,
            1.0, 1.0, 0.95, 0.85, 0.6, 0.3,
            0.05, 0.0, 0.0, 0.0, 0.0, 0.0,
        ],
        "weekend_factor": 0.8,
        "seasonal_amp": 0.4,
        "peak_season": "summer",
    },
    "rural_village": {
        "name": "Rural Village (Pacific / FREF)",
        "profile_type": "rural_village",
        "annual_kwh": 55_000,
        "hourly_shape": [
            0.12, 0.10, 0.10, 0.10, 0.10, 0.15,
            0.40, 0.35, 0.25, 0.20, 0.20, 0.20,
            0.25, 0.25, 0.25, 0.30, 0.50, 0.75,
            1.00, 0.95, 0.80, 0.55, 0.30, 0.15,
        ],
        "weekend_factor": 1.05,
        "seasonal_amp": 0.10,
        "peak_season": "winter",
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
    summary="Generate synthetic load profile",
    description="Generate an 8760-hour load profile from a built-in scenario template or composite of scenarios.",
)
async def generate_load_profile(
    project_id: uuid.UUID,
    body: GenerateLoadProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)

    # Composite scenario (multiple keys)
    if body.scenarios and len(body.scenarios) > 1:
        valid_keys = set(_SCENARIO_DEFAULTS.keys())
        invalid = [k for k in body.scenarios if k not in valid_keys]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown scenario(s): {', '.join(invalid)}. Valid: {', '.join(valid_keys)}",
            )

        # Combine hourly shapes weighted by annual_kwh
        combined_shape = np.zeros(24)
        total_kwh = 0.0
        total_weekend = 0.0
        total_seasonal = 0.0
        for key in body.scenarios:
            cfg = _SCENARIO_DEFAULTS[key]
            shape = np.array(cfg["hourly_shape"])
            weight = cfg["annual_kwh"]
            combined_shape += shape * weight
            total_weekend += cfg["weekend_factor"] * weight
            total_seasonal += cfg["seasonal_amp"] * weight
            total_kwh += weight
        combined_shape /= total_kwh

        composite_cfg = {
            "hourly_shape": combined_shape.tolist(),
            "weekend_factor": total_weekend / total_kwh,
            "seasonal_amp": total_seasonal / total_kwh,
            "peak_season": "summer",
        }
        annual_kwh = body.annual_kwh if body.annual_kwh is not None else total_kwh
        arr = _generate_synthetic_profile(composite_cfg, annual_kwh)

        names = [_SCENARIO_DEFAULTS[k]["name"] for k in body.scenarios]
        profile_name = " + ".join(names)

        profile = LoadProfile(
            project_id=project_id,
            name=profile_name,
            profile_type="composite",
            annual_kwh=float(arr.sum()),
            hourly_kw=_compress_array(arr),
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile

    # Single scenario
    scenario_key = body.scenario or (body.scenarios[0] if body.scenarios else None)
    if not scenario_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'scenario' or 'scenarios'",
        )

    scenario_cfg = _SCENARIO_DEFAULTS.get(scenario_key)
    if not scenario_cfg:
        valid = ", ".join(_SCENARIO_DEFAULTS.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown scenario '{scenario_key}'. Valid: {valid}",
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


@router.get(
    "/{project_id}/weather/{dataset_id}/preview",
    summary="Preview weather dataset",
    description="Return monthly average GHI and temperature values for dashboard preview charts.",
)
async def weather_preview(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(WeatherDataset).where(
            WeatherDataset.id == dataset_id,
            WeatherDataset.project_id == project_id,
        )
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Weather dataset not found")

    ghi = np.frombuffer(zlib.decompress(ds.ghi), dtype=np.float64)
    temp = np.frombuffer(zlib.decompress(ds.temperature), dtype=np.float64)

    # Monthly averages (assume 8760 hours, non-leap year)
    month_hours = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_ghi = []
    monthly_temp = []
    offset = 0
    for hours in month_hours:
        monthly_ghi.append(round(float(ghi[offset:offset + hours].mean()), 1))
        monthly_temp.append(round(float(temp[offset:offset + hours].mean()), 1))
        offset += hours

    return {
        "months": month_names,
        "ghi_avg": monthly_ghi,
        "temp_avg": monthly_temp,
        "annual_ghi_kwh_m2": round(float(ghi.sum()) / 1000, 0),
    }


@router.get(
    "/{project_id}/load-profiles/{profile_id}/preview",
    summary="Preview load profile",
    description="Return 24-hour average load shape, peak, min, and annual energy for preview charts.",
)
async def load_profile_preview(
    project_id: uuid.UUID,
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_project(project_id, user, db)
    result = await db.execute(
        select(LoadProfile).where(
            LoadProfile.id == profile_id,
            LoadProfile.project_id == project_id,
        )
    )
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="Load profile not found")

    hourly = np.frombuffer(zlib.decompress(lp.hourly_kw), dtype=np.float64)
    # Average by hour of day
    reshaped = hourly.reshape(365, 24)
    avg_shape = reshaped.mean(axis=0)

    return {
        "hours": list(range(24)),
        "avg_kw": [round(float(v), 2) for v in avg_shape],
        "peak_kw": round(float(hourly.max()), 1),
        "min_kw": round(float(hourly.min()), 1),
        "annual_kwh": round(float(hourly.sum()), 0),
    }


@router.get(
    "/{project_id}/load-profiles",
    response_model=list[LoadProfileResponse],
    summary="List load profiles",
    description="Return all load profiles belonging to a project.",
)
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


@router.post(
    "/{project_id}/load-profiles",
    response_model=LoadProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload load profile CSV",
    description="Upload an 8760-row CSV file of hourly kW load values.",
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
