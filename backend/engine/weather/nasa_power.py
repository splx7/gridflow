"""NASA POWER API client and PVGIS de-biasing corrections.

Fetches monthly climatology from NASA POWER (better tropical Pacific coverage)
and uses it to correct systematic biases in PVGIS TMY hourly data:
- Wet/dry season GHI inversion
- Diffuse fraction underestimation
- Temperature bias (unrealistic lows for tropical sites)
- Insufficient extreme weather events

Also provides synthetic cyclone event injection for Pacific island resilience studies.
"""

from __future__ import annotations

import httpx
import numpy as np

# Hours in each month of a non-leap year (8760 total)
MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]

# Cumulative hour offsets for month boundaries
_MONTH_OFFSETS: list[tuple[int, int]] = []
_off = 0
for _h in MONTH_HOURS:
    _MONTH_OFFSETS.append((_off, _off + _h))
    _off += _h

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"


async def fetch_nasa_power_monthly(lat: float, lon: float) -> dict:
    """Fetch monthly climatology from NASA POWER API.

    Returns dict with 12-element lists for each variable:
        ghi, dni, dhi, temperature, temp_max, temp_min, wind_speed
    """
    # Climatology endpoint does not accept start/end params
    params = {
        "latitude": lat,
        "longitude": lon,
        "community": "RE",
        "parameters": "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DNI,ALLSKY_SFC_SW_DIFF,T2M,T2M_MAX,T2M_MIN,WS10M",
        "format": "JSON",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(NASA_POWER_URL, params=params)
        response.raise_for_status()

    data = response.json()
    props = data["properties"]["parameter"]

    _MONTH_KEYS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                   "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

    def _extract_monthly(key: str, to_wm2: bool = False) -> list[float]:
        """Extract 12 monthly values. If to_wm2, convert kWh/m²/day → W/m².

        NASA POWER irradiance is in kWh/m²/day. PVGIS hourly averages are
        in W/m². To compare: W/m² = kWh/m²/day * 1000 / 24 ≈ *41.67.
        """
        raw = props[key]
        values = [float(raw[m]) for m in _MONTH_KEYS]
        if to_wm2:
            values = [v * 1000.0 / 24.0 for v in values]
        return values

    return {
        "ghi": _extract_monthly("ALLSKY_SFC_SW_DWN", to_wm2=True),
        "dni": _extract_monthly("ALLSKY_SFC_SW_DNI", to_wm2=True),
        "dhi": _extract_monthly("ALLSKY_SFC_SW_DIFF", to_wm2=True),
        "temperature": _extract_monthly("T2M"),
        "temp_max": _extract_monthly("T2M_MAX"),
        "temp_min": _extract_monthly("T2M_MIN"),
        "wind_speed": _extract_monthly("WS10M"),
    }


def apply_monthly_correction(
    pvgis_data: dict[str, np.ndarray],
    nasa_monthly: dict,
) -> tuple[dict[str, np.ndarray], dict]:
    """De-bias PVGIS hourly data using NASA POWER monthly climatology.

    For each month:
    1. Compute GHI scale factor = nasa_ghi / pvgis_ghi (clamped 0.5-2.0)
    2. Scale GHI, DNI, DHI by that factor (preserves diffuse/direct split)
    3. Shift temperature to match NASA monthly mean

    Returns (corrected_data, metadata).
    """
    ghi = pvgis_data["ghi"].copy()
    dni = pvgis_data["dni"].copy()
    dhi = pvgis_data["dhi"].copy()
    temp = pvgis_data["temperature"].copy()
    wind = pvgis_data["wind_speed"].copy()

    nasa_ghi = nasa_monthly["ghi"]
    nasa_temp = nasa_monthly["temperature"]

    scale_factors = []
    temp_shifts = []
    pvgis_monthly_ghi = []
    corrected_monthly_ghi = []

    for m in range(12):
        start, end = _MONTH_OFFSETS[m]

        # GHI scaling
        pvgis_avg = float(np.mean(ghi[start:end]))
        pvgis_monthly_ghi.append(round(pvgis_avg, 2))
        nasa_avg = nasa_ghi[m]

        if pvgis_avg > 0:
            scale = nasa_avg / pvgis_avg
        else:
            scale = 1.0

        # Clamp to prevent extreme corrections
        scale = max(0.5, min(2.0, scale))
        scale_factors.append(round(scale, 4))

        ghi[start:end] *= scale
        dni[start:end] *= scale
        dhi[start:end] *= scale

        corrected_monthly_ghi.append(round(float(np.mean(ghi[start:end])), 2))

        # Temperature shift
        pvgis_temp_avg = float(np.mean(temp[start:end]))
        shift = nasa_temp[m] - pvgis_temp_avg
        temp_shifts.append(round(shift, 2))
        temp[start:end] += shift

    # Clamp negative irradiance values
    ghi = np.maximum(ghi, 0.0)
    dni = np.maximum(dni, 0.0)
    dhi = np.maximum(dhi, 0.0)

    corrected_data = {
        "ghi": ghi,
        "dni": dni,
        "dhi": dhi,
        "temperature": temp,
        "wind_speed": wind,
    }

    metadata = {
        "correction_source": "NASA_POWER_climatology_2001_2020",
        "scale_factors": scale_factors,
        "temp_shifts": temp_shifts,
        "pvgis_monthly_ghi_avg": pvgis_monthly_ghi,
        "corrected_monthly_ghi_avg": corrected_monthly_ghi,
        "nasa_monthly_ghi": [round(v, 2) for v in nasa_ghi],
        "nasa_monthly_temp": [round(v, 2) for v in nasa_temp],
    }

    return corrected_data, metadata


def inject_cyclone_events(
    weather_data: dict[str, np.ndarray],
    lat: float,
    num_events: int = 2,
    duration_days: int = 3,
    seed: int = 42,
) -> tuple[dict[str, np.ndarray], list[dict]]:
    """Inject synthetic cyclone low-irradiance events into weather data.

    For Southern Hemisphere tropical sites (roughly lat < 20 and lon > 150 or
    Pacific island range), cyclone season is Nov-Apr.

    Each event:
    - GHI drops to 10-20% of normal
    - Wind speed spikes to 15-25 m/s
    - Placed randomly within cyclone season (seeded RNG)

    Returns (modified_data, event_metadata).
    """
    rng = np.random.default_rng(seed)

    ghi = weather_data["ghi"].copy()
    dni = weather_data["dni"].copy()
    dhi = weather_data["dhi"].copy()
    wind = weather_data["wind_speed"].copy()
    temp = weather_data["temperature"].copy()

    # Cyclone season hours: Nov 1 (day 304) through Apr 30 (day 120 next year)
    # In 8760-hour array: hours 304*24..365*24 (Nov-Dec) + 0..120*24 (Jan-Apr)
    season_hours: list[int] = []
    for d in range(0, 120):  # Jan-Apr
        for h in range(24):
            season_hours.append(d * 24 + h)
    for d in range(304, 365):  # Nov-Dec
        for h in range(24):
            season_hours.append(d * 24 + h)

    duration_hours = duration_days * 24
    events = []

    # Available start positions (must fit full duration within season)
    # Use the Nov-Dec block and Jan-Apr block separately to avoid wrapping issues
    jan_apr_hours = 120 * 24  # 2880 hours
    nov_dec_hours = 61 * 24   # 1464 hours

    for i in range(num_events):
        # Alternate between Nov-Dec and Jan-Apr blocks
        if i % 2 == 0 and nov_dec_hours >= duration_hours:
            block_start = 304 * 24
            block_end = 365 * 24 - duration_hours
        else:
            block_start = 0
            block_end = jan_apr_hours - duration_hours

        if block_end <= block_start:
            continue

        start_hour = int(rng.integers(block_start, block_end))
        end_hour = start_hour + duration_hours

        # GHI reduction factor (10-20% of normal)
        ghi_factor = rng.uniform(0.10, 0.20)
        # Wind spike (15-25 m/s)
        wind_speed = rng.uniform(15.0, 25.0)

        ghi[start_hour:end_hour] *= ghi_factor
        dni[start_hour:end_hour] *= ghi_factor * 0.5  # Heavy cloud kills direct more
        dhi[start_hour:end_hour] *= ghi_factor * 1.5   # Diffuse drops less
        # Clamp DHI to not exceed GHI
        dhi[start_hour:end_hour] = np.minimum(
            dhi[start_hour:end_hour], ghi[start_hour:end_hour]
        )
        wind[start_hour:end_hour] = wind_speed + rng.normal(0, 2.0, duration_hours)
        wind[start_hour:end_hour] = np.maximum(wind[start_hour:end_hour], 0.0)

        start_day = start_hour // 24
        events.append({
            "event_index": i,
            "start_day": start_day,
            "duration_days": duration_days,
            "start_hour": start_hour,
            "end_hour": end_hour,
            "ghi_factor": round(float(ghi_factor), 3),
            "wind_speed_ms": round(float(wind_speed), 1),
        })

    corrected_data = {
        "ghi": np.maximum(ghi, 0.0),
        "dni": np.maximum(dni, 0.0),
        "dhi": np.maximum(dhi, 0.0),
        "temperature": temp,
        "wind_speed": np.maximum(wind, 0.0),
    }

    return corrected_data, events
