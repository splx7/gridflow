"""Load-following dispatch strategy for hybrid microgrid systems.

Dispatches renewable generation to serve load first, then cascades surplus
and deficit through battery, generator, and grid in a fixed priority order:

**Surplus priority:** RE -> load -> battery charge -> grid export -> curtailment
**Deficit priority:** battery discharge -> generator -> grid import -> unmet load

This is the simplest rule-based strategy and serves as the baseline against
which more sophisticated approaches (cycle charging, optimal) are compared.
"""

from __future__ import annotations

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

# Cumulative hours at the start of each month (non-leap year).
_MONTH_START_HOURS = np.array(
    [0, 744, 1416, 2160, 2880, 3624, 4344, 5088, 5832, 6552, 7296, 8016],
    dtype=np.int64,
)


def _hour_to_month_and_hod(hour_of_year: int) -> tuple[int, int]:
    """Convert an hour-of-year index (0-8759) to (month, hour_of_day).

    Returns
    -------
    month : int
        Month of year, 1 -- 12.
    hour_of_day : int
        Hour of day, 0 -- 23.
    """
    # Month: find the last month whose start hour is <= hour_of_year.
    month = int(np.searchsorted(_MONTH_START_HOURS, hour_of_year, side="right"))
    # searchsorted with side='right' gives the insertion point *after* any
    # equal values, so month is already 1-indexed.
    hour_of_day = hour_of_year % 24
    return month, hour_of_day


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def dispatch_load_following(
    load_kw: NDArray[np.floating],
    re_output_kw: NDArray[np.floating],
    battery: Optional[BatterySystem] = None,
    generator: Optional[DieselGenerator] = None,
    grid: Optional[GridConnection] = None,
) -> dict[str, NDArray[np.floating]]:
    """Run a load-following dispatch over 8760 hourly time-steps.

    Parameters
    ----------
    load_kw : ndarray, shape (8760,)
        Hourly electrical load in kW.
    re_output_kw : ndarray, shape (8760,)
        Combined renewable-energy output (PV + wind + ...) in kW.
    battery : BatterySystem or None
        Battery storage system.  If ``None``, no battery is available.
    generator : DieselGenerator or None
        Diesel backup generator.  If ``None``, no generator is available.
    grid : GridConnection or None
        Utility grid connection.  If ``None``, the system is off-grid.

    Returns
    -------
    dict[str, ndarray]
        Keys (all ndarray of shape (8760,)):

        * ``battery_power``  -- Battery power flow (positive = discharge).
        * ``battery_soc``    -- Battery state of charge at end of each hour.
        * ``generator_output`` -- Generator electrical output in kW.
        * ``grid_import``    -- Power imported from grid in kW.
        * ``grid_export``    -- Power exported to grid in kW.
        * ``excess``         -- Curtailed energy in kW.
        * ``unmet``          -- Unserved load in kW.
    """
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

    # Reset stateful components so results are reproducible.
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

    gen_was_running = False

    for t in range(HOURS_PER_YEAR):
        month, hod = _hour_to_month_and_hod(t)
        net = re_output_kw[t] - load_kw[t]  # positive = surplus, negative = deficit

        if net >= 0:
            # ----- SURPLUS: RE exceeds load ---------------------------------
            surplus = net

            # 1. Charge battery with surplus.
            if battery is not None and surplus > 0:
                accepted = battery.charge(surplus)
                surplus -= accepted
                battery_power[t] = -accepted  # negative = charging

            # 2. Export remaining surplus to grid.
            if grid is not None and surplus > 0:
                exported, _rev = grid.export_power(surplus, hod, month)
                grid_export[t] = exported
                surplus -= exported

            # 3. Anything left over is curtailed.
            excess[t] = max(surplus, 0.0)

            # Turn off generator during surplus periods.
            if generator is not None and gen_was_running:
                generator.stop()
                gen_was_running = False

        else:
            # ----- DEFICIT: load exceeds RE ---------------------------------
            deficit = -net  # positive magnitude

            # 1. Discharge battery.
            if battery is not None and deficit > 0:
                delivered = battery.discharge(deficit)
                battery_power[t] = delivered  # positive = discharging
                deficit -= delivered

            # 2. Run generator.
            if generator is not None and deficit > 0:
                gen_kw, _fuel, _cost, gen_was_running = generator.simulate_hour(
                    deficit, gen_was_running
                )
                generator_output[t] = gen_kw
                deficit -= gen_kw

            # 3. Import from grid.
            if grid is not None and deficit > 0:
                imported, _cost = grid.import_power(deficit, hod, month)
                grid_import[t] = imported
                deficit -= imported

            # 4. Remaining deficit is unmet load.
            unmet[t] = max(deficit, 0.0)

        # Record battery SOC at end of this hour.
        if battery is not None:
            battery_soc[t] = battery.get_state()["soc"]
        # else remains 0.0

    return {
        "battery_power": battery_power,
        "battery_soc": battery_soc,
        "generator_output": generator_output,
        "grid_import": grid_import,
        "grid_export": grid_export,
        "excess": excess,
        "unmet": unmet,
    }
