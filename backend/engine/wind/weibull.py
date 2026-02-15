"""Weibull distribution analysis and wind turbine hourly simulation.

Combines wind resource correction, power curve interpolation, and
Weibull-based analytical energy estimation into a single module for
8760-hour grid simulations.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.special import gamma as gamma_fn

from engine.wind.power_curve import PowerCurve, generic_power_curve
from engine.wind.wind_resource import air_density_correction, height_correction


# ======================================================================
# Weibull parameter estimation
# ======================================================================

def weibull_params(
    wind_speeds: NDArray[np.floating],
) -> tuple[float, float]:
    """Estimate Weibull *k* (shape) and *c* (scale) via method of moments.

    The Weibull probability density function is:

    .. math::

        f(v) = \\frac{k}{c}\\left(\\frac{v}{c}\\right)^{k-1}
               \\exp\\!\\left[-\\left(\\frac{v}{c}\\right)^k\\right]

    Parameters
    ----------
    wind_speeds : ndarray
        Observed (positive) wind speed samples (m/s).  Zero and negative
        values are silently excluded before fitting.

    Returns
    -------
    k : float
        Weibull shape parameter (dimensionless).  Typical range 1.5 -- 3.0.
    c : float
        Weibull scale parameter (m/s).

    Raises
    ------
    ValueError
        If fewer than two positive wind speeds remain after filtering.

    Notes
    -----
    The method-of-moments estimator uses the mean and standard deviation:

    .. math::

        \\hat{k} \\approx \\left(\\frac{\\sigma}{\\bar{v}}\\right)^{-1.086}

    .. math::

        \\hat{c} = \\frac{\\bar{v}}{\\Gamma(1 + 1/\\hat{k})}

    This is a fast, closed-form approximation well-suited for hourly
    datasets.  For maximum-likelihood fits use :mod:`scipy.stats.weibull_min`.
    """
    ws = np.asarray(wind_speeds, dtype=np.float64)
    ws = ws[ws > 0]

    if len(ws) < 2:
        raise ValueError(
            "At least 2 positive wind speed values are required to fit "
            "Weibull parameters."
        )

    mean_v = float(np.mean(ws))
    std_v = float(np.std(ws, ddof=0))

    if std_v == 0:
        # Degenerate case: all speeds identical.
        return (10.0, mean_v)  # Very peaked distribution.

    # Justus & Mikhail (1976) approximation.
    k = (std_v / mean_v) ** (-1.086)
    c = mean_v / gamma_fn(1.0 + 1.0 / k)

    return (float(k), float(c))


# ======================================================================
# Analytical AEP via Weibull integration
# ======================================================================

def weibull_aep(
    power_curve: PowerCurve,
    k: float,
    c: float,
    hours: float = 8760.0,
) -> float:
    """Estimate annual energy production analytically using the Weibull PDF.

    Numerically integrates the product of the power curve and the Weibull
    probability density over the operational wind-speed range.

    Parameters
    ----------
    power_curve : PowerCurve
        Turbine power curve object.
    k : float
        Weibull shape parameter.
    c : float
        Weibull scale parameter (m/s).
    hours : float, optional
        Number of hours in the analysis period.  Default 8760 (one year).

    Returns
    -------
    float
        Estimated energy production (kWh) over the specified period.
    """
    # Dense evaluation grid spanning the power curve's operational range.
    n_bins = 200
    v = np.linspace(0.0, power_curve.cut_out + 1.0, n_bins)

    # Weibull PDF: f(v) = (k/c)(v/c)^(k-1) * exp(-(v/c)^k)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdf = (k / c) * (v / c) ** (k - 1) * np.exp(-((v / c) ** k))
    pdf = np.nan_to_num(pdf, nan=0.0, posinf=0.0, neginf=0.0)

    power = power_curve.interpolate(v)

    # Trapezoidal integration over wind speed.
    energy_density = np.trapz(power * pdf, v)  # kW (mean)
    aep = energy_density * hours  # kWh

    return float(aep)


# ======================================================================
# Full hourly simulation
# ======================================================================

def simulate_wind_turbine(
    rated_power_kw: float,
    hub_height: float,
    rotor_diameter: float,
    wind_speed_8760: NDArray[np.floating],
    temp_8760: NDArray[np.floating],
    config: dict[str, Any] | None = None,
) -> NDArray[np.floating]:
    """Simulate hourly wind turbine power output over a year.

    Pipeline:
    1. Height-correct measured wind speeds to hub height.
    2. Apply air-density correction using ambient temperature.
    3. Evaluate the power curve (user-supplied or generic cubic).
    4. Multiply by turbine quantity for wind-farm output.

    Parameters
    ----------
    rated_power_kw : float
        Single turbine nameplate rated power (kW).
    hub_height : float
        Turbine hub height (m).
    rotor_diameter : float
        Rotor diameter (m).  Not currently used in the power curve but
        reserved for future wake / swept-area models.
    wind_speed_8760 : ndarray, shape (8760,)
        Hourly wind speeds (m/s) at the measurement height.
    temp_8760 : ndarray, shape (8760,)
        Hourly ambient temperatures (degrees Celsius).
    config : dict or None, optional
        Additional turbine configuration.  Recognised keys:

        * ``"measurement_height"`` (float) -- Anemometer height in metres.
          Default 10.0.
        * ``"roughness_length"`` (float) -- Surface roughness z0 (m).
          Default 0.03.
        * ``"shear_method"`` (str) -- ``"log_law"`` or ``"power_law"``.
          Default ``"log_law"``.
        * ``"shear_exponent"`` (float) -- Alpha for power-law.  Default
          ``1/7``.
        * ``"cut_in_speed"`` (float) -- Cut-in speed (m/s).  Default 3.0.
        * ``"rated_speed"`` (float) -- Rated speed (m/s).  Default 12.0.
        * ``"cut_out_speed"`` (float) -- Cut-out speed (m/s).  Default 25.0.
        * ``"power_curve"`` (list[list[float]]) -- Explicit power curve as
          ``[[speed, power], ...]``.  Overrides generic curve when present.
        * ``"quantity"`` (int) -- Number of identical turbines.  Default 1.
        * ``"pressure"`` (float or ndarray) -- Atmospheric pressure (Pa).
          Default 101 325.
        * ``"availability"`` (float) -- Fraction of time turbine is
          operational, 0-1.  Default 1.0 (no downtime).

    Returns
    -------
    ndarray, shape (8760,)
        Hourly power output (kW) for the entire wind farm (i.e. single
        turbine output multiplied by *quantity*).

    Raises
    ------
    ValueError
        If input arrays do not have length 8760.
    """
    config = config or {}

    wind_speed_8760 = np.asarray(wind_speed_8760, dtype=np.float64)
    temp_8760 = np.asarray(temp_8760, dtype=np.float64)

    if wind_speed_8760.shape[0] != 8760:
        raise ValueError(
            f"wind_speed_8760 must have 8760 elements, got {wind_speed_8760.shape[0]}"
        )
    if temp_8760.shape[0] != 8760:
        raise ValueError(
            f"temp_8760 must have 8760 elements, got {temp_8760.shape[0]}"
        )

    # --- Unpack configuration with defaults ---
    measurement_height: float = float(config.get("measurement_height", 10.0))
    roughness_length: float = float(config.get("roughness_length", 0.03))
    shear_method: str = str(config.get("shear_method", "log_law"))
    shear_exponent: float | None = config.get("shear_exponent")
    cut_in: float = float(config.get("cut_in_speed", 3.0))
    rated_speed: float = float(config.get("rated_speed", 12.0))
    cut_out: float = float(config.get("cut_out_speed", 25.0))
    quantity: int = int(config.get("quantity", 1))
    pressure: float | NDArray[np.floating] = config.get("pressure", 101325.0)
    availability: float = float(config.get("availability", 1.0))

    # --- Step 1: Height correction ---
    ws_hub = height_correction(
        wind_speed=wind_speed_8760,
        measurement_height=measurement_height,
        hub_height=hub_height,
        roughness_length=roughness_length,
        method=shear_method,
        shear_exponent=shear_exponent,
    )

    # --- Step 2: Air-density correction ---
    ws_eff = air_density_correction(
        wind_speed=ws_hub,
        temperature=temp_8760,
        pressure=pressure,
    )

    # --- Step 3: Power curve ---
    user_curve: list[list[float]] | None = config.get("power_curve")
    if user_curve is not None and len(user_curve) >= 2:
        pairs = np.asarray(user_curve, dtype=np.float64)
        pc = PowerCurve(wind_speeds=pairs[:, 0], power_values=pairs[:, 1])
    else:
        pc = generic_power_curve(
            rated_power_kw=rated_power_kw,
            cut_in=cut_in,
            rated_speed=rated_speed,
            cut_out=cut_out,
        )

    power_single = pc.interpolate(ws_eff)

    # --- Step 4: Apply availability and quantity multiplier ---
    power_single *= availability

    # Ensure non-negative (guard against floating-point artefacts).
    np.clip(power_single, 0.0, None, out=power_single)

    power_farm = power_single * quantity

    return power_farm
