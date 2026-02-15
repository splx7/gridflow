"""
State of Charge (SOC) tracker using Coulomb counting.

Tracks energy flowing in and out of a battery while applying round-trip
efficiency losses symmetrically to charge and discharge.  Enforces
configurable SOC limits and returns the actual power delivered when the
request would violate those limits.
"""

from __future__ import annotations

import numpy as np


class SOCTracker:
    """Coulomb-counting SOC tracker with efficiency and SOC bounds.

    Efficiency convention
    ---------------------
    The round-trip efficiency ``eta`` is split equally across charge and
    discharge using ``sqrt(eta)``:

    * **Charging** -- of the ``P`` kW injected, only ``P * sqrt(eta)``
      is stored.
    * **Discharging** -- to deliver ``P`` kW to the load, the battery
      must release ``P / sqrt(eta)`` internally.

    Parameters
    ----------
    capacity_kwh : float
        Nameplate energy capacity of the battery in kWh.
    efficiency : float
        Round-trip efficiency in (0, 1].  Default 0.90 (90 %).
    min_soc : float
        Minimum allowed SOC in [0, 1).  Default 0.10.
    max_soc : float
        Maximum allowed SOC in (0, 1].  Default 0.95.
    initial_soc : float
        Starting SOC in [min_soc, max_soc].  Default 0.50.
    """

    def __init__(
        self,
        capacity_kwh: float,
        efficiency: float = 0.90,
        min_soc: float = 0.10,
        max_soc: float = 0.95,
        initial_soc: float = 0.50,
    ) -> None:
        if capacity_kwh <= 0:
            raise ValueError(f"capacity_kwh must be positive, got {capacity_kwh}")
        if not 0 < efficiency <= 1.0:
            raise ValueError(f"efficiency must be in (0, 1], got {efficiency}")
        if not 0 <= min_soc < max_soc <= 1.0:
            raise ValueError(
                f"Need 0 <= min_soc < max_soc <= 1, got min_soc={min_soc}, "
                f"max_soc={max_soc}"
            )

        self.capacity_kwh: float = capacity_kwh
        self.efficiency: float = efficiency
        self.min_soc: float = min_soc
        self.max_soc: float = max_soc

        # Precompute one-way efficiency factor.
        self._eta_one_way: float = float(np.sqrt(efficiency))

        # Clamp initial SOC to allowed range.
        self._soc: float = float(np.clip(initial_soc, min_soc, max_soc))
        self._initial_soc: float = self._soc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def step(
        self, power_kw: float, dt_hours: float = 1.0
    ) -> tuple[float, float]:
        """Advance one time step with the requested power flow.

        Sign convention:
            * ``power_kw > 0`` => **charging** (grid-to-battery).
            * ``power_kw < 0`` => **discharging** (battery-to-grid).

        Parameters
        ----------
        power_kw : float
            Requested power in kW (positive = charge, negative = discharge).
        dt_hours : float
            Duration of the time step in hours.  Default 1.0.

        Returns
        -------
        tuple[float, float]
            ``(actual_power_kw, new_soc)`` where ``actual_power_kw``
            follows the same sign convention and may be smaller in
            magnitude than ``power_kw`` if SOC bounds were hit.
        """
        if dt_hours <= 0:
            return (0.0, self._soc)

        if power_kw >= 0:
            actual_power = self._charge(power_kw, dt_hours)
        else:
            actual_power = self._discharge(power_kw, dt_hours)

        return (actual_power, self._soc)

    def get_soc(self) -> float:
        """Return the current state of charge in [0, 1]."""
        return self._soc

    def reset(self) -> None:
        """Reset SOC to the value provided at construction."""
        self._soc = self._initial_soc

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _charge(self, power_kw: float, dt_hours: float) -> float:
        """Handle a positive (charging) power request.

        Returns the actual power accepted by the battery (>= 0).
        """
        # Energy reaching the battery after charge-side losses.
        energy_stored = power_kw * dt_hours * self._eta_one_way  # kWh

        # How much room is left before max_soc?
        room_kwh = (self.max_soc - self._soc) * self.capacity_kwh

        if energy_stored > room_kwh:
            energy_stored = room_kwh

        # Update SOC.
        delta_soc = energy_stored / self.capacity_kwh
        self._soc = float(np.clip(self._soc + delta_soc, self.min_soc, self.max_soc))

        # Back-calculate the actual grid-side power that corresponds to
        # the energy we actually stored.
        if dt_hours > 0 and self._eta_one_way > 0:
            actual_power = energy_stored / (dt_hours * self._eta_one_way)
        else:
            actual_power = 0.0

        return float(actual_power)

    def _discharge(self, power_kw: float, dt_hours: float) -> float:
        """Handle a negative (discharging) power request.

        Returns the actual power delivered (negative value, magnitude
        may be less than requested).
        """
        # power_kw is negative.  Work with magnitudes internally.
        requested_magnitude = abs(power_kw)

        # Energy the battery must release internally to deliver
        # requested_magnitude to the load (discharge-side losses).
        energy_internal = requested_magnitude * dt_hours / self._eta_one_way

        # How much energy is available above min_soc?
        available_kwh = (self._soc - self.min_soc) * self.capacity_kwh

        if energy_internal > available_kwh:
            energy_internal = available_kwh

        # Update SOC.
        delta_soc = energy_internal / self.capacity_kwh
        self._soc = float(np.clip(self._soc - delta_soc, self.min_soc, self.max_soc))

        # Actual power delivered to the load after losses.
        if dt_hours > 0:
            actual_magnitude = energy_internal * self._eta_one_way / dt_hours
        else:
            actual_magnitude = 0.0

        return float(-actual_magnitude)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"SOCTracker(capacity_kwh={self.capacity_kwh}, "
            f"efficiency={self.efficiency}, soc={self._soc:.4f})"
        )
