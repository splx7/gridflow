"""Auto-generate radial network topology from component list.

Pure Python module (no DB dependencies). Takes a list of component dicts
and produces a radial bus/branch topology with automatic cable and
transformer sizing from IEC libraries.
"""

from __future__ import annotations

import math

from engine.network.cable_library import CABLE_LIBRARY, CableSpec, filter_cables
from engine.network.transformer_model import TRANSFORMER_LIBRARY, TransformerSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _component_capacity_kw(comp: dict) -> float:
    """Extract AC-side capacity (kW) from any component type.

    For DC sources (PV, battery), uses inverter_capacity_kw if set,
    otherwise falls back to the DC-side rating.
    """
    cfg = comp.get("config", {})
    ctype = comp.get("component_type", "")
    if ctype == "solar_pv":
        dc_cap = cfg.get("capacity_kw", cfg.get("capacity_kwp", 0))
        inv_cap = cfg.get("inverter_capacity_kw")
        return inv_cap if inv_cap is not None and inv_cap > 0 else dc_cap
    if ctype == "wind_turbine":
        qty = cfg.get("quantity", 1)
        return cfg.get("rated_power_kw", 0) * qty
    if ctype == "diesel_generator":
        return cfg.get("rated_power_kw", 0)
    if ctype == "battery":
        discharge = cfg.get("max_discharge_rate_kw", 0)
        inv_cap = cfg.get("inverter_capacity_kw")
        return inv_cap if inv_cap is not None and inv_cap > 0 else discharge
    if ctype == "inverter":
        return cfg.get("rated_power_kw", 0)
    if ctype == "grid_connection":
        return cfg.get("max_import_kw", 1000)
    return 0


def _select_transformer(
    required_kva: float,
    hv_kv: float,
    lv_kv: float,
) -> TransformerSpec | None:
    """Find smallest standard transformer that meets the required kVA."""
    candidates = [
        t for t in TRANSFORMER_LIBRARY
        if t.rating_kva >= required_kva
        and abs(t.hv_kv - hv_kv) < 1.0
        and abs(t.lv_kv - lv_kv) < 0.1
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda t: t.rating_kva)


def _select_cable(
    current_a: float,
    voltage_class: str,
    material: str,
) -> CableSpec | None:
    """Find smallest standard cable that meets the ampacity requirement."""
    cables = filter_cables(
        voltage_class=voltage_class,
        material=material,
        min_ampacity=current_a,
    )
    if not cables:
        return None
    return min(cables, key=lambda c: c.ampacity_a)


def _current_from_power(p_kw: float, v_kv: float, pf: float = 0.85) -> float:
    """Calculate line current from power: I = P / (sqrt3 × V × PF)."""
    v_v = v_kv * 1000
    if v_v <= 0 or pf <= 0:
        return 0
    return (p_kw * 1000) / (math.sqrt(3) * v_v * pf)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

LARGE_COMPONENT_THRESHOLD_KW = 100


def generate_radial_topology(
    components: list[dict],
    load_profiles: list[dict],
    mv_voltage_kv: float = 11.0,
    lv_voltage_kv: float = 0.4,
    cable_material: str = "Cu",
    default_cable_length_km: float = 0.05,
) -> dict:
    """Generate a radial network topology from project components.

    Args:
        components: list of component dicts with keys:
            id, component_type, name, config
        load_profiles: list of load profile dicts with keys: id, name
        mv_voltage_kv: medium-voltage level (default 11kV)
        lv_voltage_kv: low-voltage level (default 0.4kV)
        cable_material: "Cu" or "Al"
        default_cable_length_km: default cable length (50m)

    Returns:
        dict with buses, branches, component_assignments, load_allocations,
        recommendations
    """
    buses: list[dict] = []
    branches: list[dict] = []
    component_assignments: list[dict] = []
    load_allocations: list[dict] = []
    recommendations: list[dict] = []

    # Classify components
    grid_connections = [c for c in components if c["component_type"] == "grid_connection"]
    generators = [
        c for c in components
        if c["component_type"] in ("solar_pv", "wind_turbine", "diesel_generator")
    ]
    storage = [c for c in components if c["component_type"] == "battery"]
    all_dg = generators + storage  # distributed energy resources

    has_grid = len(grid_connections) > 0

    # -----------------------------------------------------------------------
    # 1. Slack Bus
    # -----------------------------------------------------------------------
    if has_grid:
        gc = grid_connections[0]
        slack_bus = {
            "name": "Grid Bus",
            "bus_type": "slack",
            "nominal_voltage_kv": mv_voltage_kv,
            "x_position": 400,
            "y_position": 0,
            "config": {
                "voltage_setpoint_pu": 1.0,
                "sc_mva": 250,
            },
        }
    else:
        # Off-grid: largest generator becomes slack
        all_gens = generators + storage
        if all_gens:
            largest = max(all_gens, key=_component_capacity_kw)
            slack_name = f"{largest['name']} Bus"
        else:
            slack_name = "Main Bus"
        slack_bus = {
            "name": slack_name,
            "bus_type": "slack",
            "nominal_voltage_kv": lv_voltage_kv,
            "x_position": 400,
            "y_position": 0,
            "config": {
                "voltage_setpoint_pu": 1.0,
            },
        }

    buses.append(slack_bus)
    slack_idx = 0

    # -----------------------------------------------------------------------
    # 2. Main LV Bus
    # -----------------------------------------------------------------------
    main_lv_bus = {
        "name": "Main LV Bus",
        "bus_type": "pq",
        "nominal_voltage_kv": lv_voltage_kv,
        "x_position": 400,
        "y_position": 250,
        "config": {},
    }
    buses.append(main_lv_bus)
    main_lv_idx = 1

    # -----------------------------------------------------------------------
    # 3. Transformer (MV→LV) if grid-connected
    # -----------------------------------------------------------------------
    if has_grid and mv_voltage_kv != lv_voltage_kv:
        # Total capacity = all generators + grid import
        total_gen_kw = sum(_component_capacity_kw(c) for c in generators)
        gc_import = grid_connections[0].get("config", {}).get("max_import_kw", 1000)
        total_capacity_kw = total_gen_kw + gc_import
        required_kva = total_capacity_kw * 1.25  # 25% margin

        tx = _select_transformer(required_kva, mv_voltage_kv, lv_voltage_kv)
        if tx:
            tx_branch = {
                "name": f"TX1 ({tx.name})",
                "branch_type": "transformer",
                "from_bus_idx": slack_idx,
                "to_bus_idx": main_lv_idx,
                "config": {
                    "rating_kva": tx.rating_kva,
                    "impedance_pct": tx.impedance_pct,
                    "x_r_ratio": tx.x_r_ratio,
                    "tap_ratio": 1.0,
                    "vector_group": tx.vector_group,
                },
            }
            branches.append(tx_branch)

            utilisation = (total_capacity_kw / tx.rating_kva) * 100
            recommendations.append({
                "level": "info",
                "code": "TX_SIZING",
                "message": f"Selected {tx.name} ({tx.rating_kva} kVA) at {utilisation:.0f}% utilisation",
                "suggestion": "Adjust transformer if system capacity changes significantly",
            })
            if utilisation > 80:
                recommendations.append({
                    "level": "warning",
                    "code": "TX_HIGH_LOADING",
                    "message": f"Transformer utilisation {utilisation:.0f}% exceeds 80%",
                    "suggestion": "Consider a larger transformer or reducing total generation capacity",
                })
        else:
            # No suitable standard transformer — use generic
            tx_branch = {
                "name": "TX1 (Custom)",
                "branch_type": "transformer",
                "from_bus_idx": slack_idx,
                "to_bus_idx": main_lv_idx,
                "config": {
                    "rating_kva": required_kva,
                    "impedance_pct": 6.0,
                    "x_r_ratio": 10.0,
                    "tap_ratio": 1.0,
                },
            }
            branches.append(tx_branch)
            recommendations.append({
                "level": "warning",
                "code": "TX_CUSTOM",
                "message": f"No standard transformer found for {required_kva:.0f} kVA — using custom parameters",
                "suggestion": "Verify transformer impedance and X/R ratio with manufacturer data",
            })

    elif has_grid and mv_voltage_kv == lv_voltage_kv:
        # Same voltage — direct cable connection
        cable_i = _current_from_power(
            grid_connections[0].get("config", {}).get("max_import_kw", 1000),
            lv_voltage_kv,
        )
        cable = _select_cable(cable_i * 1.25, "lv", cable_material)
        if cable:
            branches.append({
                "name": f"Feeder ({cable.name})",
                "branch_type": "cable",
                "from_bus_idx": slack_idx,
                "to_bus_idx": main_lv_idx,
                "config": {
                    "r_ohm_per_km": cable.r_ohm_per_km,
                    "x_ohm_per_km": cable.x_ohm_per_km,
                    "length_km": default_cable_length_km,
                    "ampacity_a": cable.ampacity_a,
                },
            })

    # -----------------------------------------------------------------------
    # 4. Assign components to buses + create dedicated buses for large ones
    # -----------------------------------------------------------------------
    bus_offset_x = 0

    for comp in components:
        cap_kw = _component_capacity_kw(comp)
        ctype = comp["component_type"]

        if ctype == "grid_connection":
            # Grid connection → slack bus
            component_assignments.append({
                "component_id": comp["id"],
                "bus_idx": slack_idx,
            })
            continue

        if cap_kw >= LARGE_COMPONENT_THRESHOLD_KW:
            # Dedicated bus for large component
            bus_x = 100 + bus_offset_x
            bus_offset_x += 250
            new_bus = {
                "name": f"{comp['name']} Bus",
                "bus_type": "pq",
                "nominal_voltage_kv": lv_voltage_kv,
                "x_position": bus_x,
                "y_position": 500,
                "config": {},
            }
            new_bus_idx = len(buses)
            buses.append(new_bus)

            # Cable from Main LV to dedicated bus
            cable_i = _current_from_power(cap_kw, lv_voltage_kv)
            cable = _select_cable(cable_i * 1.25, "lv", cable_material)
            if cable:
                branches.append({
                    "name": f"Cable to {comp['name']} ({cable.name})",
                    "branch_type": "cable",
                    "from_bus_idx": main_lv_idx,
                    "to_bus_idx": new_bus_idx,
                    "config": {
                        "r_ohm_per_km": cable.r_ohm_per_km,
                        "x_ohm_per_km": cable.x_ohm_per_km,
                        "length_km": default_cable_length_km,
                        "ampacity_a": cable.ampacity_a,
                    },
                })
                recommendations.append({
                    "level": "info",
                    "code": "CABLE_SIZING",
                    "message": f"Selected {cable.name} for {comp['name']} ({cable_i:.0f}A required, {cable.ampacity_a}A rated)",
                    "suggestion": f"Cable utilisation: {cable_i / cable.ampacity_a * 100:.0f}%",
                })
            else:
                # Fallback with generic cable
                branches.append({
                    "name": f"Cable to {comp['name']}",
                    "branch_type": "cable",
                    "from_bus_idx": main_lv_idx,
                    "to_bus_idx": new_bus_idx,
                    "config": {
                        "r_ohm_per_km": 0.1,
                        "x_ohm_per_km": 0.07,
                        "length_km": default_cable_length_km,
                        "ampacity_a": cable_i * 1.5,
                    },
                })
                recommendations.append({
                    "level": "warning",
                    "code": "CABLE_GENERIC",
                    "message": f"No standard cable found for {comp['name']} ({cable_i:.0f}A) — using generic parameters",
                    "suggestion": "Specify actual cable parameters from manufacturer data",
                })

            component_assignments.append({
                "component_id": comp["id"],
                "bus_idx": new_bus_idx,
            })
        else:
            # Small component → Main LV Bus directly
            component_assignments.append({
                "component_id": comp["id"],
                "bus_idx": main_lv_idx,
            })

    # -----------------------------------------------------------------------
    # 5. Load allocations
    # -----------------------------------------------------------------------
    if load_profiles:
        load_allocations.append({
            "bus_idx": main_lv_idx,
            "load_profile_id": load_profiles[0]["id"],
            "name": f"Load @ Main LV Bus",
            "fraction": 1.0,
            "power_factor": 0.85,
        })

    # -----------------------------------------------------------------------
    # 6. Summary recommendations
    # -----------------------------------------------------------------------
    n_buses = len(buses)
    n_branches = len(branches)
    n_large = sum(1 for c in components if _component_capacity_kw(c) >= LARGE_COMPONENT_THRESHOLD_KW and c["component_type"] != "grid_connection")
    n_small = len(components) - n_large - len(grid_connections)

    recommendations.insert(0, {
        "level": "info",
        "code": "TOPOLOGY_SUMMARY",
        "message": (
            f"Generated radial topology: {n_buses} buses, {n_branches} branches. "
            f"{n_large} component(s) on dedicated buses, {n_small} on Main LV Bus."
        ),
        "suggestion": "Review the SLD and adjust bus assignments as needed",
    })

    if not has_grid and not generators:
        recommendations.append({
            "level": "error",
            "code": "NO_SOURCE",
            "message": "No grid connection or generators — system has no power source",
            "suggestion": "Add a grid connection or generator component",
        })

    return {
        "buses": buses,
        "branches": branches,
        "component_assignments": component_assignments,
        "load_allocations": load_allocations,
        "recommendations": recommendations,
    }
