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


DC_SOURCE_TYPES = {"solar_pv", "battery"}
AC_SOURCE_TYPES = {"diesel_generator", "wind_turbine"}


def _inverter_capacity_kw(comp: dict) -> float:
    """Get the inverter AC-side rating for a DC source component."""
    cfg = comp.get("config", {})
    ctype = comp.get("component_type", "")
    inv_cap = cfg.get("inverter_capacity_kw")
    if inv_cap is not None and inv_cap > 0:
        return inv_cap
    if ctype == "solar_pv":
        return cfg.get("capacity_kw", cfg.get("capacity_kwp", 0))
    if ctype == "battery":
        return max(
            cfg.get("max_charge_rate_kw", 0),
            cfg.get("max_discharge_rate_kw", 0),
        )
    return cfg.get("rated_power_kw", 0)


def _inverter_efficiency(comp: dict) -> float:
    """Get inverter efficiency for a DC source component."""
    cfg = comp.get("config", {})
    eff = cfg.get("inverter_efficiency")
    if eff is not None and 0 < eff <= 1:
        return eff
    return 0.96


def generate_radial_topology(
    components: list[dict],
    load_profiles: list[dict],
    mv_voltage_kv: float = 11.0,
    lv_voltage_kv: float = 0.4,
    cable_material: str = "Cu",
    default_cable_length_km: float = 0.05,
) -> dict:
    """Generate an electrically correct radial network topology.

    DC sources (PV, battery) are connected through inverter branches to AC
    buses. AC sources (DG, wind) are connected directly. Off-grid systems
    use a GFM (grid-forming) battery inverter as voltage reference.

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

    # Classify components by DC/AC nature
    grid_connections = [c for c in components if c["component_type"] == "grid_connection"]
    dc_sources = [c for c in components if c["component_type"] in DC_SOURCE_TYPES]
    ac_sources = [c for c in components if c["component_type"] in AC_SOURCE_TYPES]
    batteries = [c for c in components if c["component_type"] == "battery"]
    # Standalone inverter components (not auto-generated)
    standalone_inverters = [c for c in components if c["component_type"] == "inverter"]

    has_grid = len(grid_connections) > 0
    has_battery = len(batteries) > 0

    # -----------------------------------------------------------------------
    # 1. Grid Bus + Transformer  OR  Main AC Bus (off-grid)
    # -----------------------------------------------------------------------
    if has_grid:
        # Grid-connected: Grid Bus (slack, MV) → Transformer → Main LV Bus (pq)
        buses.append({
            "name": "Grid Bus",
            "bus_type": "slack",
            "nominal_voltage_kv": mv_voltage_kv,
            "x_position": 400,
            "y_position": 0,
            "config": {"voltage_setpoint_pu": 1.0, "sc_mva": 250},
        })
        grid_bus_idx = 0

        buses.append({
            "name": "Main LV Bus",
            "bus_type": "pq",
            "nominal_voltage_kv": lv_voltage_kv,
            "x_position": 400,
            "y_position": 200,
            "config": {},
        })
        main_ac_idx = 1

        # Grid connection assigned to Grid Bus
        for gc in grid_connections:
            component_assignments.append({
                "component_id": gc["id"],
                "bus_idx": grid_bus_idx,
            })

        # Transformer between Grid Bus and Main LV Bus
        if mv_voltage_kv != lv_voltage_kv:
            total_gen_kw = sum(_component_capacity_kw(c) for c in dc_sources + ac_sources)
            gc_import = grid_connections[0].get("config", {}).get("max_import_kw", 1000)
            required_kva = (total_gen_kw + gc_import) * 1.25

            tx = _select_transformer(required_kva, mv_voltage_kv, lv_voltage_kv)
            if tx:
                branches.append({
                    "name": f"TX1 ({tx.name})",
                    "branch_type": "transformer",
                    "from_bus_idx": grid_bus_idx,
                    "to_bus_idx": main_ac_idx,
                    "config": {
                        "rating_kva": tx.rating_kva,
                        "impedance_pct": tx.impedance_pct,
                        "x_r_ratio": tx.x_r_ratio,
                        "tap_ratio": 1.0,
                        "vector_group": tx.vector_group,
                    },
                })
                utilisation = (total_gen_kw + gc_import) / tx.rating_kva * 100
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
                branches.append({
                    "name": "TX1 (Custom)",
                    "branch_type": "transformer",
                    "from_bus_idx": grid_bus_idx,
                    "to_bus_idx": main_ac_idx,
                    "config": {
                        "rating_kva": required_kva,
                        "impedance_pct": 6.0,
                        "x_r_ratio": 10.0,
                        "tap_ratio": 1.0,
                    },
                })
                recommendations.append({
                    "level": "warning",
                    "code": "TX_CUSTOM",
                    "message": f"No standard transformer found for {required_kva:.0f} kVA — using custom parameters",
                    "suggestion": "Verify transformer impedance and X/R ratio with manufacturer data",
                })
        else:
            # Same voltage — direct cable
            cable_i = _current_from_power(
                grid_connections[0].get("config", {}).get("max_import_kw", 1000),
                lv_voltage_kv,
            )
            cable = _select_cable(cable_i * 1.25, "lv", cable_material)
            if cable:
                branches.append({
                    "name": f"Feeder ({cable.name})",
                    "branch_type": "cable",
                    "from_bus_idx": grid_bus_idx,
                    "to_bus_idx": main_ac_idx,
                    "config": {
                        "r_ohm_per_km": cable.r_ohm_per_km,
                        "x_ohm_per_km": cable.x_ohm_per_km,
                        "length_km": default_cable_length_km,
                        "ampacity_a": cable.ampacity_a,
                    },
                })
    else:
        # Off-grid: Main AC Bus is the single AC bus
        # Slack assignment: battery present → GFM inverter provides V/f
        #                   no battery → largest DG bus = slack
        buses.append({
            "name": "Main AC Bus",
            "bus_type": "slack",
            "nominal_voltage_kv": lv_voltage_kv,
            "x_position": 400,
            "y_position": 100,
            "config": {"voltage_setpoint_pu": 1.0},
        })
        main_ac_idx = 0

        if has_battery:
            recommendations.append({
                "level": "info",
                "code": "GFM_INVERTER",
                "message": "Battery inverter operates in grid-forming (GFM) mode — provides voltage and frequency reference",
                "suggestion": "Ensure battery capacity is sufficient for transient loads",
            })
        elif ac_sources:
            recommendations.append({
                "level": "info",
                "code": "DG_SLACK",
                "message": "Largest generator provides voltage/frequency reference (no battery for GFM inverter)",
                "suggestion": "Consider adding battery storage for better power quality",
            })

    # -----------------------------------------------------------------------
    # 2. DC sources → Inverter branch → DC Bus
    # -----------------------------------------------------------------------
    dc_bus_x = 100
    for comp in dc_sources:
        ctype = comp["component_type"]
        cfg = comp.get("config", {})
        inv_kw = _inverter_capacity_kw(comp)
        inv_eff = _inverter_efficiency(comp)

        # Create DC bus for this component
        dc_bus = {
            "name": f"{comp['name']} DC Bus",
            "bus_type": "pq",
            "nominal_voltage_kv": lv_voltage_kv,
            "x_position": dc_bus_x,
            "y_position": 450,
            "config": {},
        }
        dc_bus_idx = len(buses)
        buses.append(dc_bus)
        dc_bus_x += 250

        # Inverter branch: Main AC Bus → DC Bus
        is_battery = ctype == "battery"
        bidirectional = is_battery
        if has_grid:
            mode = "GFL"
        else:
            mode = "GFM" if is_battery else "GFL"

        inv_name = f"Inv-{comp['name']}"
        if mode == "GFM":
            inv_name += " (GFM)"

        branches.append({
            "name": inv_name,
            "branch_type": "inverter",
            "from_bus_idx": main_ac_idx,
            "to_bus_idx": dc_bus_idx,
            "config": {
                "rated_power_kw": inv_kw,
                "efficiency": inv_eff,
                "mode": mode,
                "bidirectional": bidirectional,
            },
        })

        recommendations.append({
            "level": "info",
            "code": "INVERTER_SIZING",
            "message": (
                f"{inv_name}: {inv_kw:.0f} kW {mode}"
                f"{' bidirectional' if bidirectional else ''}"
                f", η={inv_eff*100:.0f}%"
            ),
            "suggestion": f"Inverter connects {comp['name']} DC bus to Main AC bus",
        })

        # Assign component to its DC bus
        component_assignments.append({
            "component_id": comp["id"],
            "bus_idx": dc_bus_idx,
        })

    # -----------------------------------------------------------------------
    # 3. AC sources → Cable (large) or direct (small)
    # -----------------------------------------------------------------------
    ac_bus_x = 100 + dc_bus_x  # offset right of DC buses
    for comp in ac_sources:
        cap_kw = _component_capacity_kw(comp)

        if cap_kw >= LARGE_COMPONENT_THRESHOLD_KW:
            # Dedicated AC bus with cable
            ac_bus = {
                "name": f"{comp['name']} Bus",
                "bus_type": "pq",
                "nominal_voltage_kv": lv_voltage_kv,
                "x_position": ac_bus_x,
                "y_position": 450,
                "config": {},
            }
            ac_bus_idx = len(buses)
            buses.append(ac_bus)
            ac_bus_x += 250

            cable_i = _current_from_power(cap_kw, lv_voltage_kv)
            cable = _select_cable(cable_i * 1.25, "lv", cable_material)
            if cable:
                branches.append({
                    "name": f"Cable to {comp['name']} ({cable.name})",
                    "branch_type": "cable",
                    "from_bus_idx": main_ac_idx,
                    "to_bus_idx": ac_bus_idx,
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
                branches.append({
                    "name": f"Cable to {comp['name']}",
                    "branch_type": "cable",
                    "from_bus_idx": main_ac_idx,
                    "to_bus_idx": ac_bus_idx,
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
                "bus_idx": ac_bus_idx,
            })
        else:
            # Small AC source → Main AC Bus directly
            component_assignments.append({
                "component_id": comp["id"],
                "bus_idx": main_ac_idx,
            })

    # -----------------------------------------------------------------------
    # 4. Standalone inverter components → assign to Main AC Bus
    # -----------------------------------------------------------------------
    for comp in standalone_inverters:
        component_assignments.append({
            "component_id": comp["id"],
            "bus_idx": main_ac_idx,
        })

    # -----------------------------------------------------------------------
    # 5. Load allocations
    # -----------------------------------------------------------------------
    if load_profiles:
        load_allocations.append({
            "bus_idx": main_ac_idx,
            "load_profile_id": load_profiles[0]["id"],
            "name": "Load @ Main AC Bus",
            "fraction": 1.0,
            "power_factor": 0.85,
        })

    # -----------------------------------------------------------------------
    # 6. Summary recommendations
    # -----------------------------------------------------------------------
    n_buses = len(buses)
    n_branches = len(branches)
    n_inverters = sum(1 for b in branches if b["branch_type"] == "inverter")
    n_dc = len(dc_sources)
    n_ac = len(ac_sources)

    recommendations.insert(0, {
        "level": "info",
        "code": "TOPOLOGY_SUMMARY",
        "message": (
            f"Generated radial topology: {n_buses} buses, {n_branches} branches "
            f"({n_inverters} inverter{'s' if n_inverters != 1 else ''}, "
            f"{n_dc} DC source{'s' if n_dc != 1 else ''}, "
            f"{n_ac} AC source{'s' if n_ac != 1 else ''})."
        ),
        "suggestion": "Review the SLD — DC sources connect through inverters to AC buses",
    })

    if not has_grid and not ac_sources and not dc_sources:
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
