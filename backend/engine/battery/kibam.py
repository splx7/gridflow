"""
Kinetic Battery Model (KiBaM) for rate-dependent capacity modeling.

The KiBaM splits battery capacity into two wells:
  - Available charge well (q1): directly supplies the load.
  - Bound charge well (q2): feeds into q1 via a rate-limited conductance.

This captures the phenomenon where high discharge rates yield less usable
energy than low discharge rates, which is significant in lead-acid and
relevant in Li-ion chemistries.

Reference:
    Manwell, J.F. & McGowan, J.G. (1993). Lead acid battery storage model
    for hybrid energy systems. Solar Energy, 50(5), 399-405.
"""

from __future__ import annotations

import numpy as np


class KiBaMModel:
    """Kinetic Battery Model with two-well capacity representation.

    Parameters
    ----------
    q_max : float
        Total battery capacity in kWh (sum of both wells at full charge).
    c : float
        Capacity ratio -- fraction of total capacity in the available-charge
        well (0 < c < 1).  Typical values: 0.2-0.4 for lead-acid,
        0.6-0.8 for Li-ion.
    k : float
        Rate constant (1/h) governing charge flow between the bound well
        and the available well.  Higher *k* means the bound charge
        replenishes the available well faster.
    """

    def __init__(self, q_max: float, c: float, k: float) -> None:
        if q_max <= 0:
            raise ValueError(f"q_max must be positive, got {q_max}")
        if not 0 < c < 1:
            raise ValueError(f"c must be in (0, 1), got {c}")
        if k <= 0:
            raise ValueError(f"k must be positive, got {k}")

        self.q_max: float = q_max
        self.c: float = c
        self.k: float = k

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def available_capacity(self, discharge_rate: float, duration: float) -> float:
        """Usable capacity (kWh) at a constant *discharge_rate* over *duration*.

        At high C-rates the available well depletes before the bound well
        can replenish it, so usable capacity is less than ``q_max``.

        Parameters
        ----------
        discharge_rate : float
            Constant discharge power in kW.  Only the magnitude matters;
            negative values are treated as their absolute value.
        duration : float
            Discharge duration in hours.

        Returns
        -------
        float
            Usable energy in kWh, clamped to [0, q_max].
        """
        discharge_rate = abs(discharge_rate)
        if discharge_rate <= 0 or duration <= 0:
            return 0.0

        c, k, q_max = self.c, self.k, self.q_max
        t = duration

        # KiBaM closed-form for maximum extractable charge at constant
        # current over duration t, starting from full charge.
        #   q1_0 = c * q_max   (initial available charge)
        #   q2_0 = (1 - c) * q_max
        q1_0 = c * q_max
        q2_0 = (1.0 - c) * q_max

        exp_term = np.exp(-k * t)

        # Maximum extractable energy (Manwell & McGowan, Eq. 6):
        #   q_available = (q1_0 * exp(-kt) + q2_0 * k*c*t
        #                  - q2_0 * c * (1 - exp(-kt))
        #                  + q_max * k*c*t * (... ) ) -- simplified below.
        #
        # A cleaner equivalent from Manwell (1993):
        #   q_max_extractable =
        #       q_max * k * c * t + q1_0 * exp(-k*t)
        #       + q2_0 * (k * c * t - 1 + exp(-k*t))
        #   all divided by (1 - exp(-k*t) + k*c*t)

        numerator = (
            q_max * k * c * t
            + q1_0 * exp_term
            + q2_0 * (k * c * t - 1.0 + exp_term)
        )
        denominator = 1.0 - exp_term + k * c * t

        if denominator == 0:
            return 0.0

        q_available = numerator / denominator

        # The actual energy extracted is the minimum of what the battery
        # can supply and what is requested.
        requested = discharge_rate * t
        extracted = float(np.clip(min(q_available, requested), 0.0, q_max))
        return extracted

    def max_charge_power(self, soc: float, max_rate: float) -> float:
        """Maximum instantaneous charge power given current SOC.

        As the battery approaches full, the bound well saturates and
        limits the rate at which energy can be absorbed.

        Parameters
        ----------
        soc : float
            Current state of charge in [0, 1].
        max_rate : float
            Nameplate maximum charge power in kW (positive value).

        Returns
        -------
        float
            Allowable charge power in kW (>= 0).
        """
        max_rate = abs(max_rate)
        soc = float(np.clip(soc, 0.0, 1.0))

        if soc >= 1.0:
            return 0.0

        c, k, q_max = self.c, self.k, self.q_max

        # Current charge in each well.
        q_total = soc * q_max
        q1 = c * q_total
        q2 = (1.0 - c) * q_total

        # The available well can accept charge up to its capacity share.
        q1_max = c * q_max
        q1_room = q1_max - q1

        # Charge must flow *through* the available well and then into the
        # bound well via the conductance k.  The bound well can absorb at
        # rate k*(q1 - q2*c/(1-c)).  When q1 is relatively full compared
        # to q2, conductance drives charge into the bound well faster.
        if c < 1.0:
            conductance_flow = k * (q1 / c - q2 / (1.0 - c))
        else:
            conductance_flow = 0.0

        # A simplified upper bound: the available well must not overflow
        # within the next infinitesimal dt, accounting for drainage into
        # the bound well.
        kinetic_limit_kw = q1_room * k / c + conductance_flow
        kinetic_limit_kw = max(kinetic_limit_kw, 0.0)

        # Taper only in the last 15% of SOC range (realistic for Li-ion/LFP).
        # Full power available from 0% to 85% SOC; linear taper 85%→100%.
        taper_start = 0.85
        if soc < taper_start:
            soc_limit = max_rate
        else:
            soc_limit = max_rate * (1.0 - soc) / (1.0 - taper_start)

        return float(min(max_rate, kinetic_limit_kw, soc_limit))

    def max_discharge_power(self, soc: float, max_rate: float) -> float:
        """Maximum instantaneous discharge power given current SOC.

        At low SOC the available well is nearly empty and cannot sustain
        high discharge rates even though the bound well holds charge.

        Parameters
        ----------
        soc : float
            Current state of charge in [0, 1].
        max_rate : float
            Nameplate maximum discharge power in kW (positive value).

        Returns
        -------
        float
            Allowable discharge power in kW (>= 0).
        """
        max_rate = abs(max_rate)
        soc = float(np.clip(soc, 0.0, 1.0))

        if soc <= 0.0:
            return 0.0

        c, k, q_max = self.c, self.k, self.q_max

        q_total = soc * q_max
        q1 = c * q_total
        q2 = (1.0 - c) * q_total

        # The available well supplies the load directly.
        # The bound well feeds into the available well at a rate
        # proportional to the concentration difference.
        if c < 1.0:
            conductance_flow = k * (q2 / (1.0 - c) - q1 / c)
        else:
            conductance_flow = 0.0

        # Maximum instantaneous power: drain the available well plus
        # whatever the bound well can supply through the conductance.
        kinetic_limit_kw = q1 * k / c + max(conductance_flow, 0.0)
        kinetic_limit_kw = max(kinetic_limit_kw, 0.0)

        # Taper only in the last 15% of SOC range (realistic for Li-ion/LFP).
        # Full power available from 15% to 100% SOC; linear taper 0%→15%.
        taper_end = 0.15
        if soc > taper_end:
            soc_limit = max_rate
        else:
            soc_limit = max_rate * soc / taper_end

        return float(min(max_rate, kinetic_limit_kw, soc_limit))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"KiBaMModel(q_max={self.q_max}, c={self.c}, k={self.k})"
        )
