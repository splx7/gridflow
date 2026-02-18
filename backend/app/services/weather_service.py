import csv
import io
import logging

import httpx
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


async def fetch_pvgis_tmy(lat: float, lon: float) -> dict[str, np.ndarray]:
    """Fetch TMY data from PVGIS API and return 8760 hourly arrays."""
    url = f"{settings.pvgis_base_url}/tmy"
    params = {
        "lat": lat,
        "lon": lon,
        "outputformat": "csv",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()

    return parse_tmy_csv(response.text)


async def fetch_pvgis_tmy_corrected(
    lat: float,
    lon: float,
    inject_extreme: bool = False,
) -> tuple[dict[str, np.ndarray], dict]:
    """Fetch PVGIS TMY data corrected with NASA POWER monthly climatology.

    Returns (corrected_data, correction_metadata).
    Falls back to uncorrected PVGIS if NASA POWER API fails.
    """
    from engine.weather.nasa_power import (
        apply_monthly_correction,
        fetch_nasa_power_monthly,
        inject_cyclone_events,
    )

    pvgis_data = await fetch_pvgis_tmy(lat, lon)

    try:
        nasa_monthly = await fetch_nasa_power_monthly(lat, lon)
    except Exception as exc:
        logger.warning("NASA POWER API failed, using uncorrected PVGIS: %s", exc)
        metadata = {
            "correction_source": "none",
            "warning": f"NASA POWER API unavailable: {exc}",
        }
        return pvgis_data, metadata

    corrected_data, metadata = apply_monthly_correction(pvgis_data, nasa_monthly)

    if inject_extreme:
        corrected_data, events = inject_cyclone_events(corrected_data, lat)
        metadata["cyclone_events"] = events

    return corrected_data, metadata


def parse_tmy_csv(csv_text: str) -> dict[str, np.ndarray]:
    """Parse PVGIS TMY CSV format into 8760 hourly arrays."""
    lines = csv_text.strip().split("\n")

    # Skip header lines until we find the data header
    data_start = 0
    for i, line in enumerate(lines):
        if line.startswith("time(UTC)") or "G(h)" in line or "Gb(n)" in line:
            data_start = i
            break

    reader = csv.DictReader(lines[data_start:])

    ghi_list: list[float] = []
    dni_list: list[float] = []
    dhi_list: list[float] = []
    temp_list: list[float] = []
    wind_list: list[float] = []

    for row in reader:
        if not row:
            continue
        try:
            ghi_list.append(float(row.get("G(h)", row.get("ghi", 0))))
            dni_list.append(float(row.get("Gb(n)", row.get("dni", 0))))
            dhi_list.append(float(row.get("Gd(h)", row.get("dhi", 0))))
            temp_list.append(float(row.get("T2m", row.get("temperature", 20))))
            wind_list.append(float(row.get("WS10m", row.get("wind_speed", 3))))
        except (ValueError, TypeError):
            continue

    if len(ghi_list) < 8760:
        raise ValueError(f"Expected 8760 hourly records, got {len(ghi_list)}")

    return {
        "ghi": np.array(ghi_list[:8760], dtype=np.float64),
        "dni": np.array(dni_list[:8760], dtype=np.float64),
        "dhi": np.array(dhi_list[:8760], dtype=np.float64),
        "temperature": np.array(temp_list[:8760], dtype=np.float64),
        "wind_speed": np.array(wind_list[:8760], dtype=np.float64),
    }
