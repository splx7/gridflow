"""N-1 Contingency Analysis and Grid Code endpoints.

Provides:
- POST /{project_id}/contingency-analysis: Run N-1 contingency analysis
- GET /grid-codes: List available grid code profiles
- GET /grid-codes/{key}: Get detailed grid code profile
"""

import uuid
import zlib

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.models.database import get_db
from app.models.bus import Bus
from app.models.branch import Branch
from app.models.component import Component
from app.models.load_allocation import LoadAllocation
from app.models.project import Project
from app.models.user import User
from app.schemas.contingency import (
    ContingencyRequest,
    ContingencyResponse,
    GridCodeListResponse,
    GridCodeDetailResponse,
)

router = APIRouter()
grid_codes_router = APIRouter()


def _decompress(data: bytes) -> np.ndarray:
    return np.frombuffer(zlib.decompress(data), dtype=np.float64)


@router.post(
    "/{project_id}/contingency-analysis",
    response_model=ContingencyResponse,
)
async def run_contingency_analysis(
    project_id: uuid.UUID,
    body: ContingencyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run N-1 contingency analysis on the project network.

    Removes each branch one at a time, re-runs power flow, and checks
    for voltage/thermal violations against the specified grid code.
    """
    # Validate project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    if project.network_mode != "multi_bus":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contingency analysis requires multi_bus network mode",
        )

    # Load buses
    buses_result = await db.execute(
        select(Bus).where(Bus.project_id == project_id)
    )
    db_buses = buses_result.scalars().all()
    if not db_buses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No buses defined"
        )

    # Load branches
    branches_result = await db.execute(
        select(Branch).where(Branch.project_id == project_id)
    )
    db_branches = branches_result.scalars().all()
    if not db_branches:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No branches defined — contingency analysis requires at least one branch",
        )

    # Load components with bus assignments
    comp_result = await db.execute(
        select(Component).where(Component.project_id == project_id)
    )
    db_components = comp_result.scalars().all()

    # Load allocations
    alloc_result = await db.execute(
        select(LoadAllocation)
        .where(LoadAllocation.project_id == project_id)
        .options(selectinload(LoadAllocation.load_profile))
    )
    db_allocations = alloc_result.scalars().all()

    # Build bus index map
    bus_uuid_to_idx = {}
    buses_config = []
    for i, bus in enumerate(db_buses):
        bus_uuid_to_idx[bus.id] = i
        buses_config.append({
            "name": bus.name,
            "bus_type": bus.bus_type,
            "nominal_voltage_kv": bus.nominal_voltage_kv,
            "config": bus.config or {},
        })

    # Build branches config
    branches_config = []
    for br in db_branches:
        if br.from_bus_id not in bus_uuid_to_idx or br.to_bus_id not in bus_uuid_to_idx:
            continue
        branches_config.append({
            "name": br.name,
            "branch_type": br.branch_type,
            "from_bus_idx": bus_uuid_to_idx[br.from_bus_id],
            "to_bus_idx": bus_uuid_to_idx[br.to_bus_id],
            "config": br.config or {},
        })

    # Import engine modules (avoid top-level for async context)
    from engine.network.network_model import build_network_from_config
    from engine.network.per_unit import power_to_pu, pf_to_q
    from engine.network.contingency import run_contingency_analysis as engine_contingency
    from engine.network.grid_codes import get_profile, build_custom_profile

    s_base = 1.0
    network = build_network_from_config(buses_config, branches_config, s_base)

    # Apply component generation to buses (snapshot: use rated capacity)
    for comp in db_components:
        if comp.bus_id and comp.bus_id in bus_uuid_to_idx:
            idx = bus_uuid_to_idx[comp.bus_id]
            cfg = comp.config or {}
            if comp.component_type == "solar_pv":
                p_kw = cfg.get("capacity_kw", cfg.get("capacity_kwp", 0))
                s_pu = power_to_pu(p_kw, 0, s_base)
                network.buses[idx].p_gen_pu += s_pu.real
            elif comp.component_type == "grid_connection":
                pass  # slack bus already set

    # Apply load allocations to buses
    for alloc in db_allocations:
        if alloc.bus_id in bus_uuid_to_idx and alloc.load_profile:
            idx = bus_uuid_to_idx[alloc.bus_id]
            load_data = _decompress(alloc.load_profile.hourly_kw)
            avg_kw = float(np.mean(load_data)) * alloc.fraction
            q_kvar = pf_to_q(avg_kw, alloc.power_factor)
            s_pu = power_to_pu(avg_kw, q_kvar, s_base)
            network.buses[idx].p_load_pu += s_pu.real
            network.buses[idx].q_load_pu += s_pu.imag

    # Resolve grid code profile
    if body.grid_code == "custom" and body.custom_profile:
        grid_code = build_custom_profile(body.custom_profile)
    else:
        try:
            grid_code = get_profile(body.grid_code)
        except KeyError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    # Run contingency analysis
    ca_result = engine_contingency(network, grid_code=grid_code)
    result_dict = ca_result.to_dict()

    return ContingencyResponse(**result_dict)


@grid_codes_router.get(
    "/grid-codes",
    response_model=GridCodeListResponse,
)
async def list_grid_codes(
    user: User = Depends(get_current_user),
):
    """List all available grid code profiles."""
    from engine.network.grid_codes import list_profiles
    profiles = list_profiles()
    return GridCodeListResponse(profiles=profiles)


@grid_codes_router.get(
    "/grid-codes/{key}",
    response_model=GridCodeDetailResponse,
)
async def get_grid_code_detail(
    key: str,
    user: User = Depends(get_current_user),
):
    """Get detailed information for a specific grid code profile."""
    from engine.network.grid_codes import get_profile

    try:
        profile = get_profile(key)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return GridCodeDetailResponse(**profile.to_dict())
