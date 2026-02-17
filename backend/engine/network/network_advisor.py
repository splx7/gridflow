"""Network advisor — analyze power flow results and generate recommendations.

Pure Python module (no DB dependencies). Takes power flow results and
network configuration to produce actionable recommendations.
"""

from __future__ import annotations

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
        buses: list of bus dicts
        branches: list of branch dicts
        cable_material: "Cu" or "Al" for upgrade suggestions

    Returns:
        list of recommendation dicts with level, code, message, suggestion
    """
    recommendations: list[dict] = []

    if not pf_result.get("converged", False):
        recommendations.append({
            "level": "error",
            "code": "PF_DIVERGED",
            "message": "Power flow did not converge",
            "suggestion": "Check network topology and component ratings. Ensure slack bus is properly defined.",
        })
        return recommendations

    summary = pf_result.get("summary", {})
    bus_voltages = pf_result.get("bus_voltages", {})
    branch_flows = pf_result.get("branch_flows", {})
    voltage_violations = pf_result.get("voltage_violations", [])
    thermal_violations = pf_result.get("thermal_violations", [])

    # Voltage violations
    for vv in voltage_violations:
        v_pu = vv.get("voltage_pu", 1.0)
        bus_name = vv.get("bus_name", "Unknown")
        limit_type = vv.get("limit", "low")

        if limit_type == "low":
            recommendations.append({
                "level": "error" if v_pu < 0.90 else "warning",
                "code": "VOLTAGE_LOW",
                "message": f"Bus '{bus_name}' voltage {v_pu:.3f} pu ({v_pu * 100:.1f}%) below minimum",
                "suggestion": "Upgrade feeder cable to reduce voltage drop, or add local reactive compensation",
            })
        else:
            recommendations.append({
                "level": "warning",
                "code": "VOLTAGE_HIGH",
                "message": f"Bus '{bus_name}' voltage {v_pu:.3f} pu ({v_pu * 100:.1f}%) above maximum",
                "suggestion": "Check transformer tap setting or reduce local generation",
            })

    # Thermal violations
    for tv in thermal_violations:
        loading = tv.get("loading_pct", 0)
        br_name = tv.get("branch_name", "Unknown")

        # Find branch type and config
        branch_cfg = None
        branch_type = "cable"
        for br in branches:
            if br.get("name") == br_name:
                branch_cfg = br.get("config", {})
                branch_type = br.get("branch_type", "cable")
                break

        if branch_type == "inverter":
            rated_kw = branch_cfg.get("rated_power_kw", 0) if branch_cfg else 0
            needed_kw = rated_kw * (loading / 100) * 1.1
            suggestion = f"Increase inverter capacity from {rated_kw:.0f} kW to ≥{needed_kw:.0f} kW"
        else:
            suggestion = "Upgrade cable to higher ampacity rating"
            if branch_cfg:
                current_ampacity = branch_cfg.get("ampacity_a", 0)
                if current_ampacity > 0:
                    needed = current_ampacity * (loading / 100) * 1.25
                    vc = "lv"  # default
                    upgrades = filter_cables(voltage_class=vc, material=cable_material, min_ampacity=needed)
                    if upgrades:
                        best = min(upgrades, key=lambda c: c.ampacity_a)
                        suggestion = f"Upgrade to {best.name} ({best.ampacity_a}A rated)"

        recommendations.append({
            "level": "error" if loading > 120 else "warning",
            "code": "THERMAL_OVERLOAD",
            "message": f"Branch '{br_name}' at {loading:.0f}% loading (exceeds 100%)",
            "suggestion": suggestion,
        })

    # Near-thermal warnings (80-100%)
    for br_name, flow in branch_flows.items():
        loading = flow.get("loading_pct", 0)
        if 80 <= loading < 100:
            # Not yet a violation, but approaching
            already_flagged = any(
                r["code"] == "THERMAL_OVERLOAD" and br_name in r["message"]
                for r in recommendations
            )
            if not already_flagged:
                # Find branch type for appropriate suggestion
                br_type = "cable"
                for br in branches:
                    if br.get("name") == br_name:
                        br_type = br.get("branch_type", "cable")
                        break
                if br_type == "inverter":
                    suggestion = "Inverter approaching rated capacity; consider upsizing for thermal headroom"
                else:
                    suggestion = "Monitor closely; consider cable upgrade if load grows"
                recommendations.append({
                    "level": "warning",
                    "code": "THERMAL_APPROACHING",
                    "message": f"Branch '{br_name}' at {loading:.0f}% loading — approaching thermal limit",
                    "suggestion": suggestion,
                })

    # Total losses check — separate inverter conversion losses from cable losses
    total_losses_pct = summary.get("total_losses_pct", 0)
    total_loss_kw = summary.get("total_losses_kw", 0)

    # Sum inverter losses from branch flows
    inverter_loss_kw = 0.0
    for br_name, flow in branch_flows.items():
        for br in branches:
            if br.get("name") == br_name and br.get("branch_type") == "inverter":
                inverter_loss_kw += flow.get("loss_kw", 0)
                break

    cable_loss_kw = total_loss_kw - inverter_loss_kw
    # Only flag cable/transformer losses against thresholds
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
        })

    if cable_losses_pct > 5:
        recommendations.append({
            "level": "error",
            "code": "HIGH_LOSSES",
            "message": f"Cable/transformer losses {cable_losses_pct:.1f}% exceed 5% (total network: {total_losses_pct:.1f}%)",
            "suggestion": "Review cable sizing across the network; larger cross-sections reduce losses",
        })
    elif cable_losses_pct > 3:
        recommendations.append({
            "level": "warning",
            "code": "MODERATE_LOSSES",
            "message": f"Cable/transformer losses {cable_losses_pct:.1f}% exceed 3% (total network: {total_losses_pct:.1f}%)",
            "suggestion": "Consider upgrading heavily loaded cables to reduce resistive losses",
        })

    # All clear
    if not recommendations:
        recommendations.append({
            "level": "info",
            "code": "ALL_CLEAR",
            "message": "No voltage or thermal violations detected",
            "suggestion": "Network is operating within normal limits",
        })

    return recommendations
