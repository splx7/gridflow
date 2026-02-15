"""Cycle-charging dispatch strategy for hybrid microgrid systems.

When the generator is needed it runs at **full rated capacity**, charging
the battery with any surplus output beyond what the load requires.  The
generator is started only when a deficit exists AND the battery state of
charge is below a configurable threshold.

This strategy reduces generator start/stop cycles and fuel consumption at
partial load, at the cost of somewhat higher total fuel burned compared to
the load-following baseline.

**Start condition:** deficit > 0 AND battery SOC < ``soc_threshold``
**Run mode:** generator at rated power; surplus charges battery then exports/curtails.
**Stop condition:** no deficit AND battery SOC >= ``soc_threshold``.
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

_MONTH_START_HOURS = np.array(
    [0, 744, 1416, 2160, 2880, 3624, 4344, 5088, 5832, 6552, 7296, 8016],
    dtype=np.int64,
)


def _hour_to_month_and_hod(hour_of_year: int) -> tuple[int, int]:
    """Convert hour-of-year (0-8759) to (month 1-12, hour_of_day 0-23)."""
    month = int(np.searchsorted(_MONTH_START_HOURS, hour_of_year, side="right"))
    hour_of_day = hour_of_year % 24
    return month, hour_of_day


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def dispatch_cycle_charging(
    load_kw: NDArray[np.floating],
    re_output_kw: NDArray[np.floating],
    battery: Optional[BatterySystem] = None,
    generator: Optional[DieselGenerator] = None,
    grid: Optional[GridConnection] = None,
    soc_threshold: float = 0.80,
) -> dict[str, NDArray[np.floating]]:
    """Run a cycle-charging dispatch over 8760 hourly time-steps.

    Parameters
    ----------
    load_kw : ndarray, shape (8760,)
        Hourly electrical load in kW.
    re_output_kw : ndarray, shape (8760,)
        Combined renewable-energy output (PV + wind + ...) in kW.
    battery : BatterySystem or None
        Battery storage system.
    generator : DieselGenerator or None
        Diesel backup generator.
    grid : GridConnection or None
        Utility grid connection.
    soc_threshold : float
        Battery SOC threshold below which the generator is started when a
        deficit exists.  Default 0.80.

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

    gen_was_running = False

    for t in range(HOURS_PER_YEAR):
        month, hod = _hour_to_month_and_hod(t)
        net = re_output_kw[t] - load_kw[t]  # positive = surplus

        current_soc = (
            battery.get_state()["soc"] if battery is not None else 1.0
        )

        if net >= 0:
            # ----- SURPLUS: RE covers load ----------------------------------
            surplus = net

            # If generator was running (from cycle-charge), keep it on until
            # battery is recharged above threshold.
            if (
                generator is not None
                and gen_was_running
                and current_soc < soc_threshold
            ):
                # Run generator at full capacity.
                gen_kw, _fuel, _cost, gen_was_running = generator.simulate_hour(
                    generator.rated_power_kw, gen_was_running
                )
                generator_output[t] = gen_kw
                surplus += gen_kw  # generator output adds to available surplus
            elif generator is not None and gen_was_running:
                # SOC above threshold, shut generator down.
                generator.stop()
                gen_was_running = False

            # Charge battery with surplus.
            if battery is not None and surplus > 0:
                accepted = battery.charge(surplus)
                surplus -= accepted
                battery_power[t] = -accepted  # negative = charging

            # Export remaining surplus to grid.
            if grid is not None and surplus > 0:
                exported, _rev = grid.export_power(surplus, hod, month)
                grid_export[t] = exported
                surplus -= exported

            # Curtail remainder.
            excess[t] = max(surplus, 0.0)

        else:
            # ----- DEFICIT: load exceeds RE ---------------------------------
            deficit = -net  # positive magnitude

            # Decide whether to start/run the generator.
            # Cycle-charging rule: generator runs at full capacity when there
            # is a deficit AND battery SOC is below threshold.
            run_gen = (
                generator is not None
                and (current_soc < soc_threshold or gen_was_running)
                and deficit > 0
            )

            if run_gen:
                # Run generator at full rated power.
                gen_kw, _fuel, _cost, gen_was_running = generator.simulate_hour(
                    generator.rated_power_kw, gen_was_running
                )
                generator_output[t] = gen_kw

                # Generator output may exceed deficit -- allocate surplus.
                gen_surplus = gen_kw - deficit
                if gen_surplus > 0:
                    deficit = 0.0

                    # Charge battery with generator surplus.
                    if battery is not None and gen_surplus > 0:
                        accepted = battery.charge(gen_surplus)
                        gen_surplus -= accepted
                        battery_power[t] = -accepted

                    # Export any remaining generator surplus to grid.
                    if grid is not None and gen_surplus > 0:
                        exported, _rev = grid.export_power(
                            gen_surplus, hod, month
                        )
                        grid_export[t] = exported
                        gen_surplus -= exported

                    excess[t] = max(gen_surplus, 0.0)
                else:
                    # Generator did not fully cover deficit.
                    deficit -= gen_kw
            else:
                # No generator or SOC above threshold -- don't run gen.
                if generator is not None and gen_was_running:
                    generator.stop()
                    gen_was_running = False

            # Remaining deficit: discharge battery.
            if battery is not None and deficit > 0:
                delivered = battery.discharge(deficit)
                battery_power[t] += delivered  # add to existing (may already have charging component)
                deficit -= delivered

            # Remaining deficit: import from grid.
            if grid is not None and deficit > 0:
                imported, _cost = grid.import_power(deficit, hod, month)
                grid_import[t] = imported
                deficit -= imported

            # Unmet load.
            unmet[t] = max(deficit, 0.0)

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
    }
