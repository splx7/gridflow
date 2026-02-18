"""PDF report download endpoint."""
import uuid
import zlib

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.rate_limit import report_limiter
from app.models.database import get_db
from app.models.project import Project
from app.models.simulation import Simulation, SimulationResult
from app.models.component import Component
from app.models.user import User
from app.models.bus import Bus
from app.models.branch import Branch

router = APIRouter()

MONTH_HOURS = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]


def _decompress(data: bytes | None) -> list[float] | None:
    if data is None:
        return None
    arr = np.frombuffer(zlib.decompress(data), dtype=np.float64)
    return arr.tolist()


def _compute_summary(
    timeseries: dict, components: list[dict],
) -> dict:
    """Derive summary statistics from 8760 timeseries arrays."""
    ts = timeseries

    def _sum(key: str) -> float:
        arr = ts.get(key)
        if arr and len(arr) == 8760:
            return float(np.sum(arr))
        return 0.0

    def _monthly(key: str) -> list[float]:
        arr = ts.get(key)
        if not arr or len(arr) != 8760:
            return [0.0] * 12
        np_arr = np.array(arr)
        result = []
        offset = 0
        for h in MONTH_HOURS:
            result.append(float(np_arr[offset:offset + h].sum()))
            offset += h
        return result

    load = ts.get("load") or []
    annual_load = _sum("load")
    peak_load = float(np.max(load)) if load and len(load) == 8760 else 0.0

    summary: dict = {
        "annual_load_kwh": annual_load,
        "annual_pv_kwh": _sum("pv_output"),
        "annual_wind_kwh": _sum("wind_output"),
        "annual_gen_kwh": _sum("generator_output"),
        "annual_grid_import_kwh": _sum("grid_import"),
        "annual_grid_export_kwh": _sum("grid_export"),
        "annual_unmet_kwh": _sum("unmet"),
        "annual_curtailed_kwh": _sum("excess"),
        "peak_load_kw": peak_load,
        "monthly_load": _monthly("load"),
        "monthly_pv": _monthly("pv_output"),
        "monthly_wind": _monthly("wind_output"),
        "monthly_gen": _monthly("generator_output"),
        "monthly_grid_import": _monthly("grid_import"),
        "monthly_grid_export": _monthly("grid_export"),
    }

    # ── Battery stats ──
    soc = ts.get("battery_soc")
    batt_power = ts.get("battery_power")

    batt_cap = 0.0
    for c in components:
        if c["component_type"] == "battery":
            batt_cap = float(c.get("config", {}).get("capacity_kwh", 0))
            break

    if soc and len(soc) == 8760 and batt_cap > 0:
        soc_arr = np.array(soc)
        soc_pct = soc_arr / batt_cap * 100
        summary["battery_avg_soc"] = float(np.mean(soc_pct))
        summary["battery_min_soc"] = float(np.min(soc_pct))
        summary["battery_hours_below_20pct"] = int(np.sum(soc_pct < 20))

    if batt_power and len(batt_power) == 8760:
        bp = np.array(batt_power)
        # positive = discharge, negative = charging
        charge = np.maximum(-bp, 0)
        discharge = np.maximum(bp, 0)
        throughput = float(np.sum(charge) + np.sum(discharge)) / 2
        summary["battery_throughput_kwh"] = throughput
        if batt_cap > 0:
            summary["battery_equiv_cycles"] = throughput / batt_cap
        else:
            summary["battery_equiv_cycles"] = 0.0

    # ── Generator stats ──
    gen_output = ts.get("generator_output")
    if gen_output and len(gen_output) == 8760:
        gen_arr = np.array(gen_output)
        running_mask = gen_arr > 0.01
        running_hours = int(np.sum(running_mask))
        summary["gen_running_hours"] = running_hours

        # Count starts (transitions from off to on)
        starts = 0
        for i in range(1, 8760):
            if gen_arr[i] > 0.01 and gen_arr[i - 1] <= 0.01:
                starts += 1
        summary["gen_starts"] = starts

        # Find generator config
        rated_power = 0.0
        fuel_price = 1.20
        fuel_curve_a = 0.0
        fuel_curve_b = 0.25
        for c in components:
            if c["component_type"] == "diesel_generator":
                cfg = c.get("config", {})
                rated_power = float(cfg.get("rated_power_kw", 0))
                fuel_price = float(cfg.get("fuel_price", 1.20))
                fuel_curve_a = float(cfg.get("fuel_curve_intercept", 0.0))
                fuel_curve_b = float(cfg.get("fuel_curve_slope", 0.25))
                break

        if rated_power > 0 and running_hours > 0:
            summary["gen_avg_loading_pct"] = float(
                np.mean(gen_arr[running_mask]) / rated_power * 100
            )
        else:
            summary["gen_avg_loading_pct"] = 0.0

        # Fuel calculation
        if rated_power > 0:
            hourly_fuel = (
                (fuel_curve_a * rated_power + fuel_curve_b * gen_arr)
                * running_mask
            )
            total_fuel = float(np.sum(hourly_fuel))
            summary["gen_total_fuel_l"] = total_fuel
            summary["gen_fuel_cost"] = total_fuel * fuel_price
        else:
            summary["gen_total_fuel_l"] = 0.0
            summary["gen_fuel_cost"] = 0.0

    # ── Grid stats ──
    grid_import = ts.get("grid_import")
    grid_export = ts.get("grid_export")
    if grid_import and len(grid_import) == 8760:
        buy_rate = 0.12
        sell_rate = 0.0
        for c in components:
            if c["component_type"] == "grid_connection":
                cfg = c.get("config", {})
                buy_rate = float(
                    cfg.get("buy_rate", cfg.get("tariff_buy_rate", 0.12))
                )
                sell_rate = float(
                    cfg.get("sell_rate", cfg.get("tariff_sell_rate", 0.0))
                )
                break
        import_total = float(np.sum(grid_import))
        export_total = float(np.sum(grid_export)) if (
            grid_export and len(grid_export) == 8760
        ) else 0.0

        summary["grid_import_cost"] = import_total * buy_rate
        summary["grid_export_revenue"] = export_total * sell_rate
        summary["grid_net_cost"] = (
            summary["grid_import_cost"] - summary["grid_export_revenue"]
        )

    return summary


@router.get(
    "/{simulation_id}/report/pdf",
    summary="Download PDF report",
    description="Generate and download a full feasibility study PDF report for a completed simulation.",
)
async def download_pdf_report(
    simulation_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report_limiter.check(request)
    # Load simulation + result
    result = await db.execute(
        select(Simulation)
        .options(selectinload(Simulation.results))
        .where(Simulation.id == simulation_id)
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

    if not sim.results:
        raise HTTPException(status_code=404, detail="Simulation results not found")

    sr = sim.results

    # Load components
    comp_result = await db.execute(
        select(Component).where(Component.project_id == project.id)
    )
    components = [
        {
            "component_type": c.component_type,
            "name": c.name,
            "config": c.config,
        }
        for c in comp_result.scalars().all()
    ]

    # Load buses
    bus_result = await db.execute(
        select(Bus).where(Bus.project_id == project.id)
    )
    buses = [
        {
            "name": b.name,
            "bus_type": b.bus_type,
            "nominal_voltage_kv": b.nominal_voltage_kv,
            "x_position": b.x_position,
            "y_position": b.y_position,
            "config": b.config,
            "id": str(b.id),
        }
        for b in bus_result.scalars().all()
    ]

    # Load branches (with from/to bus names for SLD labels)
    branch_result = await db.execute(
        select(Branch)
        .options(selectinload(Branch.from_bus), selectinload(Branch.to_bus))
        .where(Branch.project_id == project.id)
    )
    branches_data = [
        {
            "name": br.name,
            "branch_type": br.branch_type,
            "from_bus": br.from_bus.name,
            "to_bus": br.to_bus.name,
            "config": br.config,
        }
        for br in branch_result.scalars().all()
    ]

    economics = {
        "npc": sr.npc,
        "lcoe": sr.lcoe,
        "irr": sr.irr,
        "payback_years": sr.payback_years,
        "renewable_fraction": sr.renewable_fraction,
        "co2_emissions_kg": sr.co2_emissions_kg,
        "cost_breakdown": sr.cost_breakdown or {},
    }

    timeseries = {
        "load": _decompress(sr.ts_load),
        "pv_output": _decompress(sr.ts_pv_output),
        "wind_output": _decompress(sr.ts_wind_output),
        "battery_soc": _decompress(sr.ts_battery_soc),
        "battery_power": _decompress(sr.ts_battery_power),
        "generator_output": _decompress(sr.ts_generator_output),
        "grid_import": _decompress(sr.ts_grid_import),
        "grid_export": _decompress(sr.ts_grid_export),
        "excess": _decompress(sr.ts_excess),
        "unmet": _decompress(sr.ts_unmet),
    }

    summary = _compute_summary(timeseries, components)

    # Detect FREF metadata: check if any component has cyclone_derating_pct
    # or if the project name suggests FREF
    fref_metadata = None
    has_cyclone = any(
        c.get("config", {}).get("cyclone_derating_pct")
        for c in components
    )
    if has_cyclone or "fref" in (project.name or "").lower():
        from engine.economics.fiji_presets import (
            FIJI_PRESETS,
            battery_autonomy_kwh,
            cost_per_household,
            diesel_displacement_pct,
        )

        annual_load = summary.get("annual_load_kwh", 0)
        annual_re = summary.get("annual_pv_kwh", 0) + summary.get("annual_wind_kwh", 0)
        daily_load = annual_load / 365.0 if annual_load > 0 else 0.0
        npc = economics.get("npc", 0)

        fref_metadata = {
            "num_households": 50,
            "cost_per_household": cost_per_household(npc, 50),
            "autonomy_days": 3,
            "required_battery_kwh": battery_autonomy_kwh(daily_load, autonomy_days=3),
            "diesel_displacement_pct": diesel_displacement_pct(annual_re, annual_load),
            "co2_avoided_kg_year": annual_re * 0.3 * FIJI_PRESETS["co2_kg_per_litre_diesel"],
            "cyclone_derating_pct": FIJI_PRESETS["cyclone_derating_pct"],
            "logistics_premium_pct": FIJI_PRESETS["logistics_premium_pct"],
            "fea_tariff_fjd": FIJI_PRESETS["fea_tariff_fjd_per_kwh"],
        }

    from engine.reporting.pdf_report import generate_pdf_report

    pdf_buffer = generate_pdf_report(
        project_name=project.name,
        project_description=project.description,
        project_location=(project.latitude, project.longitude),
        simulation_name=sim.name,
        dispatch_strategy=sim.dispatch_strategy,
        lifetime_years=project.lifetime_years,
        discount_rate=project.discount_rate,
        economics=economics,
        timeseries=timeseries,
        components=components,
        summary=summary,
        network_data=sr.power_flow_summary,
        ts_bus_voltages=sr.ts_bus_voltages,
        sensitivity_results=sr.sensitivity_results,
        buses=buses if buses else None,
        branches=branches_data if branches_data else None,
        fref_metadata=fref_metadata,
    )

    filename = f"gridflow_{project.name}_{sim.name}.pdf".replace(" ", "_")

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
