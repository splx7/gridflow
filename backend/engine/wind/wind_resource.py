"""Wind resource processing: height correction and air density adjustments.

Provides vectorized functions for converting measured wind speed data to
hub-height conditions, suitable for 8760-hour annual simulations.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Height correction
# ---------------------------------------------------------------------------

def height_correction(
    wind_speed: NDArray[np.floating],
    measurement_height: float,
    hub_height: float,
    roughness_length: float = 0.03,
    method: str = "log_law",
    shear_exponent: float | None = None,
) -> NDArray[np.floating]:
    """Adjust wind speed from measurement height to turbine hub height.

    Parameters
    ----------
    wind_speed : ndarray
        Measured wind speeds (m/s) at *measurement_height*.
    measurement_height : float
        Height of the measurement sensor (m).  Must be > 0.
    hub_height : float
        Target turbine hub height (m).  Must be > 0.
    roughness_length : float, optional
        Surface roughness length z0 (m).  Only used when *method* is
        ``"log_law"``.  Default 0.03 (open agricultural land).
    method : {"log_law", "power_law"}
        Wind-shear extrapolation method.

        * ``"log_law"`` -- Logarithmic wind profile (default).
        * ``"power_law"`` -- Power-law profile; requires *shear_exponent*.
    shear_exponent : float or None, optional
        Wind-shear exponent alpha for the power-law method.  Typical values
        range from 0.10 (smooth terrain / water) to 0.30 (urban / forest).
        If *None* and ``method="power_law"``, a default of 0.143 (1/7 rule)
        is used.

    Returns
    -------
    ndarray
        Wind speeds (m/s) corrected to *hub_height*.

    Raises
    ------
    ValueError
        If *measurement_height*, *hub_height*, or *roughness_length* are
        non-positive, or if an unsupported *method* is specified.
    """
    wind_speed = np.asarray(wind_speed, dtype=np.float64)

    if measurement_height <= 0:
        raise ValueError(f"measurement_height must be > 0, got {measurement_height}")
    if hub_height <= 0:
        raise ValueError(f"hub_height must be > 0, got {hub_height}")

    # Short-circuit when heights match.
    if np.isclose(measurement_height, hub_height):
        return wind_speed.copy()

    if method == "log_law":
        if roughness_length <= 0:
            raise ValueError(
                f"roughness_length must be > 0 for log_law, got {roughness_length}"
            )
        correction = (
            np.log(hub_height / roughness_length)
            / np.log(measurement_height / roughness_length)
        )
    elif method == "power_law":
        alpha = shear_exponent if shear_exponent is not None else 1.0 / 7.0
        correction = (hub_height / measurement_height) ** alpha
    else:
        raise ValueError(
            f"Unsupported method '{method}'. Use 'log_law' or 'power_law'."
        )

    return wind_speed * correction


# ---------------------------------------------------------------------------
# Air density correction
# ---------------------------------------------------------------------------

# Physical constants
_GAS_CONSTANT_DRY_AIR: float = 287.058  # J/(kg*K)
_STANDARD_AIR_DENSITY: float = 1.225    # kg/m^3 at 15 degC, 101325 Pa


def air_density_correction(
    wind_speed: NDArray[np.floating],
    temperature: NDArray[np.floating] | float,
    pressure: NDArray[np.floating] | float = 101325.0,
) -> NDArray[np.floating]:
    """Apply air-density correction to wind speed using the equivalent power
    method.

    The correction converts from standard-air-density conditions to site
    conditions so that the kinetic energy flux (and therefore the turbine
    power) remains consistent when evaluated against a standard-density
    power curve.

    .. math::

        v_{\\text{eff}} = v \\left(\\frac{\\rho}{\\rho_0}\\right)^{1/3}

    Parameters
    ----------
    wind_speed : ndarray
        Wind speeds (m/s), typically already height-corrected.
    temperature : ndarray or float
        Ambient temperature(s) in **degrees Celsius**.
    pressure : ndarray or float, optional
        Atmospheric pressure(s) in Pa.  Default is standard sea-level
        pressure (101 325 Pa).

    Returns
    -------
    ndarray
        Density-corrected effective wind speeds (m/s).

    Notes
    -----
    Air density is computed from the ideal gas law for dry air:

    .. math::

        \\rho = \\frac{P}{R_d \\cdot T_K}

    where *R_d* = 287.058 J/(kg K) and *T_K* is the absolute temperature.
    """
    wind_speed = np.asarray(wind_speed, dtype=np.float64)
    temperature_k = np.asarray(temperature, dtype=np.float64) + 273.15
    pressure = np.asarray(pressure, dtype=np.float64)

    # Guard against division by zero for extremely cold temperatures.
    temperature_k = np.maximum(temperature_k, 1.0)

    rho = pressure / (_GAS_CONSTANT_DRY_AIR * temperature_k)
    density_ratio = rho / _STANDARD_AIR_DENSITY

    # Cube-root correction preserves kinetic energy equivalence.
    return wind_speed * np.cbrt(density_ratio)
