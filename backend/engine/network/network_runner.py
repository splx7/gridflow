"""Network-aware simulation runner.

Wraps the existing copper-plate SimulationRunner with power flow analysis.
Supports snapshot mode (4-12 critical hours) and hourly mode (8760 hours).
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from engine.network.network_model import BusType, NetworkModel, build_network_from_config
from engine.network.power_flow import solve_power_flow, dc_power_flow
from engine.network.short_circuit import calculate_short_circuit
from engine.network.per_unit import power_to_pu, pf_to_q


def run_network_simulation(
    dispatch_results: dict[str, Any],
    buses_config: list[dict],
    branches_config: list[dict],
    component_bus_map: dict[str, int],
    load_allocations: list[dict],
    load_kw: np.ndarray,
    mode: str = "snapshot",
    s_base_mva: float = 1.0,
    progress_callback: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Run power flow analysis on dispatch results.

    Args:
        dispatch_results: output from SimulationRunner.run()
        buses_config: bus definitions for build_network_from_config
        branches_config: branch definitions
        component_bus_map: component_type → bus_index mapping
        load_allocations: list of {bus_idx, fraction, power_factor}
        load_kw: 8760 hourly load array
        mode: "snapshot" or "hourly"
        s_base_mva: system base MVA
        progress_callback: called with progress 0.0~1.0

    Returns:
        dict with power_flow_summary and ts_bus_voltages
    """
    network_base = build_network_from_config(buses_config, branches_config, s_base_mva)

    if mode == "snapshot":
        hours = _select_critical_hours(dispatch_results, load_kw)
    else:
        hours = list(range(len(load_kw)))

    n_hours = len(hours)
    n_buses = network_base.n_bus

    # Results storage
    bus_voltages = np.ones((n_hours, n_buses))
    bus_names = [b.name for b in network_base.buses]

    all_branch_flows = []
    voltage_violations = []
    thermal_violations = []
    converged_count = 0

    # Extract timeseries from dispatch results
    pv_kw = dispatch_results.get("pv_output_kw", np.zeros(8760))
    wind_kw = dispatch_results.get("wind_output_kw", np.zeros(8760))
    gen_kw = dispatch_results.get("generator_kw", np.zeros(8760))
    grid_import_kw = dispatch_results.get("grid_import_kw", np.zeros(8760))

    for step, hour in enumerate(hours):
        # Clone network for this timestep (reset injections)
        network = build_network_from_config(buses_config, branches_config, s_base_mva)

        # Apply generation to buses
        _apply_generation(network, hour, component_bus_map,
                          pv_kw, wind_kw, gen_kw, grid_import_kw, s_base_mva)

        # Apply loads to buses
        _apply_loads(network, hour, load_allocations, load_kw, s_base_mva)

        # Solve power flow
        result = solve_power_flow(network, max_iter=30, tolerance=1e-6)
        if not result.converged:
            result = dc_power_flow(network)
        else:
            converged_count += 1

        # Store voltages
        bus_voltages[step] = result.voltage_pu

        # Check violations
        for bus in network.buses:
            v = result.voltage_pu[bus.index]
            if v < bus.v_min_pu:
                voltage_violations.append({
                    "bus_name": bus.name,
                    "bus_index": bus.index,
                    "hour": hour,
                    "voltage_pu": round(float(v), 4),
                    "limit": "low",
                })
            elif v > bus.v_max_pu:
                voltage_violations.append({
                    "bus_name": bus.name,
                    "bus_index": bus.index,
                    "hour": hour,
                    "voltage_pu": round(float(v), 4),
                    "limit": "high",
                })

        for bf in result.branch_flows:
            if bf.loading_pct > 100:
                thermal_violations.append({
                    "branch_name": bf.branch_name,
                    "branch_index": bf.branch_index,
                    "hour": hour,
                    "loading_pct": round(bf.loading_pct, 1),
                })

        if step == n_hours - 1 or step == 0:
            all_branch_flows.append({
                "hour": hour,
                "flows": [
                    {
                        "branch_name": bf.branch_name,
                        "from_p_kw": round(bf.from_p_pu * s_base_mva * 1000, 1),
                        "loss_kw": round(bf.loss_p_pu * s_base_mva * 1000, 2),
                        "loading_pct": round(bf.loading_pct, 1),
                    }
                    for bf in result.branch_flows
                ],
            })

        if progress_callback and step % max(1, n_hours // 20) == 0:
            progress_callback(step / n_hours)

    # Short circuit analysis (once, at nominal conditions)
    sc_result = calculate_short_circuit(network_base)
    short_circuit = {
        sc.bus_name: {"i_sc_ka": sc.i_sc_ka, "s_sc_mva": sc.s_sc_mva}
        for sc in sc_result.bus_results.values()
    }

    # Build summary
    min_voltages = np.min(bus_voltages, axis=0)
    max_voltages = np.max(bus_voltages, axis=0)
    worst_bus_idx = int(np.argmin(min_voltages))

    # Total losses from last snapshot
    total_losses_kw = sum(
        bf["loss_kw"]
        for snapshot in all_branch_flows
        for bf in snapshot["flows"]
    ) / max(len(all_branch_flows), 1)
    total_load_kw = float(np.mean(load_kw)) if len(load_kw) > 0 else 1.0
    losses_pct = (total_losses_kw / total_load_kw * 100) if total_load_kw > 0 else 0.0

    # Build ts_bus_voltages as dict of bus_name → list of voltages
    ts_bus_voltages = {}
    for i, name in enumerate(bus_names):
        ts_bus_voltages[name] = [round(float(v), 4) for v in bus_voltages[:, i]]

    power_flow_summary = {
        "mode": mode,
        "hours_analyzed": n_hours,
        "converged_count": converged_count,
        "min_voltage_pu": round(float(np.min(bus_voltages)), 4),
        "max_voltage_pu": round(float(np.max(bus_voltages)), 4),
        "worst_voltage_bus": bus_names[worst_bus_idx] if bus_names else "",
        "max_branch_loading_pct": max(
            (bf["loading_pct"] for s in all_branch_flows for bf in s["flows"]),
            default=0.0,
        ),
        "total_losses_pct": round(losses_pct, 2),
        "total_losses_kw": round(total_losses_kw, 2),
        "voltage_violations_count": len(voltage_violations),
        "thermal_violations_count": len(thermal_violations),
        "short_circuit": short_circuit,
        "branch_flows": all_branch_flows,
    }

    return {
        "power_flow_summary": power_flow_summary,
        "ts_bus_voltages": ts_bus_voltages,
    }


def _select_critical_hours(
    results: dict[str, Any], load_kw: np.ndarray
) -> list[int]:
    """Select 4-12 critical hours for snapshot power flow."""
    hours = set()
    n = len(load_kw)

    # Max load hour
    hours.add(int(np.argmax(load_kw)))
    # Min load hour
    hours.add(int(np.argmin(load_kw)))

    # Max generation hours
    pv = results.get("pv_output_kw")
    if pv is not None and len(pv) == n:
        hours.add(int(np.argmax(pv)))

    wind = results.get("wind_output_kw")
    if wind is not None and len(wind) == n:
        hours.add(int(np.argmax(wind)))

    # Max reverse power flow (export) hour
    grid_export = results.get("grid_export_kw")
    if grid_export is not None and len(grid_export) == n:
        hours.add(int(np.argmax(grid_export)))

    # Season peaks (hour 0, 2190, 4380, 6570)
    for h in [0, 2190, 4380, 6570]:
        if h < n:
            hours.add(h)

    # Peak demand at noon (12:00) for each season
    for day_offset in [0, 91, 182, 273]:
        h = day_offset * 24 + 12
        if h < n:
            hours.add(h)

    return sorted(hours)


def _apply_generation(
    network: NetworkModel,
    hour: int,
    component_bus_map: dict[str, int],
    pv_kw: np.ndarray,
    wind_kw: np.ndarray,
    gen_kw: np.ndarray,
    grid_import_kw: np.ndarray,
    s_base_mva: float,
) -> None:
    """Apply generation values from dispatch to network buses."""
    n = len(pv_kw)

    # PV generation
    if "solar_pv" in component_bus_map and hour < n:
        idx = component_bus_map["solar_pv"]
        p = float(pv_kw[hour]) if pv_kw[hour] > 0 else 0.0
        s_pu = power_to_pu(p, 0, s_base_mva)
        network.buses[idx].p_gen_pu += s_pu.real

    # Wind generation
    if "wind_turbine" in component_bus_map and hour < n:
        idx = component_bus_map["wind_turbine"]
        p = float(wind_kw[hour]) if wind_kw[hour] > 0 else 0.0
        s_pu = power_to_pu(p, 0, s_base_mva)
        network.buses[idx].p_gen_pu += s_pu.real

    # Diesel generator
    if "diesel_generator" in component_bus_map and hour < n:
        idx = component_bus_map["diesel_generator"]
        p = float(gen_kw[hour]) if gen_kw[hour] > 0 else 0.0
        s_pu = power_to_pu(p, 0, s_base_mva)
        network.buses[idx].p_gen_pu += s_pu.real


def _apply_loads(
    network: NetworkModel,
    hour: int,
    load_allocations: list[dict],
    load_kw: np.ndarray,
    s_base_mva: float,
) -> None:
    """Apply load allocations to network buses."""
    if hour >= len(load_kw):
        return

    total_load = float(load_kw[hour])

    for alloc in load_allocations:
        bus_idx = alloc["bus_idx"]
        fraction = alloc.get("fraction", 1.0)
        pf = alloc.get("power_factor", 0.85)

        p_kw = total_load * fraction
        q_kvar = pf_to_q(p_kw, pf)
        s_pu = power_to_pu(p_kw, q_kvar, s_base_mva)

        network.buses[bus_idx].p_load_pu += s_pu.real
        network.buses[bus_idx].q_load_pu += s_pu.imag
