"""Wind resource assessment endpoint."""
import uuid
import zlib
import struct

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.project import Project
from app.models.weather import WeatherDataset
from app.models.user import User

from engine.wind.weibull import weibull_params, weibull_aep
from engine.wind.power_curve import generic_power_curve
from engine.wind.wind_resource import height_correction

router = APIRouter()


def _decompress_ts(blob: bytes) -> list[float]:
    raw = zlib.decompress(blob)
    n = len(raw) // 8
    return list(struct.unpack(f"<{n}d", raw))


@router.get(
    "/{project_id}/wind-assessment",
    summary="Wind resource assessment",
    description="Compute Weibull parameters, AEP estimate, and wind speed histogram from weather data.",
)
async def wind_assessment(
    project_id: uuid.UUID,
    hub_height: float = 80.0,
    rated_power_kw: float = 100.0,
    cut_in: float = 3.0,
    rated_speed: float = 12.0,
    cut_out: float = 25.0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Get latest weather dataset
    result = await db.execute(
        select(WeatherDataset)
        .where(WeatherDataset.project_id == project_id)
        .order_by(WeatherDataset.created_at.desc())
        .limit(1)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No weather data available. Fetch weather first.",
        )

    # Check for wind speed data
    if not dataset.wind_speed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Weather data does not contain wind speed information.",
        )

    ws = np.array(_decompress_ts(dataset.wind_speed), dtype=np.float64)

    # Height correct from 10m (PVGIS default) to hub height
    ws_hub = height_correction(
        wind_speed=ws,
        measurement_height=10.0,
        hub_height=hub_height,
    )

    # Weibull parameters
    k, c = weibull_params(ws_hub)

    # Generate power curve and compute AEP
    pc = generic_power_curve(
        rated_power_kw=rated_power_kw,
        cut_in=cut_in,
        rated_speed=rated_speed,
        cut_out=cut_out,
    )
    aep = weibull_aep(pc, k, c)
    capacity_factor = aep / (rated_power_kw * 8760) if rated_power_kw > 0 else 0.0

    # Wind speed histogram (1 m/s bins)
    max_ws = min(float(np.max(ws_hub)) + 1.0, 35.0)
    bin_edges = np.arange(0, max_ws + 1, 1.0)
    counts, _ = np.histogram(ws_hub, bins=bin_edges)
    histogram = [
        {"bin_start": float(bin_edges[i]), "bin_end": float(bin_edges[i + 1]), "hours": int(counts[i])}
        for i in range(len(counts))
    ]

    # Monthly average wind speeds
    if len(ws_hub) == 8760:
        month_hours = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
        monthly_avg = []
        offset = 0
        for h in month_hours:
            monthly_avg.append(float(np.mean(ws_hub[offset : offset + h])))
            offset += h
    else:
        monthly_avg = []

    return {
        "weibull_k": round(k, 3),
        "weibull_c": round(c, 3),
        "mean_wind_speed": round(float(np.mean(ws_hub)), 2),
        "max_wind_speed": round(float(np.max(ws_hub)), 2),
        "aep_kwh": round(aep, 1),
        "capacity_factor": round(capacity_factor, 4),
        "hub_height_m": hub_height,
        "rated_power_kw": rated_power_kw,
        "histogram": histogram,
        "monthly_avg_wind_speed": [round(v, 2) for v in monthly_avg],
    }
