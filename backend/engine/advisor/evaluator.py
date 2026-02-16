"""
System health evaluator.

Takes a list of component configs + load/solar summaries and returns:
1. Estimated economic metrics (reuses sizing.py math)
2. Power-system warnings (critical / warning / info)

Pure arithmetic — no DB, no web deps, <10 ms.
"""

from __future__ import annotations

from dataclasses import dataclass
from engine.advisor.sizing import (
    _estimate_economics,
    _pv_annual_yield,
    estimate_peak_sun_hours,
    Estimates,
)


@dataclass
class SystemWarning:
    level: str       # "critical" | "warning" | "info"
    code: str
    message: str
    detail: str


@dataclass
class EvaluationResult:
    estimates: Estimates
    warnings: list[SystemWarning]


def _extract(components: list[dict], ctype: str) -> dict | None:
    """Find first component of given type."""
    for c in components:
        if c.get("component_type") == ctype:
            return c.get("config", {})
    return None


def _has_type(components: list[dict], ctype: str) -> bool:
    return any(c.get("component_type") == ctype for c in components)


def evaluate_system(
    components: list[dict],
    annual_kwh: float,
    peak_kw: float,
    daytime_fraction: float,
    peak_sun_hours: float,
) -> EvaluationResult:
    """Evaluate a set of components and return metrics + warnings."""

    pv_cfg = _extract(components, "solar_pv")
    batt_cfg = _extract(components, "battery")
    gen_cfg = _extract(components, "diesel_generator")
    has_grid = _has_type(components, "grid_connection")
    has_wind = _has_type(components, "wind_turbine")

    pv_kw = float(pv_cfg.get("capacity_kwp", 0)) if pv_cfg else 0
    batt_kwh = float(batt_cfg.get("capacity_kwh", 0)) if batt_cfg else 0
    gen_kw = float(gen_cfg.get("rated_power_kw", 0)) if gen_cfg else 0

    estimates = _estimate_economics(
        pv_kw=pv_kw,
        battery_kwh=batt_kwh,
        gen_kw=gen_kw,
        grid=has_grid,
        annual_kwh=annual_kwh,
        psh=peak_sun_hours,
    )

    warnings = check_warnings(
        components=components,
        pv_kw=pv_kw,
        batt_kwh=batt_kwh,
        gen_kw=gen_kw,
        has_grid=has_grid,
        has_wind=has_wind,
        annual_kwh=annual_kwh,
        peak_kw=peak_kw,
        peak_sun_hours=peak_sun_hours,
        daytime_fraction=daytime_fraction,
        batt_cfg=batt_cfg,
        gen_cfg=gen_cfg,
        pv_cfg=pv_cfg,
    )

    return EvaluationResult(estimates=estimates, warnings=warnings)


def check_warnings(
    components: list[dict],
    pv_kw: float,
    batt_kwh: float,
    gen_kw: float,
    has_grid: bool,
    has_wind: bool,
    annual_kwh: float,
    peak_kw: float,
    peak_sun_hours: float,
    daytime_fraction: float,
    batt_cfg: dict | None,
    gen_cfg: dict | None,
    pv_cfg: dict | None,
) -> list[SystemWarning]:
    warnings: list[SystemWarning] = []

    has_pv = pv_kw > 0
    has_batt = batt_kwh > 0
    has_gen = gen_kw > 0
    has_any_gen = has_pv or has_wind or has_gen or has_grid

    avg_kw = annual_kwh / 8760 if annual_kwh > 0 else 0
    usable_batt = batt_kwh * 0.8 if has_batt else 0  # 80% DoD
    autonomy_hours = usable_batt / peak_kw if peak_kw > 0 and has_batt else 0

    # ── CRITICAL ──────────────────────────────────────────────

    if not has_any_gen:
        warnings.append(SystemWarning(
            level="critical",
            code="no_generation",
            message="No generation sources configured",
            detail="Add at least one power source (solar PV, wind, diesel, or grid connection).",
        ))

    if not has_grid and (has_pv or has_wind) and not has_gen and not has_batt:
        warnings.append(SystemWarning(
            level="critical",
            code="offgrid_no_storage",
            message="Off-grid with intermittent sources only — no storage or backup",
            detail="Nighttime or low-wind periods will have no power supply. Add battery storage or a diesel generator.",
        ))

    if has_batt and not has_pv and not has_wind and not has_gen and not has_grid:
        warnings.append(SystemWarning(
            level="critical",
            code="battery_no_charging",
            message="Battery has no charging source",
            detail="Add a generation source (PV, wind, diesel, or grid) to charge the battery.",
        ))

    # ── WARNING ───────────────────────────────────────────────

    if has_batt and autonomy_hours < 2 and not has_grid:
        warnings.append(SystemWarning(
            level="warning",
            code="low_autonomy",
            message=f"Battery autonomy only {autonomy_hours:.1f}h at peak load",
            detail="Consider increasing battery capacity for better reliability during outages.",
        ))

    if not has_grid and has_pv and not has_gen:
        total_gen_kw = pv_kw
        if total_gen_kw < peak_kw * 0.8:
            warnings.append(SystemWarning(
                level="warning",
                code="peak_gen_low",
                message="Peak generation capacity is below peak load",
                detail=f"PV capacity ({pv_kw:.0f} kW) may not cover peak demand ({peak_kw:.0f} kW) even in ideal conditions.",
            ))

    if has_pv and has_batt:
        pv_annual = _pv_annual_yield(pv_kw, peak_sun_hours)
        if pv_annual > annual_kwh * 2 and autonomy_hours < 4:
            warnings.append(SystemWarning(
                level="warning",
                code="pv_oversize_small_battery",
                message="PV oversized relative to battery — significant curtailment likely",
                detail="PV generation exceeds 200% of demand but battery can store less than 4 hours. Consider larger battery or smaller PV.",
            ))

    if not has_grid and not has_gen and has_batt and autonomy_hours < 4:
        warnings.append(SystemWarning(
            level="warning",
            code="offgrid_low_autonomy",
            message="Off-grid without backup — extended outage risk",
            detail=f"Battery autonomy is {autonomy_hours:.1f}h. Consider adding a diesel generator or increasing battery capacity.",
        ))

    if has_gen and gen_cfg:
        lifetime_hours = float(gen_cfg.get("lifetime_hours", 15000))
        # Estimate annual run hours
        pv_annual = _pv_annual_yield(pv_kw, peak_sun_hours) if has_pv else 0
        unmet = max(0, annual_kwh - pv_annual)
        est_annual_hours = min(unmet / (gen_kw * 0.75), 8760) if gen_kw > 0 else 0
        if est_annual_hours * 25 > lifetime_hours:
            warnings.append(SystemWarning(
                level="warning",
                code="gen_lifetime_exceeded",
                message="Diesel generator lifetime may be exceeded within project lifetime",
                detail=f"Estimated {est_annual_hours:.0f} run hours/year × 25 years = {est_annual_hours*25:.0f}h (lifetime: {lifetime_hours:.0f}h).",
            ))

    if has_batt and batt_cfg:
        max_charge = float(batt_cfg.get("max_charge_rate_kw", 0))
        if max_charge > batt_kwh:
            warnings.append(SystemWarning(
                level="warning",
                code="high_c_rate",
                message="Battery charge rate exceeds 1C — may be unrealistic",
                detail=f"Max charge rate ({max_charge:.0f} kW) > capacity ({batt_kwh:.0f} kWh). Typical systems use C/2 or lower.",
            ))

    # ── INFO ──────────────────────────────────────────────────

    if has_pv and not has_batt and has_grid:
        warnings.append(SystemWarning(
            level="info",
            code="add_battery",
            message="Adding battery storage would improve self-consumption",
            detail="Without a battery, excess PV generation is exported at a lower sell rate. A battery captures this for later use.",
        ))

    if has_pv and annual_kwh > 0:
        pv_annual = _pv_annual_yield(pv_kw, peak_sun_hours)
        if pv_annual < annual_kwh * 0.2:
            warnings.append(SystemWarning(
                level="info",
                code="pv_undersize",
                message="PV covers less than 20% of annual demand",
                detail=f"Current PV generates ~{pv_annual:.0f} kWh/yr vs {annual_kwh:.0f} kWh/yr demand. Consider increasing PV capacity.",
            ))

    if has_pv and pv_cfg:
        import math
        tilt = float(pv_cfg.get("tilt_deg", 0))
        # For latitude lookup we don't have it here, but we can estimate optimal tilt ≈ PSH-based
        # Simplified: if tilt is 0 and PSH < 5 → probably not optimized
        if tilt == 0 and peak_sun_hours < 5:
            warnings.append(SystemWarning(
                level="info",
                code="tilt_optimization",
                message="PV tilt angle is 0° — tilting panels may improve output",
                detail="Setting tilt angle approximately equal to your latitude typically improves annual energy yield by 5-15%.",
            ))

    return warnings
