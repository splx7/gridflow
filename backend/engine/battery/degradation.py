"""
Battery degradation models: cycle aging (rainflow + Wohler) and calendar aging.

Cycle aging
-----------
A simplified rainflow counting algorithm extracts (depth, count) pairs from
an SOC time series.  The Wohler curve model then maps each cycle to a
capacity-fade contribution using an inverse power law.

Calendar aging
--------------
An Arrhenius-style model captures time- and temperature-dependent side
reactions that degrade capacity even when the battery is idle.

Both mechanisms are combined in ``total_degradation`` for convenience.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from numpy.typing import ArrayLike


# ======================================================================
# Rainflow cycle counting (simplified four-point method)
# ======================================================================

def rainflow_count(soc_history: ArrayLike) -> List[Tuple[float, float]]:
    """Extract (depth, count) cycle pairs from an SOC time series.

    Implements a simplified rainflow counting algorithm (four-point method)
    commonly used for fatigue analysis.  Half-cycles that remain in the
    residual at the end are counted as 0.5 cycles each.

    Parameters
    ----------
    soc_history : array-like of float
        SOC values over time, each in [0, 1].

    Returns
    -------
    list of (float, float)
        Each element is ``(depth, count)`` where *depth* is the SOC swing
        magnitude and *count* is 0.5 or 1.0.
    """
    soc = np.asarray(soc_history, dtype=np.float64).ravel()

    if soc.size < 2:
        return []

    # --- Step 1: extract turning points (local extrema) ---------------
    turning_points: list[float] = [float(soc[0])]
    for i in range(1, len(soc) - 1):
        prev_val, cur_val, next_val = soc[i - 1], soc[i], soc[i + 1]
        if (cur_val - prev_val) * (next_val - cur_val) < 0:
            turning_points.append(float(cur_val))
    turning_points.append(float(soc[-1]))

    if len(turning_points) < 2:
        return []

    # --- Step 2: four-point rainflow extraction -----------------------
    cycles: list[tuple[float, float]] = []
    points: list[float] = list(turning_points)

    i = 0
    while i < len(points) - 3:
        s0, s1, s2, s3 = points[i], points[i + 1], points[i + 2], points[i + 3]
        range_inner = abs(s2 - s1)
        range_outer = abs(s3 - s0)

        # Inner range is enclosed by outer range => full cycle.
        if range_inner <= abs(s1 - s0) and range_inner <= abs(s3 - s2):
            depth = range_inner
            if depth > 1e-9:
                cycles.append((depth, 1.0))
            # Remove the two inner points.
            points.pop(i + 1)
            points.pop(i + 1)
            # Restart scan from beginning (simple but correct).
            i = 0
        else:
            i += 1

    # --- Step 3: residual half-cycles ---------------------------------
    for j in range(len(points) - 1):
        depth = abs(points[j + 1] - points[j])
        if depth > 1e-9:
            cycles.append((depth, 0.5))

    return cycles


# ======================================================================
# Wohler (S-N curve) cycle degradation
# ======================================================================

def wohler_degradation(
    cycles: List[Tuple[float, float]],
    cycle_life: float,
    depth_stress_factor: float = 2.0,
) -> float:
    """Capacity-fade fraction from cycling using a Wohler / inverse-power model.

    The model assumes that the number of cycles to failure at a given
    depth-of-discharge ``D`` follows::

        N_f(D) = cycle_life / D^depth_stress_factor

    Each cycle of depth *D* repeated *n* times contributes a damage
    fraction ``n / N_f(D)`` (Palmgren-Miner linear accumulation).

    Parameters
    ----------
    cycles : list of (float, float)
        Output of :func:`rainflow_count` -- ``(depth, count)`` pairs.
    cycle_life : float
        Number of full (depth = 1.0) cycles to end-of-life (e.g. 5000).
    depth_stress_factor : float
        Exponent in the Wohler curve.  Higher values mean shallow cycles
        cause proportionally less damage.  Default 2.0.

    Returns
    -------
    float
        Cumulative capacity-fade fraction in [0, 1].  A value of 0.05
        means 5 % of original capacity has been lost to cycling.
    """
    if cycle_life <= 0:
        raise ValueError(f"cycle_life must be positive, got {cycle_life}")

    total_damage = 0.0
    for depth, count in cycles:
        if depth <= 0:
            continue
        # Cycles to failure at this depth.
        n_f = cycle_life / (depth ** depth_stress_factor)
        total_damage += count / n_f

    # Clamp to [0, 1].
    return float(np.clip(total_damage, 0.0, 1.0))


# ======================================================================
# Calendar aging (Arrhenius-style)
# ======================================================================

# Pre-defined activation energies and prefactors by chemistry.
# fade = prefactor * years^0.5 * exp(-Ea / (R * T))
# We normalise so that the reference temperature is 25 degC (298.15 K)
# and express the result directly as a fraction.
_CALENDAR_PARAMS: dict[str, dict[str, float]] = {
    "lfp": {
        "prefactor": 0.020,       # ~2 % / sqrt(year) at 25 degC
        "activation_energy_ev": 0.30,
    },
    "nmc": {
        "prefactor": 0.025,       # ~2.5 % / sqrt(year) at 25 degC
        "activation_energy_ev": 0.32,
    },
    "lto": {
        "prefactor": 0.010,       # LTO is very durable
        "activation_energy_ev": 0.28,
    },
    "lead_acid": {
        "prefactor": 0.050,
        "activation_energy_ev": 0.35,
    },
}

_BOLTZMANN_EV_PER_K = 8.617333e-5  # eV/K
_T_REF = 298.15  # 25 degC in Kelvin


def calendar_degradation(
    years: float,
    temperature_avg: float = 25.0,
    chemistry: str = "nmc",
) -> float:
    """Capacity-fade fraction from calendar (time + temperature) aging.

    Uses an Arrhenius-accelerated square-root-of-time model that is
    standard in the battery literature.

    Parameters
    ----------
    years : float
        Time elapsed in years (>= 0).
    temperature_avg : float
        Average cell temperature in degrees Celsius.  Default 25.
    chemistry : str
        Battery chemistry identifier.  One of ``"lfp"``, ``"nmc"``,
        ``"lto"``, ``"lead_acid"``.  Default ``"nmc"``.

    Returns
    -------
    float
        Calendar-aging capacity-fade fraction in [0, 1].
    """
    if years < 0:
        raise ValueError(f"years must be non-negative, got {years}")

    chem_lower = chemistry.lower()
    if chem_lower not in _CALENDAR_PARAMS:
        raise ValueError(
            f"Unknown chemistry '{chemistry}'. "
            f"Supported: {list(_CALENDAR_PARAMS.keys())}"
        )

    params = _CALENDAR_PARAMS[chem_lower]
    prefactor = params["prefactor"]
    ea = params["activation_energy_ev"]

    t_kelvin = temperature_avg + 273.15

    # Arrhenius acceleration relative to reference temperature.
    accel = np.exp(
        (ea / _BOLTZMANN_EV_PER_K) * (1.0 / _T_REF - 1.0 / t_kelvin)
    )

    fade = prefactor * np.sqrt(years) * accel
    return float(np.clip(fade, 0.0, 1.0))


# ======================================================================
# Combined degradation
# ======================================================================

def total_degradation(
    soc_history: ArrayLike,
    years: float,
    temperature: float = 25.0,
    cycle_life: float = 5000.0,
    chemistry: str = "nmc",
    depth_stress_factor: float = 2.0,
) -> float:
    """Total capacity-fade fraction combining cycle and calendar aging.

    Degradation contributions are summed (Palmgren-Miner superposition)
    and clamped to [0, 1].

    Parameters
    ----------
    soc_history : array-like of float
        SOC time series fed to :func:`rainflow_count`.
    years : float
        Calendar time elapsed.
    temperature : float
        Average cell temperature in degrees Celsius.
    cycle_life : float
        Cycles to failure at depth = 1 for the Wohler model.
    chemistry : str
        Chemistry string for calendar aging.
    depth_stress_factor : float
        Wohler exponent.

    Returns
    -------
    float
        Combined capacity-fade fraction in [0, 1].
    """
    cycles = rainflow_count(soc_history)
    cycle_fade = wohler_degradation(cycles, cycle_life, depth_stress_factor)
    cal_fade = calendar_degradation(years, temperature, chemistry)

    combined = cycle_fade + cal_fade
    return float(np.clip(combined, 0.0, 1.0))
