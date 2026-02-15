"""Fuel consumption curve model for diesel/gas generators.

Models the linear relationship between generator loading and fuel consumption
using the standard two-coefficient approach:

    F(P) = a0 * P_rated + a1 * P_output   [L/hr]

where:
    a0  = no-load fuel intercept  (L/hr per kW-rated)
    a1  = marginal fuel slope     (L/hr per kW-output)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FuelCurve:
    """Linear fuel-consumption curve for a reciprocating generator.

    Parameters
    ----------
    a0 : float
        No-load intercept coefficient in L/hr per kW of rated capacity.
        Represents fuel consumed just to keep the engine spinning with no
        electrical load applied.
    a1 : float
        Slope (marginal) coefficient in L/hr per kW of electrical output.
        Represents additional fuel consumed for each kW of load served.

    Typical values for a standard diesel genset:
        a0 ~ 0.0845 L/hr/kW-rated
        a1 ~ 0.2460 L/hr/kW-output

    References
    ----------
    HOMER Energy modelling methodology; Barley & Winn (1996).
    """

    a0: float = 0.0845
    a1: float = 0.2460

    # Energy content of diesel fuel (kWh_thermal per litre).
    _DIESEL_ENERGY_CONTENT_KWH_PER_L: float = 10.0

    def __post_init__(self) -> None:
        if self.a0 < 0:
            raise ValueError(f"a0 must be >= 0, got {self.a0}")
        if self.a1 <= 0:
            raise ValueError(f"a1 must be > 0, got {self.a1}")

    def consumption(self, power_output_kw: float, rated_power_kw: float) -> float:
        """Calculate fuel consumption at a given operating point.

        Parameters
        ----------
        power_output_kw : float
            Current electrical output of the generator (kW).
            Must be in [0, rated_power_kw].
        rated_power_kw : float
            Nameplate rated capacity of the generator (kW).

        Returns
        -------
        float
            Fuel consumption in litres per hour (L/hr).

        Raises
        ------
        ValueError
            If power_output_kw is negative or exceeds rated_power_kw.
        """
        if power_output_kw < 0:
            raise ValueError(
                f"power_output_kw must be >= 0, got {power_output_kw}"
            )
        if power_output_kw > rated_power_kw * 1.001:  # small tolerance
            raise ValueError(
                f"power_output_kw ({power_output_kw}) exceeds "
                f"rated_power_kw ({rated_power_kw})"
            )

        # Clamp to rated capacity (handles floating-point overshoot).
        power_output_kw = min(power_output_kw, rated_power_kw)

        return self.a0 * rated_power_kw + self.a1 * power_output_kw

    def efficiency(self, power_output_kw: float, rated_power_kw: float) -> float:
        """Electrical conversion efficiency at a given operating point.

        Parameters
        ----------
        power_output_kw : float
            Current electrical output of the generator (kW).
        rated_power_kw : float
            Nameplate rated capacity of the generator (kW).

        Returns
        -------
        float
            Efficiency expressed as kWh of electricity produced per litre of
            fuel consumed (kWh_e / L).  Returns 0.0 when power_output_kw
            is zero (engine idling).
        """
        if power_output_kw <= 0:
            return 0.0

        fuel_l_per_hr = self.consumption(power_output_kw, rated_power_kw)
        return power_output_kw / fuel_l_per_hr

    def thermal_efficiency(
        self, power_output_kw: float, rated_power_kw: float
    ) -> float:
        """Fraction of fuel thermal energy converted to electricity.

        Parameters
        ----------
        power_output_kw : float
            Current electrical output of the generator (kW).
        rated_power_kw : float
            Nameplate rated capacity of the generator (kW).

        Returns
        -------
        float
            Dimensionless efficiency in [0, 1].  Returns 0.0 when the
            generator is idling (zero output).
        """
        kwh_per_l = self.efficiency(power_output_kw, rated_power_kw)
        return kwh_per_l / self._DIESEL_ENERGY_CONTENT_KWH_PER_L
