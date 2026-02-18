"""PDF report download endpoint."""
import uuid
import zlib

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.project import Project
from app.models.simulation import Simulation, SimulationResult
from app.models.component import Component
from app.models.user import User

router = APIRouter()


def _decompress(data: bytes | None) -> list[float] | None:
    if data is None:
        return None
    arr = np.frombuffer(zlib.decompress(data), dtype=np.float64)
    return arr.tolist()


@router.get("/{simulation_id}/report/pdf")
async def download_pdf_report(
    simulation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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

    from engine.reporting.pdf_report import generate_pdf_report

    pdf_buffer = generate_pdf_report(
        project_name=project.name,
        project_location=(project.latitude, project.longitude),
        simulation_name=sim.name,
        dispatch_strategy=sim.dispatch_strategy,
        economics=economics,
        timeseries=timeseries,
        components=components,
        network_data=sr.power_flow_summary,
    )

    filename = f"gridflow_{project.name}_{sim.name}.pdf".replace(" ", "_")

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
