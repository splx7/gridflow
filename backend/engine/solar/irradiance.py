"""
Irradiance transposition module for converting horizontal irradiance
components (GHI, DNI, DHI) to plane-of-array (POA) irradiance using
the Perez 1990 anisotropic diffuse sky model.

References
----------
- Perez R. et al., "Modeling daylight availability and irradiance
  components from direct and global irradiance", Solar Energy,
  44(5):271-289, 1990.
- Spencer J.W., "Fourier series representation of the position of
  the sun", Search, 2(5):172, 1971.
- Iqbal M., "An Introduction to Solar Energy", Academic Press, 1983.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Perez 1990 brightness coefficients
# 8 sky-clearness (epsilon) bins, each row: [f11, f12, f13, f21, f22, f23]
# Bin edges for epsilon: [1, 1.065, 1.23, 1.5, 1.95, 2.8, 4.5, 6.2, inf]
# ---------------------------------------------------------------------------
_PEREZ_COEFFS = np.array(
    [
        [-0.0083, 0.5877, -0.0621, -0.0596, 0.0721, -0.0220],  # bin 1
        [0.1299, 0.6826, -0.1514, -0.0189, 0.0660, -0.0289],   # bin 2
        [0.3297, 0.4869, -0.2211, 0.0554, -0.0640, -0.0261],   # bin 3
        [0.5682, 0.1875, -0.2951, 0.1089, -0.1519, -0.0140],   # bin 4
        [0.8730, -0.3920, -0.3616, 0.2256, -0.4620, 0.0012],   # bin 5
        [1.1326, -1.2367, -0.4118, 0.2878, -0.8230, 0.0559],   # bin 6
        [1.0602, -1.5999, -0.3589, 0.2642, -1.1272, 0.1311],   # bin 7
        [0.6777, -0.3273, -0.2504, 0.1561, -1.3765, 0.2506],   # bin 8
    ],
    dtype=np.float64,
)

_PEREZ_EPSILON_BINS = np.array(
    [1.0, 1.065, 1.23, 1.5, 1.95, 2.8, 4.5, 6.2, np.inf],
    dtype=np.float64,
)


def solar_position(
    day_of_year: NDArray[np.float64] | float,
    hour: NDArray[np.float64] | float,
    latitude: float,
    longitude: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Compute solar zenith and azimuth angles using Spencer's equations.

    This implements an approximation suitable for engineering calculations
    (accuracy ~1 degree). For higher fidelity, an ephemeris algorithm such
    as SPA should be used.

    Parameters
    ----------
    day_of_year : array_like
        Day of year (1-365/366).
    hour : array_like
        Hour of day in *solar time* (0-23.999). For standard-time inputs
        the caller should apply the equation-of-time and longitude
        corrections before calling this function.
    latitude : float
        Site latitude in degrees (positive north).
    longitude : float
        Site longitude in degrees (positive east). Used only for the
        equation-of-time correction when converting from local standard
        time; the ``hour`` parameter is assumed to already be in solar
        time so ``longitude`` is accepted for API consistency but is not
        applied internally.

    Returns
    -------
    zenith : ndarray
        Solar zenith angle in degrees [0, 180].
    azimuth : ndarray
        Solar azimuth angle in degrees, measured clockwise from north
        [0, 360).
    """
    day_of_year = np.asarray(day_of_year, dtype=np.float64)
    hour = np.asarray(hour, dtype=np.float64)

    # Day angle (radians) -- Spencer convention
    day_angle = 2.0 * np.pi * (day_of_year - 1.0) / 365.0

    # Declination (radians) -- Spencer's Fourier series
    declination = (
        0.006918
        - 0.399912 * np.cos(day_angle)
        + 0.070257 * np.sin(day_angle)
        - 0.006758 * np.cos(2.0 * day_angle)
        + 0.000907 * np.sin(2.0 * day_angle)
        - 0.002697 * np.cos(3.0 * day_angle)
        + 0.00148 * np.sin(3.0 * day_angle)
    )

    # Hour angle (radians): solar noon = 0, morning negative
    hour_angle = np.radians((hour - 12.0) * 15.0)

    lat_rad = np.radians(latitude)

    # Solar zenith via spherical-trig identity
    cos_zenith = (
        np.sin(lat_rad) * np.sin(declination)
        + np.cos(lat_rad) * np.cos(declination) * np.cos(hour_angle)
    )
    cos_zenith = np.clip(cos_zenith, -1.0, 1.0)
    zenith = np.degrees(np.arccos(cos_zenith))

    # Solar azimuth (clockwise from north)
    sin_zenith = np.sin(np.radians(zenith))
    # Guard against division by zero at zenith=0 or 180
    sin_zenith_safe = np.where(np.abs(sin_zenith) < 1e-6, 1e-6, sin_zenith)

    cos_azimuth = (
        np.sin(declination) - np.cos(np.radians(zenith)) * np.sin(lat_rad)
    ) / (sin_zenith_safe * np.cos(lat_rad))
    cos_azimuth = np.clip(cos_azimuth, -1.0, 1.0)

    azimuth = np.degrees(np.arccos(cos_azimuth))
    # Afternoon: azimuth > 180
    azimuth = np.where(hour_angle > 0, 360.0 - azimuth, azimuth)

    return zenith, azimuth


def aoi(
    surface_tilt: float,
    surface_azimuth: float,
    solar_zenith: NDArray[np.float64],
    solar_azimuth: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Angle of incidence between the sun vector and the surface normal.

    Parameters
    ----------
    surface_tilt : float
        Surface tilt from horizontal in degrees [0, 180].
    surface_azimuth : float
        Surface azimuth in degrees clockwise from north [0, 360).
    solar_zenith : ndarray
        Solar zenith angle in degrees.
    solar_azimuth : ndarray
        Solar azimuth angle in degrees.

    Returns
    -------
    ndarray
        Angle of incidence in degrees, clipped to [0, 90].
    """
    tilt_r = np.radians(surface_tilt)
    saz_r = np.radians(surface_azimuth)
    sz_r = np.radians(solar_zenith)
    sa_r = np.radians(solar_azimuth)

    cos_aoi = (
        np.cos(sz_r) * np.cos(tilt_r)
        + np.sin(sz_r) * np.sin(tilt_r) * np.cos(sa_r - saz_r)
    )
    cos_aoi = np.clip(cos_aoi, -1.0, 1.0)
    angle = np.degrees(np.arccos(cos_aoi))

    # Clamp: sun behind the surface contributes nothing
    return np.clip(angle, 0.0, 90.0)


def _extraterrestrial_normal_irradiance(
    day_of_year: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Normal extraterrestrial irradiance (W/m^2) accounting for
    Earth-Sun distance variation (Spencer's equation)."""
    day_angle = 2.0 * np.pi * (day_of_year - 1.0) / 365.0
    e0 = (
        1.000110
        + 0.034221 * np.cos(day_angle)
        + 0.001280 * np.sin(day_angle)
        + 0.000719 * np.cos(2.0 * day_angle)
        + 0.000077 * np.sin(2.0 * day_angle)
    )
    return 1361.0 * e0  # W/m^2 (solar constant ~1361 W/m^2)


def _perez_bin_index(epsilon: NDArray[np.float64]) -> NDArray[np.intp]:
    """Map sky-clearness epsilon to Perez brightness-bin index (0-7)."""
    return np.clip(
        np.searchsorted(_PEREZ_EPSILON_BINS, epsilon, side="right") - 1,
        0,
        7,
    )


def perez_transposition(
    ghi: NDArray[np.float64],
    dni: NDArray[np.float64],
    dhi: NDArray[np.float64],
    solar_zenith: NDArray[np.float64],
    surface_tilt: float,
    surface_azimuth: float,
    day_of_year: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Transpose GHI / DNI / DHI to plane-of-array irradiance using the
    Perez 1990 anisotropic diffuse model.

    Parameters
    ----------
    ghi : ndarray, shape (N,)
        Global horizontal irradiance (W/m^2).
    dni : ndarray, shape (N,)
        Direct normal irradiance (W/m^2).
    dhi : ndarray, shape (N,)
        Diffuse horizontal irradiance (W/m^2).
    solar_zenith : ndarray, shape (N,)
        Solar zenith angle (degrees).
    surface_tilt : float
        Surface tilt angle from horizontal (degrees).
    surface_azimuth : float
        Surface azimuth, clockwise from north (degrees).
    day_of_year : ndarray, shape (N,)
        Day of year (1-366).

    Returns
    -------
    poa : ndarray, shape (N,)
        Total plane-of-array irradiance (W/m^2). Negative values are
        clipped to zero.
    """
    # This convenience function does not receive solar_azimuth. It
    # delegates to _perez_core with solar_azimuth=None, which falls
    # back to a due-south (180 deg) assumption for the beam AOI.
    # For accurate results, prefer perez_transposition_full() which
    # accepts explicit solar azimuth -- the system-level module
    # (pv_system.py) always uses that variant.
    return _perez_core(
        ghi, dni, dhi, solar_zenith, None, surface_tilt, surface_azimuth,
        day_of_year,
    )


def perez_transposition_full(
    ghi: NDArray[np.float64],
    dni: NDArray[np.float64],
    dhi: NDArray[np.float64],
    solar_zenith: NDArray[np.float64],
    solar_azimuth: NDArray[np.float64],
    surface_tilt: float,
    surface_azimuth: float,
    day_of_year: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Perez transposition with explicit solar azimuth.

    Preferred entry-point when solar azimuth is already computed
    (avoids the rough south-facing assumption).  Parameters are
    identical to :func:`perez_transposition` with the addition of
    ``solar_azimuth``.
    """
    return _perez_core(
        ghi, dni, dhi, solar_zenith, solar_azimuth,
        surface_tilt, surface_azimuth, day_of_year,
    )


def _perez_core(
    ghi: NDArray[np.float64],
    dni: NDArray[np.float64],
    dhi: NDArray[np.float64],
    solar_zenith: NDArray[np.float64],
    solar_azimuth: NDArray[np.float64] | None,
    surface_tilt: float,
    surface_azimuth: float,
    day_of_year: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Core Perez transposition implementation."""
    ghi = np.asarray(ghi, dtype=np.float64)
    dni = np.asarray(dni, dtype=np.float64)
    dhi = np.asarray(dhi, dtype=np.float64)
    solar_zenith = np.asarray(solar_zenith, dtype=np.float64)
    day_of_year = np.asarray(day_of_year, dtype=np.float64)

    n = ghi.shape[0]
    poa = np.zeros(n, dtype=np.float64)

    tilt_rad = np.radians(surface_tilt)
    sz_rad = np.radians(solar_zenith)
    cos_sz = np.cos(sz_rad)

    sun_up = (solar_zenith < 90.0) & (ghi > 0.0)
    if not np.any(sun_up):
        return poa

    # ---------- Beam on tilted surface ----------
    if solar_azimuth is not None:
        solar_azimuth = np.asarray(solar_azimuth, dtype=np.float64)
        angle_inc = aoi(surface_tilt, surface_azimuth, solar_zenith, solar_azimuth)
    else:
        # Fallback: assume sun is due south (180 deg) -- rough northern-
        # hemisphere approximation.  The system module always provides
        # the real value so this path is only for standalone testing.
        angle_inc = aoi(
            surface_tilt, surface_azimuth,
            solar_zenith, np.full(n, 180.0),
        )

    cos_aoi = np.cos(np.radians(angle_inc))
    beam_poa = np.where(sun_up, dni * np.maximum(cos_aoi, 0.0), 0.0)

    # ---------- Perez diffuse on tilted surface ----------
    # Air mass (Kasten & Young, 1989 approximation)
    am = np.where(
        sun_up,
        1.0 / (np.maximum(cos_sz, 0.0008)
               + 0.50572 * (96.07995 - solar_zenith) ** (-1.6364)),
        0.0,
    )

    # Extraterrestrial normal irradiance
    etn = _extraterrestrial_normal_irradiance(day_of_year)

    # Sky brightness (Delta)
    delta = np.where(sun_up, dhi * am / etn, 0.0)

    # Sky clearness (epsilon) -- avoid division by zero
    dhi_safe = np.where(dhi > 0.0, dhi, 1.0)
    kappa = 1.041  # constant in Perez epsilon formula
    epsilon = np.where(
        sun_up & (dhi > 0.0),
        ((dhi + dni) / dhi_safe + kappa * sz_rad ** 3)
        / (1.0 + kappa * sz_rad ** 3),
        1.0,  # overcast default
    )

    # Bin index
    bin_idx = _perez_bin_index(epsilon)

    # Perez brightness coefficients
    f11 = _PEREZ_COEFFS[bin_idx, 0]
    f12 = _PEREZ_COEFFS[bin_idx, 1]
    f13 = _PEREZ_COEFFS[bin_idx, 2]
    f21 = _PEREZ_COEFFS[bin_idx, 3]
    f22 = _PEREZ_COEFFS[bin_idx, 4]
    f23 = _PEREZ_COEFFS[bin_idx, 5]

    # F1 (circumsolar brightness) and F2 (horizon brightness)
    f1 = np.maximum(0.0, f11 + f12 * delta + f13 * sz_rad)
    f2 = f21 + f22 * delta + f23 * sz_rad

    # Geometric factors
    # a = max(0, cos(AOI)), b = max(cos(85 deg), cos(zenith))
    a = np.maximum(0.0, cos_aoi)
    b = np.maximum(np.cos(np.radians(85.0)), cos_sz)

    # Isotropic diffuse on tilted surface
    # dhi * (1 - F1) * (1 + cos(tilt))/2  +  dhi * F1 * a/b  +  dhi * F2 * sin(tilt)
    sky_diffuse = np.where(
        sun_up,
        dhi * (
            (1.0 - f1) * (1.0 + np.cos(tilt_rad)) / 2.0
            + f1 * a / np.where(b > 0, b, 1e-6)
            + f2 * np.sin(tilt_rad)
        ),
        0.0,
    )
    sky_diffuse = np.maximum(sky_diffuse, 0.0)

    # ---------- Ground-reflected component ----------
    albedo = 0.2  # default ground albedo
    ground_diffuse = ghi * albedo * (1.0 - np.cos(tilt_rad)) / 2.0
    ground_diffuse = np.where(sun_up, np.maximum(ground_diffuse, 0.0), 0.0)

    # ---------- Total POA ----------
    poa = beam_poa + sky_diffuse + ground_diffuse
    return np.maximum(poa, 0.0)
