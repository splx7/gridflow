"""
Sandia inverter performance model.

Converts DC power and voltage from one or more PV strings into AC power
output, accounting for self-consumption (tare) losses, voltage-dependent
efficiency, and AC power clipping at rated capacity.

References
----------
- King D.L., Gonzalez S., Galbraith G.M., Boyson W.E., "Performance
  Model for Grid-Connected Photovoltaic Inverters", Sandia National
  Laboratories, SAND2007-5036, 2007.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def sandia_inverter(
    p_dc: NDArray[np.float64],
    v_dc: NDArray[np.float64],
    Paco: float,
    Pdco: float,
    Vdco: float,
    Pso: float,
    C0: float,
    C1: float,
    C2: float,
    C3: float,
) -> NDArray[np.float64]:
    """Compute AC power from DC power using the Sandia inverter model.

    The model equation is::

        A = Pdco * (1 + C1 * (Vdc - Vdco))
        B = Pso  * (1 + C2 * (Vdc - Vdco))
        C = C0   * (1 + C3 * (Vdc - Vdco))
        Pac = (Paco / (A - B)) * (Pdc - B) - C * (Pdc - B)^2 / (A - B)

    where ``Pdc > Pso`` (otherwise the inverter is off).

    Parameters
    ----------
    p_dc : ndarray
        DC power input to the inverter (W). Negative values (nighttime)
        are interpreted as zero generation.
    v_dc : ndarray
        DC voltage input to the inverter (V). Should be within the
        inverter's MPPT window for meaningful results.
    Paco : float
        Rated AC power output (W). Inverter clips at this value.
    Pdco : float
        DC power level at which the inverter reaches ``Paco`` (W),
        accounting for inverter losses.
    Vdco : float
        DC voltage at which the inverter parameters are defined (V).
    Pso : float
        DC power required to start the inversion process / self-
        consumption (W). When ``p_dc < Pso`` the output is zero
        (night-time tare loss is applied as a separate term).
    C0 : float
        Parameter defining the curvature of the relationship between
        AC power and DC power at the reference operating condition.
        Units: 1/W.
    C1 : float
        Empirical coefficient relating ``Pdco`` to DC voltage. Units:
        1/V.
    C2 : float
        Empirical coefficient relating ``Pso`` to DC voltage. Units:
        1/V.
    C3 : float
        Empirical coefficient relating ``C0`` to DC voltage. Units:
        1/V.

    Returns
    -------
    p_ac : ndarray
        AC power output (W). Clipped to [``-Pso``, ``Paco``].

        - When the inverter is producing power, ``p_ac`` is in
          ``[0, Paco]``.
        - When the inverter is off at night (``p_dc <= 0``), ``p_ac``
          equals ``-Pso`` representing the night-time tare / standby
          loss. Set ``Pso = 0`` to disable tare losses.
    """
    p_dc = np.asarray(p_dc, dtype=np.float64)
    v_dc = np.asarray(v_dc, dtype=np.float64)

    p_ac = np.full_like(p_dc, -Pso)  # default: tare loss when off

    # Voltage deviation from reference
    dv = v_dc - Vdco

    # Voltage-adjusted parameters
    A = Pdco * (1.0 + C1 * dv)
    B = Pso * (1.0 + C2 * dv)
    C = C0 * (1.0 + C3 * dv)

    # Inverter is on when DC power exceeds the self-consumption threshold
    on = p_dc > Pso

    if np.any(on):
        # Avoid division by zero
        A_on = A[on]
        B_on = B[on]
        C_on = C[on]
        p_dc_on = p_dc[on]

        denom = A_on - B_on
        # Guard against zero denominator (shouldn't happen with valid params)
        denom = np.where(np.abs(denom) < 1e-10, 1e-10, denom)

        p_diff = p_dc_on - B_on

        pac_on = (Paco / denom) * p_diff - C_on * (p_diff ** 2) / denom

        # Clip to rated AC output
        pac_on = np.clip(pac_on, 0.0, Paco)

        p_ac[on] = pac_on

    # Daytime but below start threshold: zero output (not tare loss)
    below_start = (p_dc > 0.0) & (~on)
    p_ac[below_start] = 0.0

    return p_ac


def sandia_inverter_simple(
    p_dc: NDArray[np.float64],
    efficiency: float,
    Paco: float,
    Pso: float = 0.0,
) -> NDArray[np.float64]:
    """Simplified inverter model using a fixed efficiency.

    Useful when detailed Sandia parameters are not available.

    Parameters
    ----------
    p_dc : ndarray
        DC power input (W).
    efficiency : float
        Constant conversion efficiency (0-1). Typical value 0.96.
    Paco : float
        Rated AC power (W).
    Pso : float
        Night-time tare / standby loss (W). Default 0.

    Returns
    -------
    p_ac : ndarray
        AC power output (W).
    """
    p_dc = np.asarray(p_dc, dtype=np.float64)
    p_ac = np.where(p_dc > 0.0, p_dc * efficiency, -Pso)
    p_ac = np.clip(p_ac, -Pso, Paco)
    return p_ac
