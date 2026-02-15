"""Wind turbine power curve interpolation.

Provides the :class:`PowerCurve` class for mapping wind speeds to electrical
power output, and a helper to generate a generic cubic power curve when
manufacturer data is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# PowerCurve class
# ---------------------------------------------------------------------------

@dataclass
class PowerCurve:
    """Lookup table that maps wind speed to turbine electrical output.

    Internally stores sorted (wind_speed, power) pairs and uses
    :func:`numpy.interp` with clamping outside the operational range
    (cut-in to cut-out).

    Parameters
    ----------
    wind_speeds : array-like
        Reference wind speeds (m/s) in ascending order.
    power_values : array-like
        Corresponding power outputs (kW).  Must have the same length as
        *wind_speeds*.
    """

    wind_speeds: NDArray[np.floating] = field(repr=False)
    power_values: NDArray[np.floating] = field(repr=False)

    # Derived attributes (set in __post_init__).
    cut_in: float = field(init=False, repr=True)
    cut_out: float = field(init=False, repr=True)
    rated_power: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        self.wind_speeds = np.asarray(self.wind_speeds, dtype=np.float64)
        self.power_values = np.asarray(self.power_values, dtype=np.float64)

        if self.wind_speeds.shape != self.power_values.shape:
            raise ValueError(
                "wind_speeds and power_values must have the same length, "
                f"got {self.wind_speeds.shape} vs {self.power_values.shape}"
            )
        if len(self.wind_speeds) < 2:
            raise ValueError("At least two data points are required.")

        # Ensure ascending order.
        order = np.argsort(self.wind_speeds)
        self.wind_speeds = self.wind_speeds[order]
        self.power_values = self.power_values[order]

        # Identify operational range from the stored points.
        self.cut_in = float(self.wind_speeds[0])
        self.cut_out = float(self.wind_speeds[-1])
        self.rated_power = float(np.max(self.power_values))

    # ------------------------------------------------------------------
    # Core interpolation
    # ------------------------------------------------------------------

    def interpolate(self, wind_speeds: NDArray[np.floating]) -> NDArray[np.floating]:
        """Evaluate power output for an array of wind speeds.

        Parameters
        ----------
        wind_speeds : ndarray
            Query wind speeds (m/s), arbitrary shape.

        Returns
        -------
        ndarray
            Power output (kW).  Values outside the cut-in / cut-out range
            are clamped to zero.
        """
        ws = np.asarray(wind_speeds, dtype=np.float64)

        power = np.interp(ws, self.wind_speeds, self.power_values)

        # Zero output below cut-in and above cut-out.
        power = np.where(ws < self.cut_in, 0.0, power)
        power = np.where(ws > self.cut_out, 0.0, power)

        return power


# ---------------------------------------------------------------------------
# Generic power curve generator
# ---------------------------------------------------------------------------

def generic_power_curve(
    rated_power_kw: float,
    cut_in: float = 3.0,
    rated_speed: float = 12.0,
    cut_out: float = 25.0,
    n_points: int = 100,
) -> PowerCurve:
    """Generate a generic cubic power curve for a wind turbine.

    The curve follows a cubic relationship between *cut_in* and
    *rated_speed*, then holds constant at *rated_power_kw* up to
    *cut_out*.

    .. math::

        P(v) = P_{\\text{rated}} \\cdot
               \\frac{v^3 - v_{\\text{ci}}^3}
                     {v_{\\text{rated}}^3 - v_{\\text{ci}}^3}
        \\quad v_{\\text{ci}} \\le v \\le v_{\\text{rated}}

    Parameters
    ----------
    rated_power_kw : float
        Nameplate rated power (kW).
    cut_in : float, optional
        Cut-in wind speed (m/s).  Default 3.0.
    rated_speed : float, optional
        Wind speed at which the turbine reaches rated power (m/s).
        Default 12.0.
    cut_out : float, optional
        Cut-out wind speed (m/s).  Default 25.0.
    n_points : int, optional
        Number of data points in the resulting curve.  Default 100.

    Returns
    -------
    PowerCurve
        A :class:`PowerCurve` instance ready for interpolation.

    Raises
    ------
    ValueError
        If the speed relationships ``0 < cut_in < rated_speed < cut_out``
        are not satisfied.
    """
    if not (0 < cut_in < rated_speed < cut_out):
        raise ValueError(
            "Speeds must satisfy 0 < cut_in < rated_speed < cut_out, "
            f"got cut_in={cut_in}, rated_speed={rated_speed}, cut_out={cut_out}"
        )

    # --- Build the piecewise curve ---
    # Region 1: cut_in -> rated_speed (cubic ramp)
    ramp_speeds = np.linspace(cut_in, rated_speed, max(n_points // 2, 10))
    v_ci_cubed = cut_in ** 3
    ramp_power = rated_power_kw * (
        (ramp_speeds ** 3 - v_ci_cubed) / (rated_speed ** 3 - v_ci_cubed)
    )

    # Region 2: rated_speed -> cut_out (flat at rated)
    flat_speeds = np.linspace(rated_speed, cut_out, max(n_points // 2, 10))
    flat_power = np.full_like(flat_speeds, rated_power_kw)

    # Concatenate (avoid duplicating the rated_speed point).
    all_speeds = np.concatenate([ramp_speeds, flat_speeds[1:]])
    all_power = np.concatenate([ramp_power, flat_power[1:]])

    return PowerCurve(wind_speeds=all_speeds, power_values=all_power)
