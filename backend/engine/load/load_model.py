"""Synthetic load-profile generation for power-system simulations.

Creates 8760-element (one year, hourly resolution) load profiles from
built-in templates, with optional noise injection and annual-energy scaling.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from numpy.typing import NDArray


# ======================================================================
# Built-in hourly shape templates (24 values, normalised to peak = 1.0)
# ======================================================================

# Residential: low overnight, morning bump, strong evening peak.
_RESIDENTIAL_HOURLY = np.array(
    [
        0.30, 0.25, 0.22, 0.20, 0.20, 0.22,  # 00-05
        0.35, 0.50, 0.55, 0.45, 0.40, 0.38,  # 06-11
        0.40, 0.42, 0.45, 0.55, 0.70, 0.85,  # 12-17
        1.00, 0.95, 0.85, 0.70, 0.55, 0.40,  # 18-23
    ],
    dtype=np.float64,
)

# Commercial: ramps up in the morning, flat daytime, drops after 18:00.
_COMMERCIAL_HOURLY = np.array(
    [
        0.20, 0.18, 0.17, 0.17, 0.18, 0.20,  # 00-05
        0.30, 0.55, 0.80, 0.92, 0.95, 1.00,  # 06-11
        0.98, 1.00, 0.97, 0.95, 0.85, 0.65,  # 12-17
        0.45, 0.35, 0.30, 0.27, 0.24, 0.22,  # 18-23
    ],
    dtype=np.float64,
)

# Industrial: nearly flat 24/7 operation with minor overnight dip.
_INDUSTRIAL_HOURLY = np.array(
    [
        0.85, 0.83, 0.82, 0.82, 0.83, 0.87,  # 00-05
        0.92, 0.96, 0.98, 1.00, 1.00, 1.00,  # 06-11
        0.99, 1.00, 1.00, 0.99, 0.98, 0.96,  # 12-17
        0.94, 0.92, 0.90, 0.89, 0.87, 0.86,  # 18-23
    ],
    dtype=np.float64,
)

# Rural village: very low overnight, cooking bump at dawn, strong evening peak.
# Typical Pacific Island / rural developing community pattern.
_RURAL_VILLAGE_HOURLY = np.array(
    [
        0.10, 0.10, 0.10, 0.10, 0.12, 0.15,  # 00-05
        0.40, 0.35, 0.25, 0.20, 0.20, 0.22,  # 06-11
        0.25, 0.22, 0.20, 0.25, 0.35, 0.60,  # 12-17
        1.00, 0.95, 0.80, 0.55, 0.30, 0.15,  # 18-23
    ],
    dtype=np.float64,
)

_PROFILES = {
    "residential": _RESIDENTIAL_HOURLY,
    "commercial": _COMMERCIAL_HOURLY,
    "industrial": _INDUSTRIAL_HOURLY,
    "rural_village": _RURAL_VILLAGE_HOURLY,
}

# Monthly seasonal multipliers (index 0 = January).
# Northern-hemisphere pattern: higher in summer/winter, lower in shoulder.
_MONTHLY_SEASONAL = np.array(
    [
        1.10,  # Jan
        1.05,  # Feb
        0.95,  # Mar
        0.90,  # Apr
        0.92,  # May
        1.05,  # Jun
        1.15,  # Jul
        1.12,  # Aug
        1.00,  # Sep
        0.90,  # Oct
        0.95,  # Nov
        1.08,  # Dec
    ],
    dtype=np.float64,
)

# Southern-hemisphere pattern: higher Jun-Aug (winter lighting), lower Dec-Feb.
_MONTHLY_SEASONAL_SOUTHERN = np.array(
    [
        0.90,  # Jan (summer)
        0.92,  # Feb
        0.95,  # Mar
        1.00,  # Apr
        1.05,  # May
        1.12,  # Jun (winter)
        1.15,  # Jul
        1.10,  # Aug
        1.00,  # Sep
        0.95,  # Oct
        0.92,  # Nov
        0.88,  # Dec (summer)
    ],
    dtype=np.float64,
)

# Day-of-week multipliers (Mon=0 ... Sun=6).
_DOW_MULTIPLIER_RESIDENTIAL = np.array(
    [0.95, 0.95, 0.95, 0.95, 1.00, 1.10, 1.10], dtype=np.float64
)
_DOW_MULTIPLIER_COMMERCIAL = np.array(
    [1.05, 1.05, 1.05, 1.05, 1.00, 0.60, 0.55], dtype=np.float64
)
_DOW_MULTIPLIER_INDUSTRIAL = np.array(
    [1.00, 1.00, 1.00, 1.00, 1.00, 0.90, 0.85], dtype=np.float64
)
# Rural village: minimal weekday variation (subsistence patterns consistent).
_DOW_MULTIPLIER_RURAL_VILLAGE = np.array(
    [0.98, 0.98, 0.98, 0.98, 1.00, 1.05, 1.05], dtype=np.float64
)

_DOW_MULTIPLIERS = {
    "residential": _DOW_MULTIPLIER_RESIDENTIAL,
    "commercial": _DOW_MULTIPLIER_COMMERCIAL,
    "industrial": _DOW_MULTIPLIER_INDUSTRIAL,
    "rural_village": _DOW_MULTIPLIER_RURAL_VILLAGE,
}


# ======================================================================
# Public API
# ======================================================================


def generate_load_profile(
    annual_kwh: float,
    profile_type: str = "residential",
    noise_factor: float = 0.1,
    seed: Optional[int] = None,
    hemisphere: str = "northern",
) -> NDArray[np.float64]:
    """Create an 8760-element hourly load profile.

    Parameters
    ----------
    annual_kwh : float
        Total energy consumption target for the year (kWh).
    profile_type : str
        One of ``'residential'``, ``'commercial'``, ``'industrial'``,
        or ``'rural_village'``.
    noise_factor : float
        Standard deviation of Gaussian noise as a fraction of the hourly
        value.  ``0.0`` produces a perfectly deterministic profile.
    seed : int, optional
        Random seed for reproducibility.
    hemisphere : str
        ``'northern'`` or ``'southern'``.  Selects the seasonal pattern.
        Southern hemisphere has higher winter (Jun-Aug) and lower summer
        (Dec-Feb) multipliers.

    Returns
    -------
    NDArray[np.float64]
        Shape ``(8760,)`` array of hourly loads in kW.

    Raises
    ------
    ValueError
        If *profile_type* is not recognised or *annual_kwh* is negative.
    """
    if annual_kwh < 0:
        raise ValueError(f"annual_kwh must be >= 0, got {annual_kwh}")

    profile_type = profile_type.lower()
    if profile_type not in _PROFILES:
        raise ValueError(
            f"Unknown profile_type '{profile_type}'. "
            f"Choose from: {sorted(_PROFILES.keys())}"
        )

    hourly_shape = _PROFILES[profile_type]
    dow_mult = _DOW_MULTIPLIERS[profile_type]

    # Select seasonal pattern based on hemisphere
    if hemisphere.lower() == "southern":
        monthly_seasonal = _MONTHLY_SEASONAL_SOUTHERN
    else:
        monthly_seasonal = _MONTHLY_SEASONAL

    rng = np.random.default_rng(seed)

    # Build the raw 8760 profile.
    # We iterate conceptually over 365 days, each with 24 hours.
    # Year assumed to start on a Monday (day-of-week index 0).
    hours_per_year = 8760
    profile = np.empty(hours_per_year, dtype=np.float64)

    hour_idx = 0
    for day in range(365):
        month = _day_to_month(day)
        day_of_week = day % 7  # 0 = Monday

        seasonal = monthly_seasonal[month]
        weekday = dow_mult[day_of_week]

        for h in range(24):
            profile[hour_idx] = hourly_shape[h] * seasonal * weekday
            hour_idx += 1

    # Inject optional noise (multiplicative, clipped to stay positive).
    if noise_factor > 0:
        noise = rng.normal(loc=1.0, scale=noise_factor, size=hours_per_year)
        noise = np.clip(noise, 0.1, 3.0)  # prevent negatives / extremes
        profile *= noise

    # Scale to match the desired annual energy.
    profile = scale_profile(profile, annual_kwh)

    return profile


def scale_profile(
    base_profile: NDArray[np.float64],
    target_annual_kwh: float,
) -> NDArray[np.float64]:
    """Scale an existing hourly profile so its total matches a target.

    Parameters
    ----------
    base_profile : NDArray[np.float64]
        Hourly load values (kW), length 8760.
    target_annual_kwh : float
        Desired total energy over the year (kWh).

    Returns
    -------
    NDArray[np.float64]
        Scaled copy of *base_profile* with ``sum() == target_annual_kwh``
        (within floating-point precision).

    Raises
    ------
    ValueError
        If *base_profile* sums to zero (cannot be scaled) or has the
        wrong length.
    """
    if len(base_profile) != 8760:
        raise ValueError(
            f"base_profile must have 8760 elements, got {len(base_profile)}"
        )

    current_total = base_profile.sum()
    if current_total == 0:
        raise ValueError("Cannot scale an all-zero profile.")

    scale = target_annual_kwh / current_total
    return base_profile * scale


# ======================================================================
# Internal helpers
# ======================================================================


def _day_to_month(day_of_year: int) -> int:
    """Convert 0-based day-of-year (0 -- 364) to 0-based month index.

    Uses a non-leap-year calendar (365 days).

    Parameters
    ----------
    day_of_year : int
        Day index, where 0 = January 1 and 364 = December 31.

    Returns
    -------
    int
        Month index, 0 (January) through 11 (December).
    """
    # Cumulative days at the *start* of each month (non-leap year).
    _MONTH_START = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

    for m in range(11, -1, -1):
        if day_of_year >= _MONTH_START[m]:
            return m

    return 0  # pragma: no cover — unreachable
