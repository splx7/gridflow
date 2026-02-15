"""PVGIS API client for fetching TMY and solar radiation data."""

import httpx
import numpy as np

from engine.weather.tmy_parser import TMYData, parse_pvgis_csv

PVGIS_BASE_URL = "https://re.jrc.ec.europa.eu/api/v5_3"


async def fetch_tmy(
    lat: float,
    lon: float,
    startyear: int = 2005,
    endyear: int = 2020,
) -> TMYData:
    """Fetch TMY data from PVGIS for given coordinates.

    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
        startyear: Start year for TMY generation
        endyear: End year for TMY generation

    Returns:
        TMYData with 8760 hourly values
    """
    params = {
        "lat": lat,
        "lon": lon,
        "outputformat": "csv",
        "startyear": startyear,
        "endyear": endyear,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(f"{PVGIS_BASE_URL}/tmy", params=params)
        response.raise_for_status()

    return parse_pvgis_csv(response.text)


async def fetch_hourly_radiation(
    lat: float,
    lon: float,
    year: int = 2020,
    pvcalculation: bool = False,
    peakpower: float | None = None,
    angle: float | None = None,
    aspect: float | None = None,
) -> dict[str, np.ndarray]:
    """Fetch hourly radiation data from PVGIS for a specific year.

    Args:
        lat: Latitude
        lon: Longitude
        year: Year to fetch data for
        pvcalculation: If True, include PV output calculation
        peakpower: PV peak power in kWp (required if pvcalculation=True)
        angle: PV tilt angle in degrees
        aspect: PV azimuth (0=south, 90=west, -90=east)

    Returns:
        Dictionary with hourly arrays
    """
    params: dict = {
        "lat": lat,
        "lon": lon,
        "outputformat": "csv",
        "startyear": year,
        "endyear": year,
        "pvcalculation": int(pvcalculation),
    }
    if peakpower is not None:
        params["peakpower"] = peakpower
    if angle is not None:
        params["angle"] = angle
    if aspect is not None:
        params["aspect"] = aspect

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(f"{PVGIS_BASE_URL}/seriescalc", params=params)
        response.raise_for_status()

    # Parse the response - similar structure to TMY
    return {"raw_csv": response.text}
