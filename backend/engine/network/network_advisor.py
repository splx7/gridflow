"""Network advisor — analyze power flow results and generate recommendations.

Pure Python module (no DB dependencies). Takes power flow results and
network configuration to produce actionable recommendations.
"""

from __future__ import annotations

import math

from engine.network.cable_library import filter_cables


def analyze_power_flow(
    pf_result: dict,
    buses: list[dict],
    branches: list[dict],
    cable_material: str = "Cu",
) -> list[dict]:
    """Analyze power flow results and return recommendations.

    Args:
        pf_result: Power flow result dict with keys:
            converged, bus_voltages, branch_flows, summary,
            voltage_violations, thermal_violations
        buses: list of bus dicts (must include "id" key when available)
        branches: list of branch dicts (must include "id" key when available)
        cable_material: "Cu" or "Al" for upgrade suggestions

    Returns:
        list of recommendation dicts with level, code, message, suggestion, action
    """
    recommendations: list[dict] = []

    if not pf_result.get("converged", False):
        recommendations.append({
            "level": "error",
            "code": "PF_DIVERGED",
            "message": "Power flow did not converge",
            "suggestion": "Check network topology and component ratings. Ensure slack bus is properly defined.",
            "action": None,
        })
        return recommendations

    summary = pf_result.get("summary", {})
    bus_voltages = pf_result.get("bus_voltages", {})
    branch_flows = pf_result.get("branch_flows", {})
    voltage_violations = pf_result.get("voltage_violations", [])
    thermal_violations = pf_result.get("thermal_violations", [])

    # Build lookup: bus name -> bus dict
    bus_by_name: dict[str, dict] = {}
    for b in buses:
        bus_by_name[b.get("name", "")] = b

    # Build lookup: branch name -> branch dict
    branch_by_name: dict[str, dict] = {}
    for br in branches:
        branch_by_name[br.get("name", "")] = br

    # Voltage violations
    for vv in voltage_violations:
        v_pu = vv.get("voltage_pu", 1.0)
        bus_name = vv.get("bus_name", "Unknown")
        limit_type = vv.get("limit", "low")

        if limit_type == "low":
            # Find the branch feeding this bus for a cable upgrade action
            action = _voltage_low_action(bus_name, v_pu, branches, branch_flows, cable_material)
            min_pct = 95.0
            recommendations.append({
                "level": "error" if v_pu < 0.90 else "warning",
                "code": "VOLTAGE_LOW",
                "message": (
                    f"Bus '{bus_name}' voltage {v_pu * 100:.1f}% "
                    f"(minimum {min_pct:.0f}%)"
                ),
                "suggestion": "Upgrade feeder cable to reduce voltage drop, or add local reactive compensation",
                "action": action,
            })
        else:
            recommendations.append({
                "level": "warning",
                "code": "VOLTAGE_HIGH",
                "message": (
                    f"Bus '{bus_name}' voltage {v_pu * 100:.1f}% "
                    f"(maximum 105%)"
                ),
                "suggestion": "Check transformer tap setting or reduce local generation",
                "action": None,
            })

    # Thermal violations
    for tv in thermal_violations:
        loading = tv.get("loading_pct", 0)
        br_name = tv.get("branch_name", "Unknown")

        # Find branch type and config
        branch_dict = branch_by_name.get(br_name, {})
        branch_cfg = branch_dict.get("config", {})
        branch_type = branch_dict.get("branch_type", "cable")
        branch_id = branch_dict.get("id")

        # Get actual flow from branch_flows
        flow_data = branch_flows.get(br_name, {})
        actual_kw = flow_data.get("from_kw", 0) if isinstance(flow_data, dict) else 0

        if branch_type == "inverter":
            rated_kw = branch_cfg.get("rated_power_kw", 0)
            needed_kw = math.ceil(rated_kw * (loading / 100) * 1.1)
            suggestion = f"Increase inverter capacity from {rated_kw:.0f} kW to {needed_kw} kW"
            action = {
                "type": "update_branch",
                "target_id": str(branch_id) if branch_id else None,
                "target_name": br_name,
                "field": "config.rated_power_kw",
                "old_value": rated_kw,
                "new_value": needed_kw,
                "description": f"Upgrade inverter to {needed_kw} kW",
            } if branch_id else None
            msg = (
                f"Branch '{br_name}' at {loading:.0f}% loading "
                f"— rated {rated_kw:.0f} kW, actual flow {actual_kw:.0f} kW"
            )
        else:
            # Cable / line
            current_ampacity = branch_cfg.get("ampacity_a", 0)
            rated_kw_approx = current_ampacity * branch_cfg.get("nominal_voltage_kv", 0.4) * math.sqrt(3) if current_ampacity else 0
            suggestion = "Upgrade cable to higher ampacity rating"
            action = None

            if current_ampacity > 0:
                needed = current_ampacity * (loading / 100) * 1.25
                vc = "lv"
                upgrades = filter_cables(voltage_class=vc, material=cable_material, min_ampacity=needed)
                if upgrades:
                    best = min(upgrades, key=lambda c: c.ampacity_a)
                    suggestion = f"Upgrade to {best.name} ({best.ampacity_a}A rated)"
                    if branch_id:
                        action = {
                            "type": "update_branch",
                            "target_id": str(branch_id),
                            "target_name": br_name,
                            "field": "config.cable_spec",
                            "old_value": branch_cfg.get("name", "current cable"),
                            "new_value": best.name,
                            "description": f"Upgrade to {best.name} ({best.ampacity_a}A)",
                            "cable_params": {
                                "name": best.name,
                                "r_ohm_per_km": best.r_ohm_per_km,
                                "x_ohm_per_km": best.x_ohm_per_km,
                                "ampacity_a": best.ampacity_a,
                            },
                        }

            msg = (
                f"Branch '{br_name}' at {loading:.0f}% loading "
                f"— ampacity {current_ampacity:.0f}A"
                + (f", flow {actual_kw:.0f} kW" if actual_kw else "")
            )

        recommendations.append({
            "level": "error" if loading > 120 else "warning",
            "code": "THERMAL_OVERLOAD",
            "message": msg,
            "suggestion": suggestion,
            "action": action,
        })

    # Near-thermal warnings (80-100%)
    for br_name, flow in branch_flows.items():
        loading = flow.get("loading_pct", 0) if isinstance(flow, dict) else 0
        if 80 <= loading < 100:
            already_flagged = any(
                r["code"] == "THERMAL_OVERLOAD" and br_name in r["message"]
                for r in recommendations
            )
            if not already_flagged:
                br_dict = branch_by_name.get(br_name, {})
                br_type = br_dict.get("branch_type", "cable")
                if br_type == "inverter":
                    suggestion = "Inverter approaching rated capacity; consider upsizing for thermal headroom"
                else:
                    suggestion = "Monitor closely; consider cable upgrade if load grows"
                recommendations.append({
                    "level": "warning",
                    "code": "THERMAL_APPROACHING",
                    "message": f"Branch '{br_name}' at {loading:.0f}% loading — approaching thermal limit",
                    "suggestion": suggestion,
                    "action": None,
                })

    # Total losses check — separate inverter conversion losses from cable losses
    total_losses_pct = summary.get("total_losses_pct", 0)
    total_loss_kw = summary.get("total_losses_kw", 0)

    # Sum inverter losses from branch flows
    inverter_loss_kw = 0.0
    for br_name, flow in branch_flows.items():
        if isinstance(flow, dict):
            for br in branches:
                if br.get("name") == br_name and br.get("branch_type") == "inverter":
                    inverter_loss_kw += flow.get("loss_kw", 0)
                    break

    cable_loss_kw = total_loss_kw - inverter_loss_kw
    if total_loss_kw > 0:
        cable_losses_pct = total_losses_pct * (cable_loss_kw / total_loss_kw)
    else:
        cable_losses_pct = 0.0

    if inverter_loss_kw > 0 and total_loss_kw > 0:
        inv_pct = total_losses_pct * (inverter_loss_kw / total_loss_kw)
        recommendations.append({
            "level": "info",
            "code": "INVERTER_LOSSES",
            "message": (
                f"Inverter conversion losses: {inverter_loss_kw:.1f} kW "
                f"({inv_pct:.1f}% of generation) — expected for power electronics"
            ),
            "suggestion": "Inverter losses are inherent to DC/AC conversion and cannot be reduced by cable upgrades",
            "action": None,
        })

    if cable_losses_pct > 5:
        recommendations.append({
            "level": "error",
            "code": "HIGH_LOSSES",
            "message": f"Cable/transformer losses {cable_losses_pct:.1f}% exceed 5% (total network: {total_losses_pct:.1f}%)",
            "suggestion": "Review cable sizing across the network; larger cross-sections reduce losses",
            "action": None,
        })
    elif cable_losses_pct > 3:
        recommendations.append({
            "level": "warning",
            "code": "MODERATE_LOSSES",
            "message": f"Cable/transformer losses {cable_losses_pct:.1f}% exceed 3% (total network: {total_losses_pct:.1f}%)",
            "suggestion": "Consider upgrading heavily loaded cables to reduce resistive losses",
            "action": None,
        })

    # All clear
    if not recommendations:
        recommendations.append({
            "level": "info",
            "code": "ALL_CLEAR",
            "message": "No voltage or thermal violations detected",
            "suggestion": "Network is operating within normal limits",
            "action": None,
        })

    return recommendations


def _voltage_low_action(
    bus_name: str,
    v_pu: float,
    branches: list[dict],
    branch_flows: dict,
    cable_material: str,
) -> dict | None:
    """Find the feeder branch to the low-voltage bus and suggest cable upgrade."""
    # Find branches where to_bus name matches (feeder into this bus)
    for br in branches:
        br_name = br.get("name", "")
        br_type = br.get("branch_type", "cable")
        br_id = br.get("id")

        if br_type not in ("cable", "line"):
            continue

        # Check if this branch feeds the affected bus by looking at to_bus index
        # We match by branch name containing bus name or by checking flow data
        flow = branch_flows.get(br_name, {})
        if not isinstance(flow, dict):
            continue

        cfg = br.get("config", {})
        current_ampacity = cfg.get("ampacity_a", 0)
        if current_ampacity <= 0 or not br_id:
            continue

        # Suggest cable with lower resistance to reduce voltage drop
        needed_ampacity = current_ampacity * 1.5  # step up significantly for VD improvement
        upgrades = filter_cables(voltage_class="lv", material=cable_material, min_ampacity=needed_ampacity)
        if upgrades:
            best = min(upgrades, key=lambda c: c.r_ohm_per_km)  # pick lowest resistance
            return {
                "type": "update_branch",
                "target_id": str(br_id),
                "target_name": br_name,
                "field": "config.cable_spec",
                "old_value": cfg.get("name", "current cable"),
                "new_value": best.name,
                "description": f"Upgrade to {best.name} (lower R = {best.r_ohm_per_km} ohm/km)",
                "cable_params": {
                    "name": best.name,
                    "r_ohm_per_km": best.r_ohm_per_km,
                    "x_ohm_per_km": best.x_ohm_per_km,
                    "ampacity_a": best.ampacity_a,
                },
            }

    return None
