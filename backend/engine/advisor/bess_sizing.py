"""BESS (Battery Energy Storage System) Auto-Sizing Advisor.

Analyzes hourly surplus/deficit from dispatch simulation results to
recommend optimal battery capacity_kwh and max_power_kw.

Targets:
- Maximum 5% unmet load fraction (configurable)
- Minimum 80% renewable energy fraction (configurable)
- Minimize oversizing by iterating capacity in steps

The algorithm:
1. Compute hourly surplus (RE > load) and deficit (load > RE)
2. Calculate the energy that a battery could shift from surplus to deficit hours
3. Size the battery to meet the target constraints
4. Recommend power rating based on peak charge/discharge requirements
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class BESSSizingResult:
    """Recommended BESS configuration."""
    recommended_capacity_kwh: float
    recommended_max_power_kw: float
    recommended_max_charge_kw: float
    recommended_max_discharge_kw: float
    # Projected performance with the recommended battery
    projected_unmet_fraction: float
    projected_re_fraction: float
    projected_shifted_kwh: float  # energy shifted surplus -> deficit
    # Load/generation analysis
    annual_load_kwh: float
    annual_re_kwh: float
    annual_surplus_kwh: float
    annual_deficit_kwh: float
    peak_surplus_kw: float
    peak_deficit_kw: float
    max_consecutive_deficit_hours: int
    # Sizing rationale
    sizing_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "recommendation": {
                "capacity_kwh": round(self.recommended_capacity_kwh, 1),
                "max_power_kw": round(self.recommended_max_power_kw, 1),
                "max_charge_kw": round(self.recommended_max_charge_kw, 1),
                "max_discharge_kw": round(self.recommended_max_discharge_kw, 1),
            },
            "projected_performance": {
                "unmet_fraction": round(self.projected_unmet_fraction, 4),
                "re_fraction": round(self.projected_re_fraction, 4),
                "shifted_kwh": round(self.projected_shifted_kwh, 1),
            },
            "load_generation_analysis": {
                "annual_load_kwh": round(self.annual_load_kwh, 1),
                "annual_re_kwh": round(self.annual_re_kwh, 1),
                "annual_surplus_kwh": round(self.annual_surplus_kwh, 1),
                "annual_deficit_kwh": round(self.annual_deficit_kwh, 1),
                "peak_surplus_kw": round(self.peak_surplus_kw, 1),
                "peak_deficit_kw": round(self.peak_deficit_kw, 1),
                "max_consecutive_deficit_hours": self.max_consecutive_deficit_hours,
            },
            "sizing_notes": self.sizing_notes,
        }


def _simulate_battery(
    surplus_kw: np.ndarray,
    deficit_kw: np.ndarray,
    capacity_kwh: float,
    max_charge_kw: float,
    max_discharge_kw: float,
    efficiency: float = 0.90,
    min_soc: float = 0.10,
    max_soc: float = 0.95,
) -> tuple[float, float]:
    """Simulate a simple battery dispatch to estimate unmet and shifted energy.

    Args:
        surplus_kw: Hourly surplus (RE - load, zeroed where negative)
        deficit_kw: Hourly deficit (load - RE, zeroed where negative)
        capacity_kwh: Battery capacity
        max_charge_kw: Maximum charge rate
        max_discharge_kw: Maximum discharge rate
        efficiency: Round-trip efficiency
        min_soc: Minimum state of charge
        max_soc: Maximum state of charge

    Returns:
        (total_unmet_kwh, total_shifted_kwh)
    """
    n = len(surplus_kw)
    usable_min = capacity_kwh * min_soc
    usable_max = capacity_kwh * max_soc
    soc_kwh = capacity_kwh * 0.5  # start at 50%
    soc_kwh = max(usable_min, min(usable_max, soc_kwh))

    sqrt_eff = np.sqrt(efficiency)
    total_unmet = 0.0
    total_shifted = 0.0

    for h in range(n):
        if surplus_kw[h] > 0:
            # Charge
            charge = min(surplus_kw[h], max_charge_kw)
            energy_in = charge * sqrt_eff  # losses on charge
            room = usable_max - soc_kwh
            if energy_in > room:
                energy_in = room
            soc_kwh += energy_in
        elif deficit_kw[h] > 0:
            # Discharge
            discharge_needed = deficit_kw[h]
            discharge = min(discharge_needed, max_discharge_kw)
            energy_out = discharge / sqrt_eff  # losses on discharge
            available = soc_kwh - usable_min
            if energy_out > available:
                energy_out = available
                discharge = energy_out * sqrt_eff
            soc_kwh -= energy_out
            total_shifted += discharge
            remaining_deficit = deficit_kw[h] - discharge
            total_unmet += max(0.0, remaining_deficit)
        else:
            total_unmet += 0.0  # no deficit, no surplus

    return total_unmet, total_shifted


def _max_consecutive_deficit(deficit_kw: np.ndarray) -> int:
    """Find the longest consecutive run of non-zero deficit hours."""
    max_run = 0
    current_run = 0
    for d in deficit_kw:
        if d > 0:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0
    return max_run


def recommend_bess(
    load_kw: np.ndarray,
    re_output_kw: np.ndarray,
    generator_kw: np.ndarray | None = None,
    grid_import_kw: np.ndarray | None = None,
    max_unmet_fraction: float = 0.05,
    min_re_fraction: float = 0.80,
    efficiency: float = 0.90,
    min_soc: float = 0.10,
    max_soc: float = 0.95,
    max_capacity_kwh: float | None = None,
) -> BESSSizingResult:
    """Recommend BESS capacity and power rating from dispatch results.

    Analyzes the hourly energy balance to find the battery size that
    meets the target constraints (max unmet load, min RE fraction).

    Args:
        load_kw: Hourly load demand (8760,)
        re_output_kw: Hourly renewable output (8760,)
        generator_kw: Hourly generator output (8760,), optional (from existing dispatch)
        grid_import_kw: Hourly grid import (8760,), optional (from existing dispatch)
        max_unmet_fraction: Target maximum unmet load fraction (default 5%)
        min_re_fraction: Target minimum renewable fraction (default 80%)
        efficiency: Round-trip battery efficiency
        min_soc: Minimum SOC
        max_soc: Maximum SOC
        max_capacity_kwh: Upper limit for recommended capacity (cost constraint)

    Returns:
        BESSSizingResult with recommended configuration and projected performance
    """
    load = np.asarray(load_kw, dtype=np.float64)
    re = np.asarray(re_output_kw, dtype=np.float64)
    n = len(load)

    gen = np.zeros(n, dtype=np.float64)
    if generator_kw is not None:
        gen = np.asarray(generator_kw, dtype=np.float64)

    grid = np.zeros(n, dtype=np.float64)
    if grid_import_kw is not None:
        grid = np.asarray(grid_import_kw, dtype=np.float64)

    notes: list[str] = []

    # Compute load-generation balance (only against RE, since we want
    # the battery to displace non-RE sources)
    net = re - load  # positive = surplus RE, negative = deficit
    surplus_kw = np.maximum(net, 0.0)
    deficit_kw = np.maximum(-net, 0.0)

    annual_load_kwh = float(np.sum(load))
    annual_re_kwh = float(np.sum(re))
    annual_surplus_kwh = float(np.sum(surplus_kw))
    annual_deficit_kwh = float(np.sum(deficit_kw))
    peak_surplus = float(np.max(surplus_kw))
    peak_deficit = float(np.max(deficit_kw))
    max_consec = _max_consecutive_deficit(deficit_kw)

    # Current performance without battery
    non_re_kwh = float(np.sum(gen)) + float(np.sum(grid))
    served_kwh = annual_load_kwh  # assume fully served for baseline
    current_re_fraction = max(0.0, 1.0 - non_re_kwh / served_kwh) if served_kwh > 0 else 0.0

    # Initial capacity estimate:
    # Heuristic: battery should cover the average daily deficit
    avg_daily_deficit = annual_deficit_kwh / 365.0
    initial_capacity = avg_daily_deficit * 1.2  # 20% margin

    # Power rating: must handle peak charge/discharge
    # Use 90th percentile to avoid oversizing for rare peaks
    p90_surplus = float(np.percentile(surplus_kw[surplus_kw > 0], 90)) if np.any(surplus_kw > 0) else 0.0
    p90_deficit = float(np.percentile(deficit_kw[deficit_kw > 0], 90)) if np.any(deficit_kw > 0) else 0.0

    # Ensure min power rating is reasonable (at least C/4 rate)
    min_power_kw = initial_capacity / 4.0

    max_charge_kw = max(p90_surplus, min_power_kw)
    max_discharge_kw = max(p90_deficit, min_power_kw)

    # Set upper limit for capacity search
    if max_capacity_kwh is not None:
        capacity_limit = max_capacity_kwh
    else:
        # Cap at 3x daily average deficit or annual surplus, whichever is smaller
        capacity_limit = min(avg_daily_deficit * 3, annual_surplus_kwh * 0.5)
        capacity_limit = max(capacity_limit, initial_capacity * 2)

    notes.append(
        f"Annual RE: {annual_re_kwh:.0f} kWh, Load: {annual_load_kwh:.0f} kWh "
        f"(RE fraction without storage: {current_re_fraction:.1%})"
    )
    notes.append(
        f"Daily avg deficit: {avg_daily_deficit:.1f} kWh, "
        f"max consecutive deficit: {max_consec}h"
    )

    # Iterative sizing: try capacities from small to large
    # Find the smallest capacity that meets both targets
    best_capacity = initial_capacity
    best_unmet_frac = 1.0
    best_re_frac = 0.0
    best_shifted = 0.0

    # Capacity steps: 10 steps from 25% to 200% of initial estimate
    capacities = np.linspace(
        max(initial_capacity * 0.25, 10.0),
        capacity_limit,
        num=20,
    )

    for cap in capacities:
        # Scale power rating with capacity (C/2 rate minimum, capped by peaks)
        charge_kw = min(max_charge_kw, cap / 2)
        discharge_kw = min(max_discharge_kw, cap / 2)
        # Ensure at least C/4
        charge_kw = max(charge_kw, cap / 4)
        discharge_kw = max(discharge_kw, cap / 4)

        unmet_kwh, shifted_kwh = _simulate_battery(
            surplus_kw, deficit_kw, cap,
            charge_kw, discharge_kw,
            efficiency, min_soc, max_soc,
        )

        unmet_frac = unmet_kwh / annual_load_kwh if annual_load_kwh > 0 else 0.0
        # RE fraction with battery: RE directly serves + battery shifts
        if served_kwh > 0:
            # Deficit covered by battery is now served by RE (shifted)
            # Non-RE needed = deficit - shifted (what battery couldn't cover)
            remaining_non_re = max(0, annual_deficit_kwh - shifted_kwh)
            re_frac = max(0.0, 1.0 - remaining_non_re / served_kwh)
        else:
            re_frac = 0.0

        if unmet_frac <= max_unmet_fraction and re_frac >= min_re_fraction:
            best_capacity = cap
            best_unmet_frac = unmet_frac
            best_re_frac = re_frac
            best_shifted = shifted_kwh
            notes.append(
                f"Target met at {cap:.0f} kWh: "
                f"unmet={unmet_frac:.1%}, RE={re_frac:.1%}"
            )
            break
        else:
            best_capacity = cap
            best_unmet_frac = unmet_frac
            best_re_frac = re_frac
            best_shifted = shifted_kwh
    else:
        # Didn't meet targets, use the largest capacity tried
        notes.append(
            f"Targets not fully met at max capacity {best_capacity:.0f} kWh: "
            f"unmet={best_unmet_frac:.1%} (target <{max_unmet_fraction:.0%}), "
            f"RE={best_re_frac:.1%} (target >{min_re_fraction:.0%})"
        )
        if annual_re_kwh < annual_load_kwh * min_re_fraction:
            notes.append(
                "Insufficient RE generation to meet target RE fraction "
                "with battery alone. Consider adding more PV/wind capacity."
            )

    # Round to practical sizes
    best_capacity = _round_to_practical(best_capacity)

    # Final power rating
    final_charge_kw = min(max_charge_kw, best_capacity / 2)
    final_discharge_kw = min(max_discharge_kw, best_capacity / 2)
    final_charge_kw = max(final_charge_kw, best_capacity / 4)
    final_discharge_kw = max(final_discharge_kw, best_capacity / 4)
    final_charge_kw = _round_to_practical(final_charge_kw)
    final_discharge_kw = _round_to_practical(final_discharge_kw)
    max_power = max(final_charge_kw, final_discharge_kw)

    notes.append(
        f"Recommended: {best_capacity:.0f} kWh / {max_power:.0f} kW "
        f"(C-rate: {max_power / best_capacity:.2f}C)"
    )

    return BESSSizingResult(
        recommended_capacity_kwh=best_capacity,
        recommended_max_power_kw=max_power,
        recommended_max_charge_kw=final_charge_kw,
        recommended_max_discharge_kw=final_discharge_kw,
        projected_unmet_fraction=best_unmet_frac,
        projected_re_fraction=best_re_frac,
        projected_shifted_kwh=best_shifted,
        annual_load_kwh=annual_load_kwh,
        annual_re_kwh=annual_re_kwh,
        annual_surplus_kwh=annual_surplus_kwh,
        annual_deficit_kwh=annual_deficit_kwh,
        peak_surplus_kw=peak_surplus,
        peak_deficit_kw=peak_deficit,
        max_consecutive_deficit_hours=max_consec,
        sizing_notes=notes,
    )


def _round_to_practical(value: float) -> float:
    """Round to practical battery sizing increments.

    - < 20 kWh: round to nearest 5
    - 20-100 kWh: round to nearest 10
    - 100-500 kWh: round to nearest 25
    - > 500 kWh: round to nearest 50
    """
    if value < 5:
        return max(5.0, round(value))
    elif value < 20:
        return round(value / 5) * 5
    elif value < 100:
        return round(value / 10) * 10
    elif value < 500:
        return round(value / 25) * 25
    else:
        return round(value / 50) * 50
