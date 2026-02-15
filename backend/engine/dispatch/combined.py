"""Combined dispatch strategy with adaptive mode switching.

Starts in **load-following** mode for efficiency.  When the battery SOC
drops below ``critical_soc`` the strategy switches to **cycle-charging**
mode (generator at full capacity) to aggressively recharge the battery.
Once SOC recovers above ``recovery_soc`` the strategy reverts to load-
following.

The hysteresis band (critical_soc .. recovery_soc) prevents rapid mode
oscillation.

Mode transitions
----------------
    LOAD_FOLLOWING  --[soc < critical_soc]--> CYCLE_CHARGING
    CYCLE_CHARGING  --[soc >= recovery_soc]--> LOAD_FOLLOWING
"""

from __future__ import annotations

import enum
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from engine.battery.battery_system import BatterySystem
from engine.generator.diesel_generator import DieselGenerator
from engine.grid.grid_connection import GridConnection

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOURS_PER_YEAR = 8760

_MONTH_START_HOURS = np.array(
    [0, 744, 1416, 2160, 2880, 3624, 4344, 5088, 5832, 6552, 7296, 8016],
    dtype=np.int64,
)


def _hour_to_month_and_hod(hour_of_year: int) -> tuple[int, int]:
    """Convert hour-of-year (0-8759) to (month 1-12, hour_of_day 0-23)."""
    month = int(np.searchsorted(_MONTH_START_HOURS, hour_of_year, side="right"))
    hour_of_day = hour_of_year % 24
    return month, hour_of_day


class _Mode(enum.Enum):
    """Internal dispatch mode tracker."""

    LOAD_FOLLOWING = "load_following"
    CYCLE_CHARGING = "cycle_charging"


# ---------------------------------------------------------------------------
# Per-hour dispatch helpers (inline, avoiding function-call overhead)
# ---------------------------------------------------------------------------


def _dispatch_hour_load_following(
    t: int,
    net: float,
    month: int,
    hod: int,
    battery: Optional[BatterySystem],
    generator: Optional[DieselGenerator],
    grid: Optional[GridConnection],
    gen_was_running: bool,
    battery_power: NDArray,
    generator_output: NDArray,
    grid_import: NDArray,
    grid_export: NDArray,
    excess: NDArray,
    unmet: NDArray,
) -> bool:
    """Dispatch one hour in load-following mode.  Returns gen_was_running."""
    if net >= 0:
        surplus = net

        # Charge battery.
        if battery is not None and surplus > 0:
            accepted = battery.charge(surplus)
            surplus -= accepted
            battery_power[t] = -accepted

        # Export to grid.
        if grid is not None and surplus > 0:
            exported, _ = grid.export_power(surplus, hod, month)
            grid_export[t] = exported
            surplus -= exported

        excess[t] = max(surplus, 0.0)

        # Turn off generator during surplus.
        if generator is not None and gen_was_running:
            generator.stop()
            gen_was_running = False
    else:
        deficit = -net

        # Battery discharge.
        if battery is not None and deficit > 0:
            delivered = battery.discharge(deficit)
            battery_power[t] = delivered
            deficit -= delivered

        # Generator.
        if generator is not None and deficit > 0:
            gen_kw, _, _, gen_was_running = generator.simulate_hour(
                deficit, gen_was_running
            )
            generator_output[t] = gen_kw
            deficit -= gen_kw

        # Grid import.
        if grid is not None and deficit > 0:
            imported, _ = grid.import_power(deficit, hod, month)
            grid_import[t] = imported
            deficit -= imported

        unmet[t] = max(deficit, 0.0)

    return gen_was_running


def _dispatch_hour_cycle_charging(
    t: int,
    net: float,
    month: int,
    hod: int,
    battery: Optional[BatterySystem],
    generator: Optional[DieselGenerator],
    grid: Optional[GridConnection],
    gen_was_running: bool,
    battery_power: NDArray,
    generator_output: NDArray,
    grid_import: NDArray,
    grid_export: NDArray,
    excess: NDArray,
    unmet: NDArray,
    soc_threshold: float,
) -> bool:
    """Dispatch one hour in cycle-charging mode.  Returns gen_was_running."""
    current_soc = battery.get_state()["soc"] if battery is not None else 1.0

    if net >= 0:
        surplus = net

        # Keep generator running if battery still below threshold.
        if (
            generator is not None
            and gen_was_running
            and current_soc < soc_threshold
        ):
            gen_kw, _, _, gen_was_running = generator.simulate_hour(
                generator.rated_power_kw, gen_was_running
            )
            generator_output[t] = gen_kw
            surplus += gen_kw
        elif generator is not None and gen_was_running:
            generator.stop()
            gen_was_running = False

        # Charge battery.
        if battery is not None and surplus > 0:
            accepted = battery.charge(surplus)
            surplus -= accepted
            battery_power[t] = -accepted

        # Export.
        if grid is not None and surplus > 0:
            exported, _ = grid.export_power(surplus, hod, month)
            grid_export[t] = exported
            surplus -= exported

        excess[t] = max(surplus, 0.0)
    else:
        deficit = -net

        # Generator at full capacity.
        run_gen = (
            generator is not None
            and (current_soc < soc_threshold or gen_was_running)
            and deficit > 0
        )

        if run_gen:
            gen_kw, _, _, gen_was_running = generator.simulate_hour(
                generator.rated_power_kw, gen_was_running
            )
            generator_output[t] = gen_kw

            gen_surplus = gen_kw - deficit
            if gen_surplus > 0:
                deficit = 0.0

                if battery is not None and gen_surplus > 0:
                    accepted = battery.charge(gen_surplus)
                    gen_surplus -= accepted
                    battery_power[t] = -accepted

                if grid is not None and gen_surplus > 0:
                    exported, _ = grid.export_power(gen_surplus, hod, month)
                    grid_export[t] = exported
                    gen_surplus -= exported

                excess[t] = max(gen_surplus, 0.0)
            else:
                deficit -= gen_kw
        else:
            if generator is not None and gen_was_running:
                generator.stop()
                gen_was_running = False

        # Battery discharge for remaining deficit.
        if battery is not None and deficit > 0:
            delivered = battery.discharge(deficit)
            battery_power[t] += delivered
            deficit -= delivered

        # Grid import.
        if grid is not None and deficit > 0:
            imported, _ = grid.import_power(deficit, hod, month)
            grid_import[t] = imported
            deficit -= imported

        unmet[t] = max(deficit, 0.0)

    return gen_was_running


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def dispatch_combined(
    load_kw: NDArray[np.floating],
    re_output_kw: NDArray[np.floating],
    battery: Optional[BatterySystem] = None,
    generator: Optional[DieselGenerator] = None,
    grid: Optional[GridConnection] = None,
    critical_soc: float = 0.30,
    recovery_soc: float = 0.70,
) -> dict[str, NDArray[np.floating]]:
    """Run combined load-following / cycle-charging dispatch over 8760 hours.

    The strategy begins in load-following mode.  When the battery SOC falls
    below ``critical_soc`` the mode switches to cycle-charging (generator at
    full power) until SOC recovers above ``recovery_soc``.

    Parameters
    ----------
    load_kw : ndarray, shape (8760,)
        Hourly electrical load in kW.
    re_output_kw : ndarray, shape (8760,)
        Combined renewable-energy output in kW.
    battery : BatterySystem or None
        Battery storage system.
    generator : DieselGenerator or None
        Diesel backup generator.
    grid : GridConnection or None
        Utility grid connection.
    critical_soc : float
        SOC level that triggers a switch to cycle-charging.  Default 0.30.
    recovery_soc : float
        SOC level that triggers a return to load-following.  Default 0.70.

    Returns
    -------
    dict[str, ndarray]
        Keys (all ndarray of shape (8760,)):

        * ``battery_power``    -- Battery power flow (positive = discharge).
        * ``battery_soc``      -- Battery SOC at end of each hour.
        * ``generator_output`` -- Generator electrical output in kW.
        * ``grid_import``      -- Power imported from grid in kW.
        * ``grid_export``      -- Power exported to grid in kW.
        * ``excess``           -- Curtailed energy in kW.
        * ``unmet``            -- Unserved load in kW.
        * ``dispatch_mode``    -- Integer mode indicator per hour
                                  (0 = load_following, 1 = cycle_charging).

    Raises
    ------
    ValueError
        If ``critical_soc >= recovery_soc`` (no hysteresis band).
    """
    if critical_soc >= recovery_soc:
        raise ValueError(
            f"critical_soc ({critical_soc}) must be strictly less than "
            f"recovery_soc ({recovery_soc}) to form a hysteresis band."
        )

    load_kw = np.asarray(load_kw, dtype=np.float64)
    re_output_kw = np.asarray(re_output_kw, dtype=np.float64)

    if load_kw.shape != (HOURS_PER_YEAR,):
        raise ValueError(
            f"load_kw must have shape ({HOURS_PER_YEAR},), got {load_kw.shape}"
        )
    if re_output_kw.shape != (HOURS_PER_YEAR,):
        raise ValueError(
            f"re_output_kw must have shape ({HOURS_PER_YEAR},), "
            f"got {re_output_kw.shape}"
        )

    # Reset stateful components.
    if generator is not None:
        generator.reset_accumulators()
    if grid is not None:
        grid.reset()

    # Pre-allocate output arrays.
    battery_power = np.zeros(HOURS_PER_YEAR, dtype=np.float64)
    battery_soc = np.zeros(HOURS_PER_YEAR, dtype=np.float64)
    generator_output = np.zeros(HOURS_PER_YEAR, dtype=np.float64)
    grid_import = np.zeros(HOURS_PER_YEAR, dtype=np.float64)
    grid_export = np.zeros(HOURS_PER_YEAR, dtype=np.float64)
    excess = np.zeros(HOURS_PER_YEAR, dtype=np.float64)
    unmet = np.zeros(HOURS_PER_YEAR, dtype=np.float64)
    dispatch_mode = np.zeros(HOURS_PER_YEAR, dtype=np.float64)

    gen_was_running = False
    mode = _Mode.LOAD_FOLLOWING

    for t in range(HOURS_PER_YEAR):
        month, hod = _hour_to_month_and_hod(t)
        net = re_output_kw[t] - load_kw[t]

        # --- Mode transition logic (hysteresis) ----------------------------
        if battery is not None:
            current_soc = battery.get_state()["soc"]

            if mode == _Mode.LOAD_FOLLOWING and current_soc < critical_soc:
                mode = _Mode.CYCLE_CHARGING
            elif mode == _Mode.CYCLE_CHARGING and current_soc >= recovery_soc:
                mode = _Mode.LOAD_FOLLOWING

        # --- Dispatch based on current mode --------------------------------
        if mode == _Mode.LOAD_FOLLOWING:
            dispatch_mode[t] = 0.0
            gen_was_running = _dispatch_hour_load_following(
                t, net, month, hod,
                battery, generator, grid, gen_was_running,
                battery_power, generator_output,
                grid_import, grid_export, excess, unmet,
            )
        else:
            dispatch_mode[t] = 1.0
            gen_was_running = _dispatch_hour_cycle_charging(
                t, net, month, hod,
                battery, generator, grid, gen_was_running,
                battery_power, generator_output,
                grid_import, grid_export, excess, unmet,
                soc_threshold=recovery_soc,
            )

        # Record battery SOC.
        if battery is not None:
            battery_soc[t] = battery.get_state()["soc"]

    return {
        "battery_power": battery_power,
        "battery_soc": battery_soc,
        "generator_output": generator_output,
        "grid_import": grid_import,
        "grid_export": grid_export,
        "excess": excess,
        "unmet": unmet,
        "dispatch_mode": dispatch_mode,
    }
