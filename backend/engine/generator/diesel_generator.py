"""Diesel generator dispatch and lifecycle tracking.

Provides a stateful generator model that enforces minimum-load constraints,
tracks cumulative runtime statistics, and accounts for start/stop costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from .fuel_curve import FuelCurve


@dataclass
class DieselGenerator:
    """Dispatchable diesel generator with operational constraints.

    Parameters
    ----------
    rated_power_kw : float
        Nameplate maximum continuous output (kW).
    min_load_ratio : float
        Minimum permissible loading as a fraction of rated_power_kw.
        Operating below this ratio is disallowed to protect the engine.
        Typical range 0.25 -- 0.40.
    fuel_curve : FuelCurve
        Fuel consumption model (see :class:`FuelCurve`).
    fuel_price : float
        Cost of fuel in $/litre.
    om_cost_per_hour : float
        Fixed operations & maintenance cost per running hour ($/hr).
    start_cost : float
        One-time cost incurred each time the generator is started ($).
        Accounts for wear, fuel priming, and battery drain on the starter.
    """

    rated_power_kw: float
    min_load_ratio: float = 0.30
    fuel_curve: FuelCurve = field(default_factory=FuelCurve)
    fuel_price: float = 1.20
    om_cost_per_hour: float = 5.0
    start_cost: float = 15.0

    # --- Runtime accumulators (not constructor parameters) ---------------
    running_hours: float = field(default=0.0, init=False, repr=False)
    fuel_consumed_total: float = field(default=0.0, init=False, repr=False)
    starts_count: int = field(default=0, init=False, repr=False)
    _is_running: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.rated_power_kw <= 0:
            raise ValueError(
                f"rated_power_kw must be > 0, got {self.rated_power_kw}"
            )
        if not 0 < self.min_load_ratio < 1:
            raise ValueError(
                f"min_load_ratio must be in (0, 1), got {self.min_load_ratio}"
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Whether the generator is currently online."""
        return self._is_running

    @property
    def min_power_kw(self) -> float:
        """Minimum permissible electrical output when running (kW)."""
        return self.rated_power_kw * self.min_load_ratio

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def start(self) -> float:
        """Start the generator.

        Returns
        -------
        float
            Start-up cost ($).  Returns 0.0 if already running.
        """
        if self._is_running:
            return 0.0
        self._is_running = True
        self.starts_count += 1
        return self.start_cost

    def stop(self) -> None:
        """Shut down the generator."""
        self._is_running = False

    # ------------------------------------------------------------------
    # Dispatch (single time-step)
    # ------------------------------------------------------------------

    def dispatch(
        self, power_request_kw: float
    ) -> Tuple[float, float, float]:
        """Determine actual output and cost for a power request.

        The generator must already be running (call :meth:`start` first).
        If the request is below the minimum load, the generator runs at
        minimum load to protect the engine.  If the request exceeds rated
        capacity, output is clamped to rated.

        Parameters
        ----------
        power_request_kw : float
            Desired electrical output (kW).  May be zero if the caller
            wants to idle the genset (output will be forced to min_load).

        Returns
        -------
        actual_output_kw : float
            Electrical output delivered (kW).
        fuel_liters : float
            Fuel consumed during this one-hour time-step (L).
        cost : float
            Total variable cost for this hour ($), comprising fuel cost
            and O&M cost.  Does *not* include start cost (that is handled
            separately by :meth:`start`).

        Raises
        ------
        RuntimeError
            If the generator is not running.
        """
        if not self._is_running:
            raise RuntimeError(
                "Generator is not running. Call start() before dispatch()."
            )

        # Enforce minimum and maximum loading.
        if power_request_kw < self.min_power_kw:
            actual_kw = self.min_power_kw
        elif power_request_kw > self.rated_power_kw:
            actual_kw = self.rated_power_kw
        else:
            actual_kw = power_request_kw

        fuel_l = self.fuel_curve.consumption(actual_kw, self.rated_power_kw)
        cost = fuel_l * self.fuel_price + self.om_cost_per_hour

        # Update accumulators.
        self.running_hours += 1.0
        self.fuel_consumed_total += fuel_l

        return actual_kw, fuel_l, cost

    # ------------------------------------------------------------------
    # Convenience: simulate a single hour (handles start/stop logic)
    # ------------------------------------------------------------------

    def simulate_hour(
        self,
        power_request_kw: float,
        was_running: bool,
    ) -> Tuple[float, float, float, bool]:
        """Simulate one hourly time-step with automatic start/stop logic.

        This is a higher-level wrapper around :meth:`start`, :meth:`stop`,
        and :meth:`dispatch` that decides whether the generator should be
        on or off based on the requested power.

        Decision logic
        --------------
        * If ``power_request_kw <= 0`` the generator is shut down (or stays
          off) and all outputs are zero.
        * Otherwise the generator is started (if not already running) and
          dispatched at the requested power (subject to min/max limits).

        Parameters
        ----------
        power_request_kw : float
            Desired electrical output for this hour (kW).
        was_running : bool
            Whether the generator was running at the *end* of the previous
            time-step.  Used to determine whether a start-up cost applies.

        Returns
        -------
        output_kw : float
            Actual electrical output delivered (kW).
        fuel_l : float
            Fuel consumed (litres).
        cost : float
            Total cost for this hour ($), including start cost if applicable.
        is_running : bool
            Generator state at the end of this time-step.
        """
        # Synchronise internal state with the provided flag (allows the
        # caller to control state externally, e.g. in a dispatch loop).
        self._is_running = was_running

        # --- Off request ---
        if power_request_kw <= 0:
            if self._is_running:
                self.stop()
            return 0.0, 0.0, 0.0, False

        # --- On request ---
        startup_cost = 0.0
        if not self._is_running:
            startup_cost = self.start()

        output_kw, fuel_l, variable_cost = self.dispatch(power_request_kw)
        total_cost = variable_cost + startup_cost

        return output_kw, fuel_l, total_cost, True

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------

    def total_fuel_cost(self) -> float:
        """Cumulative fuel expenditure ($)."""
        return self.fuel_consumed_total * self.fuel_price

    def total_om_cost(self) -> float:
        """Cumulative O&M expenditure ($)."""
        return self.running_hours * self.om_cost_per_hour

    def total_start_cost(self) -> float:
        """Cumulative start-up expenditure ($)."""
        return self.starts_count * self.start_cost

    def reset_accumulators(self) -> None:
        """Zero-out all runtime statistics."""
        self.running_hours = 0.0
        self.fuel_consumed_total = 0.0
        self.starts_count = 0
        self._is_running = False
