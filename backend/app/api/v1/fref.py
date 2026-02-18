"""FREF (Fiji Rural Electrification Fund) analysis endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.project import Project
from app.models.simulation import Simulation, SimulationResult
from app.models.user import User

router = APIRouter()


@router.get(
    "/simulations/{simulation_id}/fref-analysis",
    summary="FREF community analysis",
    description="Compute Fiji FREF metrics: cost per household, diesel displacement, "
    "autonomy analysis, CO2 avoided, and smart metering costs.",
)
async def fref_analysis(
    simulation_id: uuid.UUID,
    num_households: int = Query(default=50, ge=1, le=1000),
    autonomy_days: int = Query(default=3, ge=1, le=10),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Load simulation + result
    result = await db.execute(
        select(Simulation).where(Simulation.id == simulation_id)
    )
    sim = result.scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Verify ownership
    proj_result = await db.execute(
        select(Project).where(Project.id == sim.project_id, Project.user_id == user.id)
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    sr_result = await db.execute(
        select(SimulationResult).where(SimulationResult.simulation_id == simulation_id)
    )
    sr = sr_result.scalar_one_or_none()
    if not sr:
        raise HTTPException(status_code=404, detail="Simulation results not found")

    from engine.economics.fiji_presets import (
        FIJI_PRESETS,
        apply_logistics_premium,
        battery_autonomy_kwh,
        cost_per_household,
        cyclone_derating_factor,
        diesel_displacement_pct,
    )

    npc = sr.npc or 0.0
    re_fraction = sr.renewable_fraction or 0.0
    annual_load = 0.0
    if sr.cost_breakdown:
        annual_load = sr.cost_breakdown.get("annual_load_kwh", 0.0)
    if annual_load == 0 and npc > 0:
        # Estimate from LCOE if available
        lcoe = sr.lcoe or 0.0
        if lcoe > 0:
            annual_load = npc / (lcoe * project.lifetime_years) if project.lifetime_years > 0 else 0.0

    # Cost per household
    hh = cost_per_household(npc, num_households, currency=project.currency or "USD")

    # Diesel displacement
    annual_re_kwh = annual_load * re_fraction
    displacement = diesel_displacement_pct(annual_re_kwh, annual_load)

    # Battery autonomy requirement
    daily_load = annual_load / 365.0 if annual_load > 0 else 0.0
    required_battery_kwh = battery_autonomy_kwh(daily_load, autonomy_days=autonomy_days)

    # CO2 avoided (kg/yr) = displaced diesel litres * 2.68 kg CO2/L
    # Diesel consumption rate: ~0.3 L/kWh for small gensets
    diesel_litres_avoided = annual_re_kwh * 0.3
    co2_avoided_kg = diesel_litres_avoided * FIJI_PRESETS["co2_kg_per_litre_diesel"]

    # FEA tariff comparison
    fea_annual_cost = annual_load * FIJI_PRESETS["fea_tariff_fjd_per_kwh"]
    system_lcoe_fjd = (sr.lcoe or 0.0) * FIJI_PRESETS["usd_to_fjd"]
    system_annual_cost_fjd = annual_load * system_lcoe_fjd

    # Smart metering
    smart_meter_total = num_households * FIJI_PRESETS["smart_meter_cost_usd"]

    return {
        "num_households": num_households,
        "autonomy_days": autonomy_days,
        "cost_per_household_usd": round(hh["usd"], 2),
        "cost_per_household_fjd": round(hh["fjd"], 2),
        "diesel_displacement_pct": round(displacement, 1),
        "annual_re_kwh": round(annual_re_kwh, 0),
        "annual_load_kwh": round(annual_load, 0),
        "required_battery_kwh": round(required_battery_kwh, 0),
        "co2_avoided_kg_year": round(co2_avoided_kg, 0),
        "co2_avoided_tonnes_lifetime": round(
            co2_avoided_kg * project.lifetime_years / 1000, 1
        ),
        "fea_tariff_comparison": {
            "fea_annual_cost_fjd": round(fea_annual_cost, 2),
            "system_annual_cost_fjd": round(system_annual_cost_fjd, 2),
            "savings_pct": round(
                max(0, (1 - system_annual_cost_fjd / fea_annual_cost) * 100)
                if fea_annual_cost > 0
                else 0.0,
                1,
            ),
        },
        "smart_metering": {
            "cost_per_household_usd": FIJI_PRESETS["smart_meter_cost_usd"],
            "total_cost_usd": smart_meter_total,
            "total_cost_fjd": smart_meter_total * FIJI_PRESETS["usd_to_fjd"],
        },
        "cyclone_derating_factor": cyclone_derating_factor(),
        "logistics_premium_pct": FIJI_PRESETS["logistics_premium_pct"],
    }
