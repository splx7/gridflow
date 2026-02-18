"""Financing analysis endpoint."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.project import Project
from app.models.simulation import Simulation, SimulationResult
from app.models.user import User
from app.schemas.financing import FinancingParams

from engine.economics.financing import cashflow_projection

router = APIRouter()


@router.post(
    "/{simulation_id}/results/financing",
    summary="Financing analysis",
    description="Compute financing cashflows with debt/equity split, loan amortization, and tax shield.",
)
async def financing_analysis(
    simulation_id: uuid.UUID,
    body: FinancingParams,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get simulation result
    result = await db.execute(
        select(SimulationResult)
        .join(Simulation)
        .join(Project)
        .where(
            SimulationResult.simulation_id == simulation_id,
            Project.user_id == user.id,
        )
    )
    sr = result.scalar_one_or_none()
    if not sr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation results not found",
        )

    # Get project for lifetime/discount rate
    sim_result = await db.execute(
        select(Simulation).where(Simulation.id == simulation_id)
    )
    sim = sim_result.scalar_one()
    proj_result = await db.execute(
        select(Project).where(Project.id == sim.project_id)
    )
    project = proj_result.scalar_one()

    # Compute annual revenue (grid-only baseline savings)
    cost_breakdown = sr.cost_breakdown or {}
    grid_cfg = {}
    config_snapshot = sim.config_snapshot or {}
    for comp in config_snapshot.get("components", {}).values():
        if isinstance(comp, dict) and comp.get("type") == "grid_connection":
            grid_cfg = comp
            break

    buy_rate = float(grid_cfg.get("buy_rate", grid_cfg.get("tariff_buy_rate", 0.12)))
    annual_load = float(cost_breakdown.get("fuel_litres_annual", 0)) * 0  # placeholder
    # Better: use the actual annual load from the result
    # Load is sum of ts_load which is stored compressed, so use cost_breakdown
    # Annual revenue = what it would cost from grid alone
    annual_load_kwh = 0.0
    if sr.ts_load:
        import zlib
        import struct
        raw = zlib.decompress(sr.ts_load)
        n = len(raw) // 8
        load_arr = struct.unpack(f"<{n}d", raw)
        annual_load_kwh = sum(load_arr)

    annual_revenue = annual_load_kwh * buy_rate

    result_data = cashflow_projection(
        cost_breakdown=cost_breakdown,
        lifetime_years=project.lifetime_years,
        discount_rate=project.discount_rate,
        debt_fraction=body.debt_fraction,
        interest_rate=body.interest_rate,
        loan_term=body.loan_term,
        equity_cost=body.equity_cost,
        tax_rate=body.tax_rate,
        om_escalation=body.om_escalation,
        annual_revenue=annual_revenue,
    )

    return {
        "simulation_id": str(simulation_id),
        "lifetime_years": project.lifetime_years,
        "discount_rate": project.discount_rate,
        "params": body.model_dump(),
        "annual_revenue": round(annual_revenue, 2),
        **result_data,
    }
