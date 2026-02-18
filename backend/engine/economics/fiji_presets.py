"""Fiji FREF cost presets and utility functions.

Constants and helper functions specific to the Fiji Rural Electrification
Fund (FREF) programme, covering FEA tariffs, logistics premiums for outer
island delivery, cyclone derating, and per-household cost metrics.
"""

from __future__ import annotations

from typing import Any

# ======================================================================
# FREF cost presets
# ======================================================================

FIJI_PRESETS: dict[str, Any] = {
    # Currency
    "currency": "FJD",
    "usd_to_fjd": 2.25,  # approximate exchange rate

    # FEA tariff (Fiji Electricity Authority, 2024 schedule)
    "fea_tariff_fjd_per_kwh": 0.3401,
    "fea_tariff_usd_per_kwh": 0.3401 / 2.25,

    # Diesel fuel
    "diesel_price_fjd_per_l": 3.50,
    "diesel_price_usd_per_l": 3.50 / 2.25,

    # Logistics premium for outer islands (barge + handling)
    "logistics_premium_pct": 30.0,

    # Cyclone derating (annual energy loss from cyclone damage/cleaning)
    "cyclone_derating_pct": 5.0,

    # Battery autonomy requirement (FREF standard: 3 days)
    "autonomy_days": 3,

    # Financial parameters
    "discount_rate": 0.06,
    "project_lifetime_years": 20,

    # CO2 factor for displaced diesel
    "co2_kg_per_litre_diesel": 2.68,

    # Smart metering cost per household
    "smart_meter_cost_usd": 150.0,
}


# ======================================================================
# Utility functions
# ======================================================================


def apply_logistics_premium(base_cost: float, premium_pct: float | None = None) -> float:
    """Apply the outer-island logistics premium to a base equipment cost.

    Parameters
    ----------
    base_cost : float
        Equipment cost before logistics (USD or FJD).
    premium_pct : float or None
        Logistics surcharge as a percentage. Defaults to FREF standard 30%.

    Returns
    -------
    float
        Cost including logistics premium.
    """
    if premium_pct is None:
        premium_pct = FIJI_PRESETS["logistics_premium_pct"]
    return base_cost * (1.0 + premium_pct / 100.0)


def battery_autonomy_kwh(
    daily_load_kwh: float,
    autonomy_days: int = 3,
    min_soc: float = 0.10,
    max_soc: float = 0.95,
) -> float:
    """Calculate required battery capacity for N days of autonomy.

    Parameters
    ----------
    daily_load_kwh : float
        Average daily energy consumption (kWh).
    autonomy_days : int
        Number of days the battery must sustain load without charging.
    min_soc : float
        Minimum state of charge (fraction, 0-1).
    max_soc : float
        Maximum state of charge (fraction, 0-1).

    Returns
    -------
    float
        Required battery capacity in kWh (usable + reserves).
    """
    usable_fraction = max_soc - min_soc
    if usable_fraction <= 0:
        return 0.0
    return (daily_load_kwh * autonomy_days) / usable_fraction


def cyclone_derating_factor(derating_pct: float | None = None) -> float:
    """Return the multiplicative derating factor for cyclone risk.

    Parameters
    ----------
    derating_pct : float or None
        Annual energy derating percentage. Defaults to FREF standard 5%.

    Returns
    -------
    float
        Factor to multiply annual PV output by (e.g. 0.95 for 5% derating).
    """
    if derating_pct is None:
        derating_pct = FIJI_PRESETS["cyclone_derating_pct"]
    return 1.0 - derating_pct / 100.0


def diesel_displacement_pct(
    annual_re_kwh: float,
    annual_load_kwh: float,
) -> float:
    """Calculate the percentage of diesel generation displaced by renewables.

    Assumes that without the RE system, all load would be served by diesel.

    Parameters
    ----------
    annual_re_kwh : float
        Annual renewable energy generated (kWh).
    annual_load_kwh : float
        Annual load demand (kWh).

    Returns
    -------
    float
        Diesel displacement as a percentage (0-100).
    """
    if annual_load_kwh <= 0:
        return 0.0
    return min(100.0, (annual_re_kwh / annual_load_kwh) * 100.0)


def cost_per_household(
    total_npc: float,
    num_households: int,
    currency: str = "USD",
) -> dict[str, float]:
    """Calculate the cost per household in USD and FJD.

    Parameters
    ----------
    total_npc : float
        Total net present cost of the system (USD).
    num_households : int
        Number of households served.
    currency : str
        Currency of ``total_npc`` (``"USD"`` or ``"FJD"``).

    Returns
    -------
    dict
        ``{"usd": cost_per_hh_usd, "fjd": cost_per_hh_fjd}``
    """
    if num_households <= 0:
        return {"usd": 0.0, "fjd": 0.0}

    rate = FIJI_PRESETS["usd_to_fjd"]

    if currency.upper() == "FJD":
        cost_fjd = total_npc / num_households
        cost_usd = cost_fjd / rate
    else:
        cost_usd = total_npc / num_households
        cost_fjd = cost_usd * rate

    return {"usd": cost_usd, "fjd": cost_fjd}
