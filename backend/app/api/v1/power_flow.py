"""Power flow analysis endpoint.

Runs Newton-Raphson AC power flow on the project's network topology.
Synchronous (< 1s for typical microgrid networks < 20 buses).
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
from app.models.load_profile import LoadProfile
from app.models.project import Project
from app.models.user import User
from app.schemas.power_flow import (
    BranchFlowSummary,
    PowerFlowRequest,
    PowerFlowResponse,
    PowerFlowSummary,
    ShortCircuitBus,
    ThermalViolation,
    VoltageViolation,
)

router = APIRouter()


def _decompress(data: bytes) -> np.ndarray:
    return np.frombuffer(zlib.decompress(data), dtype=np.float64)


@router.post("/{project_id}/power-flow", response_model=PowerFlowResponse)
async def run_power_flow(
    project_id: uuid.UUID,
    body: PowerFlowRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate project
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.network_mode != "multi_bus":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Power flow requires multi_bus network mode",
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

    # Import engine modules (avoid top-level import for async context)
    from engine.network.network_model import build_network_from_config
    from engine.network.power_flow import solve_power_flow, dc_power_flow
    from engine.network.short_circuit import calculate_short_circuit
    from engine.network.per_unit import power_to_pu, pf_to_q

    s_base = 1.0
    network = build_network_from_config(buses_config, branches_config, s_base)

    # Apply component generation to buses
    for comp in db_components:
        if comp.bus_id and comp.bus_id in bus_uuid_to_idx:
            idx = bus_uuid_to_idx[comp.bus_id]
            cfg = comp.config or {}
            if comp.component_type == "solar_pv":
                # Use capacity as generation (simplified for snapshot)
                p_kw = cfg.get("capacity_kw", cfg.get("capacity_kwp", 0))
                s_pu = power_to_pu(p_kw, 0, s_base)
                network.buses[idx].p_gen_pu += s_pu.real
            elif comp.component_type == "grid_connection":
                network.buses[idx].bus_type = "slack" if network.buses[idx].bus_type.value == "slack" else network.buses[idx].bus_type

    # Apply load allocations to buses
    for alloc in db_allocations:
        if alloc.bus_id in bus_uuid_to_idx and alloc.load_profile:
            idx = bus_uuid_to_idx[alloc.bus_id]
            # Use average load for snapshot mode
            load_data = _decompress(alloc.load_profile.hourly_kw)
            avg_kw = float(np.mean(load_data)) * alloc.fraction
            q_kvar = pf_to_q(avg_kw, alloc.power_factor)
            s_pu = power_to_pu(avg_kw, q_kvar, s_base)
            network.buses[idx].p_load_pu += s_pu.real
            network.buses[idx].q_load_pu += s_pu.imag

    # Solve power flow
    pf_result = solve_power_flow(network, max_iter=30, tolerance=1e-6)

    # Fallback to DC if NR fails
    if not pf_result.converged:
        pf_result = dc_power_flow(network)

    # Build response
    bus_voltages = {}
    voltage_violations = []
    bus_id_map = {i: db_buses[i] for i in range(len(db_buses))}

    for bus_data in network.buses:
        i = bus_data.index
        db_bus = bus_id_map[i]
        v = float(pf_result.voltage_pu[i])
        bus_voltages[db_bus.name] = round(v, 4)

        if v < bus_data.v_min_pu:
            voltage_violations.append(VoltageViolation(
                bus_id=str(db_bus.id), bus_name=db_bus.name,
                voltage_pu=round(v, 4), limit="low",
            ))
        elif v > bus_data.v_max_pu:
            voltage_violations.append(VoltageViolation(
                bus_id=str(db_bus.id), bus_name=db_bus.name,
                voltage_pu=round(v, 4), limit="high",
            ))

    branch_flows = {}
    thermal_violations = []
    total_loss_kw = 0.0
    total_flow_kw = 0.0

    for bf in pf_result.branch_flows:
        db_br = db_branches[bf.branch_index] if bf.branch_index < len(db_branches) else None
        if not db_br:
            continue

        from_kw = abs(bf.from_p_pu) * s_base * 1000
        to_kw = abs(bf.to_p_pu) * s_base * 1000
        loss_kw = bf.loss_p_pu * s_base * 1000

        # Voltage drop calculation
        from_idx = network.branches[bf.branch_index].from_bus
        to_idx = network.branches[bf.branch_index].to_bus
        vd_pct = abs(
            pf_result.voltage_pu[from_idx] - pf_result.voltage_pu[to_idx]
        ) * 100

        branch_flows[db_br.name] = BranchFlowSummary(
            from_kw=round(from_kw, 1),
            to_kw=round(to_kw, 1),
            loss_kw=round(loss_kw, 2),
            vd_pct=round(vd_pct, 2),
            loading_pct=round(bf.loading_pct, 1),
        )

        total_loss_kw += loss_kw
        total_flow_kw += from_kw

        if bf.loading_pct > 100:
            thermal_violations.append(ThermalViolation(
                branch_id=str(db_br.id),
                branch_name=db_br.name,
                loading_pct=round(bf.loading_pct, 1),
                rating_mva=network.branches[bf.branch_index].rating_mva,
            ))

    # Short circuit
    sc_result = calculate_short_circuit(network)
    short_circuit = {}
    for bus_data in network.buses:
        db_bus = bus_id_map[bus_data.index]
        sc = sc_result.bus_results.get(bus_data.index)
        if sc:
            short_circuit[db_bus.name] = ShortCircuitBus(
                i_sc_ka=sc.i_sc_ka, s_sc_mva=sc.s_sc_mva
            )

    # Summary
    voltages = list(bus_voltages.values())
    min_v = min(voltages) if voltages else 1.0
    max_v = max(voltages) if voltages else 1.0
    worst_bus = min(bus_voltages, key=bus_voltages.get) if bus_voltages else ""
    max_loading = max(
        (bf.loading_pct for bf in pf_result.branch_flows), default=0.0
    )
    losses_pct = (total_loss_kw / total_flow_kw * 100) if total_flow_kw > 0 else 0.0

    return PowerFlowResponse(
        converged=pf_result.converged,
        iterations=pf_result.iterations,
        bus_voltages=bus_voltages,
        branch_flows=branch_flows,
        voltage_violations=voltage_violations,
        thermal_violations=thermal_violations,
        short_circuit=short_circuit,
        summary=PowerFlowSummary(
            min_voltage_pu=round(min_v, 4),
            max_voltage_pu=round(max_v, 4),
            worst_voltage_bus=worst_bus,
            max_branch_loading_pct=round(max_loading, 1),
            total_losses_pct=round(losses_pct, 2),
            total_losses_kw=round(total_loss_kw, 2),
        ),
    )
