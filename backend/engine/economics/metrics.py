"""Core economic metrics for power system analysis.

Computes Net Present Cost (NPC), Levelised Cost of Energy (LCOE),
Internal Rate of Return (IRR), simple payback period, and detailed
cost breakdowns from dispatch simulation results and component
configurations.

All monetary values are in USD ($).  Energy is in kWh or kW as noted.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

try:
    from scipy.optimize import brentq
except ImportError:  # pragma: no cover – scipy is optional at import time
    brentq = None  # type: ignore[assignment]


# ======================================================================
# Constants
# ======================================================================

HOURS_PER_YEAR: int = 8760
BATTERY_EOL_THRESHOLD: float = 0.80  # Replace when capacity < 80 %


# ======================================================================
# Internal helpers
# ======================================================================

def _discount_factor(rate: float, year: int) -> float:
    """Return ``1 / (1 + rate) ** year``."""
    return 1.0 / (1.0 + rate) ** year


def _annuity_factor(rate: float, years: int) -> float:
    """Present-value annuity factor: sum of discount factors for years 1..N."""
    if rate == 0:
        return float(years)
    return sum(_discount_factor(rate, y) for y in range(1, years + 1))


def _get_component(
    components: dict[str, dict], key: str
) -> dict[str, Any] | None:
    """Return the config dict for *key*, or ``None`` if absent."""
    return components.get(key)


# ======================================================================
# Capital costs
# ======================================================================

def _capital_costs(components: dict[str, dict]) -> dict[str, float]:
    """Compute upfront capital cost for each component type.

    Each component config is expected to carry a ``capital_cost`` key
    (total $) or ``capital_cost_per_kw`` / ``capital_cost_per_kwh`` that
    is multiplied by the relevant capacity field.
    """
    costs: dict[str, float] = {}

    for comp_type, cfg in components.items():
        if "capital_cost" in cfg:
            costs[comp_type] = float(cfg["capital_cost"])
        elif "capital_cost_per_kw" in cfg:
            capacity = float(cfg.get("capacity_kw", cfg.get("rated_power_kw", 0)))
            costs[comp_type] = float(cfg["capital_cost_per_kw"]) * capacity
        elif "capital_cost_per_kwh" in cfg:
            capacity = float(cfg.get("capacity_kwh", 0))
            costs[comp_type] = float(cfg["capital_cost_per_kwh"]) * capacity
        else:
            costs[comp_type] = 0.0

    return costs


# ======================================================================
# O&M costs
# ======================================================================

def _om_annual(components: dict[str, dict]) -> dict[str, float]:
    """Annual operations & maintenance cost for each component.

    Recognises ``om_cost_annual`` (flat $) or ``om_cost_per_kw_year``
    multiplied by rated capacity.
    """
    costs: dict[str, float] = {}

    for comp_type, cfg in components.items():
        if "om_cost_annual" in cfg:
            costs[comp_type] = float(cfg["om_cost_annual"])
        elif "om_cost_per_kw_year" in cfg:
            capacity = float(cfg.get("capacity_kw", cfg.get("rated_power_kw", 0)))
            costs[comp_type] = float(cfg["om_cost_per_kw_year"]) * capacity
        else:
            costs[comp_type] = 0.0

    return costs


# ======================================================================
# Fuel costs
# ======================================================================

def _annual_fuel_cost(
    results: dict, components: dict[str, dict], fuel_escalation: float
) -> tuple[float, float]:
    """Return (base_year_fuel_cost, fuel_litres_per_year).

    If generator results contain ``fuel_consumed_l`` (ndarray of hourly
    litres) and the component config has ``fuel_price``, compute the
    annual fuel bill.  ``fuel_escalation`` is applied year-over-year
    during discounting in the caller.
    """
    gen_cfg = _get_component(components, "diesel_generator")
    if gen_cfg is None:
        return 0.0, 0.0

    fuel_price = float(gen_cfg.get("fuel_price", 1.20))

    fuel_arr = results.get("generator_fuel_l")
    if fuel_arr is not None:
        fuel_arr = np.asarray(fuel_arr, dtype=np.float64)
        annual_litres = float(np.sum(fuel_arr))
    else:
        annual_litres = float(results.get("total_fuel_l", 0.0))

    return annual_litres * fuel_price, annual_litres


# ======================================================================
# Grid costs (import cost minus export revenue) for one year
# ======================================================================

def _annual_grid_cost(results: dict) -> float:
    """Net annual grid cost: import costs minus export revenue."""
    import_cost = float(results.get("grid_import_cost", 0.0))
    export_revenue = float(results.get("grid_export_revenue", 0.0))
    return import_cost - export_revenue


# ======================================================================
# Battery replacement
# ======================================================================

def _battery_replacement_years(
    components: dict[str, dict],
    lifetime_years: int,
) -> list[int]:
    """Estimate years in which battery must be replaced.

    Uses cycle life and annual throughput to estimate when remaining
    capacity drops below ``BATTERY_EOL_THRESHOLD``.  A simple linear
    degradation model is used: replacement every ``replacement_interval``
    years.
    """
    batt_cfg = _get_component(components, "battery")
    if batt_cfg is None:
        return []

    cycle_life = float(batt_cfg.get("cycle_life", 5000))
    capacity_kwh = float(batt_cfg.get("capacity_kwh", 0))
    # Estimate daily cycling depth from typical usage (default 1 cycle/day).
    daily_cycles = float(batt_cfg.get("daily_cycles", 1.0))

    if cycle_life <= 0 or capacity_kwh <= 0 or daily_cycles <= 0:
        return []

    # Years until battery degrades to EOL threshold.
    # At ``daily_cycles`` full equivalent cycles per day, total cycles per
    # year = daily_cycles * 365.  Battery reaches EOL at ``cycle_life``
    # equivalent cycles.  We assume linear capacity fade so threshold of
    # 80 % is reached at cycle_life cycles.
    cycles_per_year = daily_cycles * 365.0
    years_to_eol = cycle_life / cycles_per_year

    replacement_years: list[int] = []
    year = int(np.ceil(years_to_eol))
    while year < lifetime_years:
        replacement_years.append(year)
        year += int(np.ceil(years_to_eol))

    return replacement_years


def _battery_replacement_cost(components: dict[str, dict]) -> float:
    """Cost of a single battery replacement ($)."""
    batt_cfg = _get_component(components, "battery")
    if batt_cfg is None:
        return 0.0

    if "replacement_cost" in batt_cfg:
        return float(batt_cfg["replacement_cost"])

    # Fall back to capital cost (no labour markup).
    if "capital_cost" in batt_cfg:
        return float(batt_cfg["capital_cost"])
    elif "capital_cost_per_kwh" in batt_cfg:
        capacity = float(batt_cfg.get("capacity_kwh", 0))
        return float(batt_cfg["capital_cost_per_kwh"]) * capacity

    return 0.0


# ======================================================================
# Salvage value (linear depreciation)
# ======================================================================

def _salvage_value(
    components: dict[str, dict],
    capital_costs: dict[str, float],
    lifetime_years: int,
) -> float:
    """Residual / salvage value at end of analysis period.

    Uses linear depreciation: salvage = capital * (remaining_life / component_life).
    """
    total_salvage = 0.0

    for comp_type, cfg in components.items():
        comp_life = float(cfg.get("lifetime_years", lifetime_years))
        if comp_life <= 0:
            continue

        cap = capital_costs.get(comp_type, 0.0)

        # How many full replacements fit in the analysis period?
        # The *last* installation year determines remaining life.
        if comp_life >= lifetime_years:
            remaining = comp_life - lifetime_years
        else:
            last_install_year = int(np.floor(lifetime_years / comp_life) * comp_life)
            remaining = (last_install_year + comp_life) - lifetime_years

        salvage_fraction = max(remaining / comp_life, 0.0)
        total_salvage += cap * salvage_fraction

    return total_salvage


# ======================================================================
# IRR calculation
# ======================================================================

def _compute_irr(cash_flows: list[float]) -> float | None:
    """Compute IRR using Brent's method.

    Parameters
    ----------
    cash_flows : list[float]
        Cash flows starting at year 0 (typically negative) through year N.

    Returns
    -------
    float or None
        Internal rate of return, or ``None`` if no valid root is found.
    """
    if brentq is None:
        return None

    def npv_at_rate(r: float) -> float:
        return sum(cf / (1.0 + r) ** t for t, cf in enumerate(cash_flows))

    # Search for a root in a reasonable range.
    try:
        irr = brentq(npv_at_rate, -0.50, 5.0, xtol=1e-8, maxiter=500)
        return float(irr)
    except (ValueError, RuntimeError):
        return None


# ======================================================================
# Main entry point
# ======================================================================

def compute_economics(
    results: dict,
    components: dict[str, dict],
    lifetime_years: int = 25,
    discount_rate: float = 0.08,
) -> dict:
    """Compute comprehensive economic metrics for a power system.

    Parameters
    ----------
    results : dict
        Dispatch simulation results.  Expected keys include:

        * ``load_kw`` -- ndarray (8760,) of served load
        * ``generator_fuel_l`` -- ndarray (8760,) of fuel consumed (L)
        * ``grid_import_kwh`` / ``grid_export_kwh`` -- total annual values
        * ``grid_import_cost`` / ``grid_export_revenue`` -- annual $ values
        * ``unmet_load_kw`` -- ndarray (8760,) of unserved load (optional)

    components : dict[str, dict]
        Component configurations keyed by type (``"solar_pv"``,
        ``"wind_turbine"``, ``"battery"``, ``"diesel_generator"``,
        ``"grid_connection"``).  Each must contain cost parameters.
    lifetime_years : int
        Project analysis period in years.
    discount_rate : float
        Nominal annual discount rate (e.g. 0.08 = 8 %).

    Returns
    -------
    dict
        Keys: ``npc``, ``lcoe``, ``irr``, ``payback_years``,
        ``cost_breakdown``, ``annual_costs``.
    """
    r = discount_rate

    # ------------------------------------------------------------------
    # 1. Capital costs (year 0)
    # ------------------------------------------------------------------
    cap_costs = _capital_costs(components)
    total_capital = sum(cap_costs.values())

    # ------------------------------------------------------------------
    # 2. Annual O&M (discounted over lifetime)
    # ------------------------------------------------------------------
    om_annual = _om_annual(components)
    total_om_annual = sum(om_annual.values())
    om_npv = total_om_annual * _annuity_factor(r, lifetime_years)

    # ------------------------------------------------------------------
    # 3. Fuel costs (discounted with escalation)
    # ------------------------------------------------------------------
    gen_cfg = _get_component(components, "diesel_generator")
    fuel_escalation = float((gen_cfg or {}).get("fuel_escalation", 0.0))

    base_fuel_cost, annual_litres = _annual_fuel_cost(
        results, components, fuel_escalation
    )

    fuel_npv = 0.0
    for yr in range(1, lifetime_years + 1):
        escalated = base_fuel_cost * (1.0 + fuel_escalation) ** (yr - 1)
        fuel_npv += escalated * _discount_factor(r, yr)

    # ------------------------------------------------------------------
    # 4. Grid costs (discounted)
    # ------------------------------------------------------------------
    base_grid_cost = _annual_grid_cost(results)
    grid_npv = base_grid_cost * _annuity_factor(r, lifetime_years)

    # ------------------------------------------------------------------
    # 5. Battery replacement costs
    # ------------------------------------------------------------------
    replacement_years = _battery_replacement_years(components, lifetime_years)
    single_replacement = _battery_replacement_cost(components)
    replacement_npv = sum(
        single_replacement * _discount_factor(r, yr)
        for yr in replacement_years
    )

    # ------------------------------------------------------------------
    # 6. Salvage value (subtracted from NPC)
    # ------------------------------------------------------------------
    salvage = _salvage_value(components, cap_costs, lifetime_years)
    salvage_npv = salvage * _discount_factor(r, lifetime_years)

    # ------------------------------------------------------------------
    # 7. Net Present Cost
    # ------------------------------------------------------------------
    npc = (
        total_capital
        + om_npv
        + fuel_npv
        + grid_npv
        + replacement_npv
        - salvage_npv
    )

    # ------------------------------------------------------------------
    # 8. LCOE = NPC / total discounted energy served
    # ------------------------------------------------------------------
    load_kw = results.get("load_kw")
    if load_kw is not None:
        load_kw = np.asarray(load_kw, dtype=np.float64)
        annual_load_kwh = float(np.sum(load_kw))  # 1-hour timesteps
    else:
        annual_load_kwh = float(results.get("annual_load_kwh", 0.0))

    if annual_load_kwh > 0:
        total_discounted_energy = annual_load_kwh * _annuity_factor(r, lifetime_years)
        lcoe = npc / total_discounted_energy
    else:
        lcoe = 0.0

    # ------------------------------------------------------------------
    # 9. IRR vs grid-only baseline
    # ------------------------------------------------------------------
    # Grid-only annual cost: what it would cost to serve the full load
    # from the grid alone.
    grid_cfg = _get_component(components, "grid_connection") or {}
    grid_buy_rate = float(grid_cfg.get("buy_rate", grid_cfg.get("tariff_buy_rate", 0.12)))
    grid_only_annual = annual_load_kwh * grid_buy_rate

    # Annual savings from the hybrid system.
    annual_operating = total_om_annual + base_fuel_cost + base_grid_cost
    annual_savings = grid_only_annual - annual_operating

    # Build cash flow series for IRR.
    cash_flows = [-total_capital]
    for yr in range(1, lifetime_years + 1):
        cf = annual_savings
        # Subtract replacement cost in replacement years.
        if yr in replacement_years:
            cf -= single_replacement
        cash_flows.append(cf)

    irr = _compute_irr(cash_flows)

    # ------------------------------------------------------------------
    # 10. Simple payback
    # ------------------------------------------------------------------
    if annual_savings > 0:
        payback_years = total_capital / annual_savings
    else:
        payback_years = float("inf")

    # ------------------------------------------------------------------
    # 11. Cost breakdown
    # ------------------------------------------------------------------
    cost_breakdown = {
        "capital": cap_costs,
        "capital_total": total_capital,
        "om_annual": om_annual,
        "om_npv": om_npv,
        "fuel_annual": base_fuel_cost,
        "fuel_npv": fuel_npv,
        "fuel_litres_annual": annual_litres,
        "grid_annual": base_grid_cost,
        "grid_npv": grid_npv,
        "replacement_years": replacement_years,
        "replacement_cost_each": single_replacement,
        "replacement_npv": replacement_npv,
        "salvage_value": salvage,
        "salvage_npv": salvage_npv,
    }

    # Per-year cost schedule for detailed analysis.
    annual_costs: list[dict[str, float]] = []
    for yr in range(0, lifetime_years + 1):
        entry: dict[str, float] = {"year": yr}
        if yr == 0:
            entry["capital"] = total_capital
            entry["om"] = 0.0
            entry["fuel"] = 0.0
            entry["grid"] = 0.0
            entry["replacement"] = 0.0
            entry["total"] = total_capital
        else:
            escalated_fuel = base_fuel_cost * (1.0 + fuel_escalation) ** (yr - 1)
            repl = single_replacement if yr in replacement_years else 0.0
            year_total = total_om_annual + escalated_fuel + base_grid_cost + repl
            entry["capital"] = 0.0
            entry["om"] = total_om_annual
            entry["fuel"] = escalated_fuel
            entry["grid"] = base_grid_cost
            entry["replacement"] = repl
            entry["total"] = year_total
            entry["discounted_total"] = year_total * _discount_factor(r, yr)
        annual_costs.append(entry)

    return {
        "npc": npc,
        "lcoe": lcoe,
        "irr": irr,
        "payback_years": payback_years,
        "cost_breakdown": cost_breakdown,
        "annual_costs": annual_costs,
    }
