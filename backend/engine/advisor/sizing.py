"""
Rule-based system sizing advisor.

Generates 3 candidate system configurations (Conservative / Balanced / Aggressive)
based on load profile characteristics and user goals.  Pure arithmetic — no
simulation, no web dependencies, <100 ms target.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Cost constants (mirrors frontend COMPONENT_DEFAULTS)
# ---------------------------------------------------------------------------
PV_COST_PER_KW = 1_000        # $/kW capital
PV_OM_PER_KW_YEAR = 15        # $/kW/yr O&M
PV_LIFETIME = 25

BATTERY_COST_PER_KWH = 300    # $/kWh capital
BATTERY_REPLACE_PER_KWH = 200
BATTERY_OM_PER_KWH_YEAR = 5
BATTERY_LIFETIME = 10

GEN_COST_PER_KW = 500         # $/kW capital
GEN_OM_PER_HOUR = 2.0
GEN_LIFETIME_HOURS = 15_000
GEN_FUEL_PRICE = 1.0          # $/L

GRID_BUY_RATE = 0.12          # $/kWh
GRID_SELL_RATE = 0.05

DISCOUNT_RATE = 0.08
PROJECT_LIFETIME = 25


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class GoalWeights:
    cost: int = 3        # 1-5
    renewables: int = 3
    reliability: int = 3
    roi: int = 3


@dataclass
class LoadSummary:
    annual_kwh: float
    peak_kw: float
    daytime_fraction: float   # fraction of load between 06:00-18:00


@dataclass
class SolarResource:
    peak_sun_hours: float     # kWh/m²/day (≈ equivalent sun hours)
    estimated_cf: float       # capacity factor


@dataclass
class ComponentSpec:
    component_type: str
    name: str
    config: dict


@dataclass
class Estimates:
    estimated_npc: float
    estimated_lcoe: float
    estimated_renewable_fraction: float
    estimated_payback_years: float | None
    estimated_capital_cost: float
    estimated_co2_reduction_pct: float


@dataclass
class GoalScores:
    cost: float
    renewables: float
    reliability: float
    roi: float


@dataclass
class Recommendation:
    name: str
    description: str
    best_for: str
    components: list[ComponentSpec]
    estimates: Estimates
    goal_scores: GoalScores


@dataclass
class AdvisorResult:
    recommendations: list[Recommendation]
    load_summary: LoadSummary
    solar_resource: SolarResource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def estimate_peak_sun_hours(latitude: float) -> float:
    """Rough PSH estimate from latitude.  Tropical ~5.5, temperate ~3.5."""
    abs_lat = abs(latitude)
    if abs_lat <= 15:
        return 5.5
    elif abs_lat <= 30:
        return 5.5 - (abs_lat - 15) * 0.1   # 5.5 → 4.0
    elif abs_lat <= 45:
        return 4.0 - (abs_lat - 30) * 0.05   # 4.0 → 3.25
    elif abs_lat <= 60:
        return 3.25 - (abs_lat - 45) * 0.05  # 3.25 → 2.5
    else:
        return 2.5


def _annuity_factor(rate: float, years: int) -> float:
    """Present value of annuity factor."""
    if rate == 0:
        return float(years)
    return (1 - (1 + rate) ** -years) / rate


def _pv_annual_yield(pv_kw: float, psh: float) -> float:
    """Estimated annual PV generation (kWh) with system losses."""
    return pv_kw * psh * 365 * 0.85  # 15% total system losses


def _estimate_economics(
    pv_kw: float,
    battery_kwh: float,
    gen_kw: float,
    grid: bool,
    annual_kwh: float,
    psh: float,
    lifetime: int = PROJECT_LIFETIME,
    discount_rate: float = DISCOUNT_RATE,
) -> Estimates:
    """Quick NPC / LCOE / payback / RE% estimation."""
    # Capital
    pv_capex = pv_kw * PV_COST_PER_KW
    batt_capex = battery_kwh * BATTERY_COST_PER_KWH
    gen_capex = gen_kw * GEN_COST_PER_KW
    total_capex = pv_capex + batt_capex + gen_capex

    # Annual O&M
    pv_om = pv_kw * PV_OM_PER_KW_YEAR
    batt_om = battery_kwh * BATTERY_OM_PER_KWH_YEAR
    # Generator runs to fill unmet — rough hours estimate
    pv_gen = _pv_annual_yield(pv_kw, psh)
    re_fraction = min(pv_gen / annual_kwh, 1.0) if annual_kwh > 0 else 0
    unmet_kwh = max(0, annual_kwh - pv_gen)

    gen_hours = 0.0
    gen_fuel_cost = 0.0
    gen_om_annual = 0.0
    if gen_kw > 0 and unmet_kwh > 0:
        gen_hours = min(unmet_kwh / (gen_kw * 0.75), 8760)
        gen_fuel_cost = gen_hours * gen_kw * 0.3 * GEN_FUEL_PRICE  # ~0.3 L/kWh
        gen_om_annual = gen_hours * GEN_OM_PER_HOUR

    grid_cost = 0.0
    if grid:
        grid_import = max(0, unmet_kwh - (gen_kw * gen_hours * 0.75 if gen_kw > 0 else 0))
        grid_cost = grid_import * GRID_BUY_RATE

    total_annual_om = pv_om + batt_om + gen_om_annual + gen_fuel_cost + grid_cost

    # Battery replacement (once at year 10)
    batt_replace_pv = 0.0
    if battery_kwh > 0 and lifetime > BATTERY_LIFETIME:
        batt_replace_pv = battery_kwh * BATTERY_REPLACE_PER_KWH / (1 + discount_rate) ** BATTERY_LIFETIME

    # NPC
    af = _annuity_factor(discount_rate, lifetime)
    npc = total_capex + total_annual_om * af + batt_replace_pv

    # LCOE
    total_energy_pv = annual_kwh * af
    lcoe = npc / total_energy_pv if total_energy_pv > 0 else 0

    # Simple payback (vs grid-only baseline)
    if grid:
        annual_grid_baseline = annual_kwh * GRID_BUY_RATE
        annual_savings = annual_grid_baseline - total_annual_om
        payback = total_capex / annual_savings if annual_savings > 0 else None
    else:
        payback = None

    co2_reduction = re_fraction * 100

    return Estimates(
        estimated_npc=round(npc, 0),
        estimated_lcoe=round(lcoe, 4),
        estimated_renewable_fraction=round(re_fraction, 3),
        estimated_payback_years=round(payback, 1) if payback is not None else None,
        estimated_capital_cost=round(total_capex, 0),
        estimated_co2_reduction_pct=round(co2_reduction, 1),
    )


def _goal_adjustment(goals: GoalWeights) -> tuple[float, float, float]:
    """Return multipliers for (pv, battery, generator) based on goal weights."""
    # Normalize to [-1, 1] range from 1-5 scale
    cost_bias = (goals.cost - 3) / 2       # high = smaller system
    re_bias = (goals.renewables - 3) / 2    # high = bigger PV/battery
    rel_bias = (goals.reliability - 3) / 2  # high = more battery/gen
    roi_bias = (goals.roi - 3) / 2          # high = optimize self-consumption

    # PV multiplier: +renewables, +roi, -cost
    pv_mult = 1.0 + 0.15 * (re_bias + roi_bias * 0.5 - cost_bias * 0.5)

    # Battery multiplier: +renewables, +reliability, -cost
    batt_mult = 1.0 + 0.15 * (re_bias * 0.5 + rel_bias - cost_bias * 0.5)

    # Generator multiplier: +reliability, -renewables
    gen_mult = 1.0 + 0.15 * (rel_bias - re_bias * 0.5)

    # Clamp to ±30%
    pv_mult = max(0.7, min(1.3, pv_mult))
    batt_mult = max(0.7, min(1.3, batt_mult))
    gen_mult = max(0.7, min(1.3, gen_mult))

    return pv_mult, batt_mult, gen_mult


def _build_components(
    pv_kw: float,
    battery_kwh: float,
    gen_kw: float,
    grid: bool,
    latitude: float,
) -> list[ComponentSpec]:
    """Build component spec list."""
    components: list[ComponentSpec] = []

    if pv_kw > 0:
        # Optimal tilt ≈ abs(latitude), azimuth 180 for N hemisphere, 0 for S
        tilt = round(min(abs(latitude), 45), 1)
        azimuth = 180 if latitude >= 0 else 0
        components.append(ComponentSpec(
            component_type="solar_pv",
            name="Solar PV",
            config={
                "type": "solar_pv",
                "capacity_kwp": round(pv_kw, 1),
                "tilt_deg": tilt,
                "azimuth_deg": azimuth,
                "module_type": "mono-si",
                "inverter_efficiency": 0.96,
                "system_losses": 0.14,
                "capital_cost_per_kw": PV_COST_PER_KW,
                "om_cost_per_kw_year": PV_OM_PER_KW_YEAR,
                "lifetime_years": PV_LIFETIME,
                "derating_factor": 0.005,
            },
        ))

    if battery_kwh > 0:
        c_rate = 0.5  # typical C/2 rate
        charge_rate = round(battery_kwh * c_rate, 1)
        components.append(ComponentSpec(
            component_type="battery",
            name="Battery Storage",
            config={
                "type": "battery",
                "capacity_kwh": round(battery_kwh, 1),
                "max_charge_rate_kw": charge_rate,
                "max_discharge_rate_kw": charge_rate,
                "round_trip_efficiency": 0.9,
                "min_soc": 0.2,
                "max_soc": 1.0,
                "initial_soc": 0.5,
                "chemistry": "nmc",
                "cycle_life": 5000,
                "capital_cost_per_kwh": BATTERY_COST_PER_KWH,
                "replacement_cost_per_kwh": BATTERY_REPLACE_PER_KWH,
                "om_cost_per_kwh_year": BATTERY_OM_PER_KWH_YEAR,
                "lifetime_years": BATTERY_LIFETIME,
            },
        ))

    if gen_kw > 0:
        components.append(ComponentSpec(
            component_type="diesel_generator",
            name="Diesel Backup",
            config={
                "type": "diesel_generator",
                "rated_power_kw": round(gen_kw, 1),
                "min_load_ratio": 0.25,
                "fuel_curve_a0": 0.246,
                "fuel_curve_a1": 0.08145,
                "fuel_price_per_liter": GEN_FUEL_PRICE,
                "capital_cost_per_kw": GEN_COST_PER_KW,
                "om_cost_per_hour": GEN_OM_PER_HOUR,
                "lifetime_hours": GEN_LIFETIME_HOURS,
                "start_cost": 5.0,
            },
        ))

    if grid:
        components.append(ComponentSpec(
            component_type="grid_connection",
            name="Grid Connection",
            config={
                "type": "grid_connection",
                "max_import_kw": 1_000_000,
                "max_export_kw": 1_000_000,
                "sell_back_enabled": True,
                "net_metering": False,
                "buy_rate": GRID_BUY_RATE,
                "sell_rate": GRID_SELL_RATE,
                "demand_charge": 0,
            },
        ))

    return components


def _score_recommendation(
    re_fraction: float,
    capital_cost: float,
    payback: float | None,
    annual_kwh: float,
    gen_kw: float,
    battery_kwh: float,
    peak_kw: float,
) -> GoalScores:
    """Score how well a recommendation matches each goal (0-1)."""
    # Cost score: lower capital = higher score
    max_capex = annual_kwh * 0.5  # rough ceiling for normalization
    cost_score = max(0, 1 - capital_cost / max_capex) if max_capex > 0 else 0.5

    # Renewables score: directly from RE fraction
    renewables_score = re_fraction

    # Reliability score: battery autonomy hours + gen backup
    autonomy_hours = (battery_kwh * 0.8) / peak_kw if peak_kw > 0 else 0
    gen_backup = 1.0 if gen_kw > 0 else 0
    reliability_score = min(1.0, autonomy_hours / 12 * 0.7 + gen_backup * 0.3)

    # ROI score: based on payback period
    if payback is not None and payback > 0:
        roi_score = max(0, 1 - payback / 20)  # 0-year = 1.0, 20-year = 0.0
    else:
        roi_score = 0.3  # no grid = no payback comparison

    return GoalScores(
        cost=round(cost_score, 3),
        renewables=round(renewables_score, 3),
        reliability=round(reliability_score, 3),
        roi=round(roi_score, 3),
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_recommendations(
    annual_kwh: float,
    peak_kw: float,
    daytime_fraction: float,
    latitude: float,
    goals: GoalWeights | None = None,
    grid_available: bool = True,
    budget_ceiling: float | None = None,
    psh_override: float | None = None,
) -> AdvisorResult:
    """
    Generate 3 system recommendations: Conservative, Balanced, Aggressive.

    Args:
        annual_kwh: Annual energy demand in kWh.
        peak_kw: Peak load in kW.
        daytime_fraction: Fraction of energy consumed 06:00-18:00.
        latitude: Project latitude (for PSH estimation and tilt).
        goals: User preference weights (1-5 each axis).
        grid_available: Whether grid connection is available.
        budget_ceiling: Optional max capital budget in $.
        psh_override: Override automatic PSH estimation.

    Returns:
        AdvisorResult with 3 recommendations.
    """
    if goals is None:
        goals = GoalWeights()

    psh = psh_override or estimate_peak_sun_hours(latitude)
    cf = psh / 24  # capacity factor estimate
    avg_kw = annual_kwh / 8760

    # Goal-based size adjustment
    pv_mult, batt_mult, gen_mult = _goal_adjustment(goals)

    # --- Candidate 1: Conservative (RE ~40%) ---
    c1_pv = (0.40 * annual_kwh) / (psh * 365 * 0.85) * pv_mult
    c1_batt = 2 * avg_kw * batt_mult
    c1_gen = 0.0
    if not grid_available:
        c1_gen = peak_kw * 0.5 * gen_mult

    # --- Candidate 2: Balanced (RE ~70%) ---
    c2_pv = (0.70 * annual_kwh) / (psh * 365 * 0.85) * pv_mult
    c2_batt = 4 * avg_kw * batt_mult
    c2_gen = 0.0
    if not grid_available:
        c2_gen = peak_kw * 0.7 * gen_mult

    # --- Candidate 3: Aggressive (RE ~95%) ---
    c3_pv = (1.20 * annual_kwh) / (psh * 365 * 0.85) * pv_mult
    c3_batt = 8 * peak_kw * batt_mult
    c3_gen = 0.0
    if not grid_available:
        c3_gen = peak_kw * gen_mult  # full backup

    # Budget ceiling enforcement
    candidates_raw = [
        (c1_pv, c1_batt, c1_gen),
        (c2_pv, c2_batt, c2_gen),
        (c3_pv, c3_batt, c3_gen),
    ]
    if budget_ceiling is not None:
        capped = []
        for pv, batt, gen in candidates_raw:
            capex = pv * PV_COST_PER_KW + batt * BATTERY_COST_PER_KWH + gen * GEN_COST_PER_KW
            if capex > budget_ceiling:
                scale = budget_ceiling / capex
                pv *= scale
                batt *= scale
                gen *= scale
            capped.append((pv, batt, gen))
        candidates_raw = capped

    # Build recommendations
    templates = [
        ("Budget Smart", "Lowest upfront cost with meaningful solar savings", "Lowest cost"),
        ("Balanced Green", "Good renewable fraction with reasonable investment", "Best value"),
        ("Maximum Independence", "Near-complete energy independence with high RE fraction", "Highest renewables"),
    ]

    load_summary = LoadSummary(
        annual_kwh=round(annual_kwh, 1),
        peak_kw=round(peak_kw, 2),
        daytime_fraction=round(daytime_fraction, 3),
    )
    solar_resource = SolarResource(
        peak_sun_hours=round(psh, 2),
        estimated_cf=round(cf, 4),
    )

    recommendations: list[Recommendation] = []
    for i, (pv, batt, gen) in enumerate(candidates_raw):
        name, desc, best_for = templates[i]
        comps = _build_components(pv, batt, gen, grid_available, latitude)
        est = _estimate_economics(pv, batt, gen, grid_available, annual_kwh, psh)
        scores = _score_recommendation(
            est.estimated_renewable_fraction,
            est.estimated_capital_cost,
            est.estimated_payback_years,
            annual_kwh,
            gen,
            batt,
            peak_kw,
        )
        recommendations.append(Recommendation(
            name=name,
            description=desc,
            best_for=best_for,
            components=comps,
            estimates=est,
            goal_scores=scores,
        ))

    return AdvisorResult(
        recommendations=recommendations,
        load_summary=load_summary,
        solar_resource=solar_resource,
    )


# ---------------------------------------------------------------------------
# Load profile analysis helpers
# ---------------------------------------------------------------------------

def analyze_load_profile(hourly_kw: list[float]) -> tuple[float, float, float]:
    """
    Compute (annual_kwh, peak_kw, daytime_fraction) from 8760 hourly kW values.
    """
    n = len(hourly_kw)
    if n == 0:
        return 0.0, 0.0, 0.5

    annual_kwh = sum(hourly_kw)  # kW × 1hr = kWh
    peak_kw = max(hourly_kw)

    # Daytime = hours 6-17 of each day (indices 6..17 in each 24h block)
    daytime_kwh = 0.0
    for day in range(n // 24):
        base = day * 24
        for h in range(6, 18):
            if base + h < n:
                daytime_kwh += hourly_kw[base + h]

    daytime_fraction = daytime_kwh / annual_kwh if annual_kwh > 0 else 0.5

    return annual_kwh, peak_kw, daytime_fraction


# ---------------------------------------------------------------------------
# Scenario defaults (mirrors frontend SCENARIO_PRESETS)
# ---------------------------------------------------------------------------

SCENARIO_DEFAULTS: dict[str, tuple[float, float, float]] = {
    # (annual_kwh, peak_kw, daytime_fraction)
    "residential_small": (5_000, 2.1, 0.35),
    "residential_large": (12_000, 5.0, 0.40),
    "commercial_office": (50_000, 20.0, 0.70),
    "commercial_retail": (80_000, 30.0, 0.60),
    "industrial_light": (200_000, 80.0, 0.65),
    "industrial_heavy": (500_000, 180.0, 0.55),
    "agricultural": (30_000, 15.0, 0.75),
    # Developing-country scenarios
    "village_microgrid": (80_000, 25.0, 0.55),
    "health_clinic": (15_000, 5.0, 0.60),
    "school_campus": (25_000, 12.0, 0.80),
    "telecom_tower": (18_000, 2.5, 0.50),
    "small_enterprise": (22_000, 8.0, 0.70),
    "water_pumping": (35_000, 18.0, 0.85),
}
