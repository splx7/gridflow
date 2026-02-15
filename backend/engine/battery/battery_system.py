"""
System-level battery simulation combining KiBaM, SOC tracking, and degradation.

``BatterySystem`` is the primary entry point for grid simulation code.
It wraps the lower-level modules into a single object with a simple
``charge`` / ``discharge`` interface and tracks cumulative throughput,
cycle count, and remaining capacity over the lifetime of the battery.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from .kibam import KiBaMModel
from .soc_tracker import SOCTracker
from .degradation import rainflow_count, wohler_degradation, calendar_degradation


class BatterySystem:
    """Integrated battery model: kinetics + SOC + degradation.

    Parameters
    ----------
    capacity_kwh : float
        Nameplate energy capacity in kWh.
    max_charge_kw : float
        Maximum charge power in kW.
    max_discharge_kw : float
        Maximum discharge power in kW.
    efficiency : float
        Round-trip efficiency in (0, 1].  Default 0.90.
    min_soc : float
        Minimum SOC limit.  Default 0.10.
    max_soc : float
        Maximum SOC limit.  Default 0.95.
    initial_soc : float
        Starting SOC.  Default 0.50.
    kibam_c : float
        KiBaM capacity ratio.  Default 0.7 (Li-ion typical).
    kibam_k : float
        KiBaM rate constant (1/h).  Default 0.5.
    cycle_life : float
        Full-depth cycles to end-of-life.  Default 5000.
    chemistry : str
        Chemistry label for calendar aging model.  Default ``"nmc"``.
    depth_stress_factor : float
        Wohler exponent for cycle degradation.  Default 2.0.
    """

    def __init__(
        self,
        capacity_kwh: float,
        max_charge_kw: float,
        max_discharge_kw: float,
        efficiency: float = 0.90,
        min_soc: float = 0.10,
        max_soc: float = 0.95,
        initial_soc: float = 0.50,
        kibam_c: float = 0.7,
        kibam_k: float = 0.5,
        cycle_life: float = 5000.0,
        chemistry: str = "nmc",
        depth_stress_factor: float = 2.0,
    ) -> None:
        self.capacity_kwh: float = capacity_kwh
        self.max_charge_kw: float = abs(max_charge_kw)
        self.max_discharge_kw: float = abs(max_discharge_kw)
        self.cycle_life: float = cycle_life
        self.chemistry: str = chemistry
        self.depth_stress_factor: float = depth_stress_factor

        # Sub-models.
        self._kibam = KiBaMModel(
            q_max=capacity_kwh,
            c=kibam_c,
            k=kibam_k,
        )
        self._soc_tracker = SOCTracker(
            capacity_kwh=capacity_kwh,
            efficiency=efficiency,
            min_soc=min_soc,
            max_soc=max_soc,
            initial_soc=initial_soc,
        )

        # Cumulative bookkeeping.
        self._throughput_kwh: float = 0.0
        self._soc_history: list[float] = [initial_soc]
        self._capacity_remaining: float = 1.0  # fraction of nameplate
        self._elapsed_years: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def charge(self, power_kw: float, dt: float = 1.0) -> float:
        """Charge the battery.

        Parameters
        ----------
        power_kw : float
            Requested charge power in kW (positive value).
        dt : float
            Time step in hours.  Default 1.0.

        Returns
        -------
        float
            Actual power accepted by the battery in kW (>= 0).
        """
        power_kw = abs(power_kw)

        # KiBaM limit on charge rate.
        soc = self._soc_tracker.get_soc()
        kibam_limit = self._kibam.max_charge_power(soc, self.max_charge_kw)
        clamped_power = min(power_kw, self.max_charge_kw, kibam_limit)

        # Derate by remaining capacity (degraded battery stores less).
        effective_power = clamped_power * self._capacity_remaining

        # SOC tracker handles efficiency losses and SOC bounds.
        actual_power, new_soc = self._soc_tracker.step(effective_power, dt)

        # Bookkeeping.
        energy_kw = abs(actual_power) * dt
        self._throughput_kwh += energy_kw
        self._soc_history.append(new_soc)
        self._elapsed_years += dt / 8760.0

        return float(abs(actual_power))

    def discharge(self, power_kw: float, dt: float = 1.0) -> float:
        """Discharge the battery.

        Parameters
        ----------
        power_kw : float
            Requested discharge power in kW (positive value).
        dt : float
            Time step in hours.  Default 1.0.

        Returns
        -------
        float
            Actual power delivered to the load in kW (>= 0).
        """
        power_kw = abs(power_kw)

        # KiBaM limit on discharge rate.
        soc = self._soc_tracker.get_soc()
        kibam_limit = self._kibam.max_discharge_power(soc, self.max_discharge_kw)
        clamped_power = min(power_kw, self.max_discharge_kw, kibam_limit)

        # Derate by remaining capacity.
        effective_power = clamped_power * self._capacity_remaining

        # SOC tracker: negative power = discharge.
        actual_power, new_soc = self._soc_tracker.step(-effective_power, dt)

        # Bookkeeping (actual_power is negative for discharge).
        energy_kw = abs(actual_power) * dt
        self._throughput_kwh += energy_kw
        self._soc_history.append(new_soc)
        self._elapsed_years += dt / 8760.0

        return float(abs(actual_power))

    def get_state(self) -> Dict[str, float]:
        """Return a snapshot of the current battery state.

        Returns
        -------
        dict with keys:
            soc : float
                Current state of charge in [0, 1].
            capacity_remaining : float
                Fraction of nameplate capacity remaining after degradation.
            cycles : float
                Estimated equivalent full cycles consumed so far.
            throughput_kwh : float
                Cumulative energy throughput in kWh.
        """
        self._update_degradation()

        return {
            "soc": self._soc_tracker.get_soc(),
            "capacity_remaining": self._capacity_remaining,
            "cycles": self._estimate_equivalent_cycles(),
            "throughput_kwh": self._throughput_kwh,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_degradation(self) -> None:
        """Recompute remaining capacity from SOC history and elapsed time."""
        cycles = rainflow_count(self._soc_history)
        cycle_fade = wohler_degradation(
            cycles, self.cycle_life, self.depth_stress_factor
        )
        cal_fade = calendar_degradation(
            self._elapsed_years,
            temperature_avg=25.0,
            chemistry=self.chemistry,
        )
        total_fade = float(np.clip(cycle_fade + cal_fade, 0.0, 1.0))
        self._capacity_remaining = 1.0 - total_fade

    def _estimate_equivalent_cycles(self) -> float:
        """Estimate equivalent full cycles from throughput.

        One full cycle = capacity_kwh discharged + capacity_kwh charged.
        """
        if self.capacity_kwh <= 0:
            return 0.0
        # A full cycle involves discharging then recharging the full
        # capacity, so total throughput for one cycle = 2 * capacity.
        return self._throughput_kwh / (2.0 * self.capacity_kwh)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        state = self.get_state()
        return (
            f"BatterySystem("
            f"soc={state['soc']:.3f}, "
            f"capacity_remaining={state['capacity_remaining']:.4f}, "
            f"cycles={state['cycles']:.1f}, "
            f"throughput={state['throughput_kwh']:.1f} kWh)"
        )
