"""
Single-diode PV cell/module model based on De Soto et al. (2006).

Implements the five-parameter single-diode equivalent circuit and solves
for the maximum power point using the Lambert W function.

References
----------
- De Soto W., Klein S.A., Beckman W.A., "Improvement and validation of
  a model for photovoltaic array performance", Solar Energy,
  80(1):78-88, 2006.
- Jain A., Kapoor A., "Exact analytical solutions of the parameters of
  real solar cells using Lambert W-function", Solar Energy Materials
  and Solar Cells, 81(2):269-277, 2004.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.special import lambertw

# ---------------------------------------------------------------------------
# Physical / reference constants
# ---------------------------------------------------------------------------
Q_ELECTRON: float = 1.602176634e-19     # electron charge (C)
K_BOLTZMANN: float = 1.380649e-23        # Boltzmann constant (J/K)
T_REF: float = 298.15                    # STC cell temperature (K) = 25 degC
E_REF: float = 1000.0                    # STC irradiance (W/m^2)


@dataclass(frozen=True)
class DiodeParams:
    """Five translated single-diode parameters at operating conditions."""

    I_L: NDArray[np.float64]      # photo-generated current (A)
    I_o: NDArray[np.float64]      # diode saturation current (A)
    R_s: NDArray[np.float64]      # series resistance (Ohm)
    R_sh: NDArray[np.float64]     # shunt resistance (Ohm)
    nNsVth: NDArray[np.float64]   # modified ideality factor * Ns * Vth (V)


@dataclass(frozen=True)
class MPPResult:
    """Maximum-power-point operating values for a PV module."""

    I_mp: NDArray[np.float64]  # current at MPP (A)
    V_mp: NDArray[np.float64]  # voltage at MPP (V)
    P_mp: NDArray[np.float64]  # power at MPP (W)


# ---------------------------------------------------------------------------
# Cell temperature model (NOCT-based)
# ---------------------------------------------------------------------------

def cell_temperature(
    poa: NDArray[np.float64],
    t_amb: NDArray[np.float64],
    noct: float = 45.0,
) -> NDArray[np.float64]:
    """Estimate cell temperature using the NOCT model.

    Parameters
    ----------
    poa : ndarray
        Plane-of-array irradiance (W/m^2).
    t_amb : ndarray
        Ambient (dry-bulb) temperature (degC).
    noct : float
        Nominal Operating Cell Temperature (degC). Typical crystalline
        silicon value is 45 degC.

    Returns
    -------
    ndarray
        Cell temperature (degC).
    """
    poa = np.asarray(poa, dtype=np.float64)
    t_amb = np.asarray(t_amb, dtype=np.float64)
    return t_amb + (noct - 20.0) / 800.0 * poa


# ---------------------------------------------------------------------------
# De Soto parameter translation
# ---------------------------------------------------------------------------

def de_soto_params(
    irradiance_poa: NDArray[np.float64],
    cell_temp: NDArray[np.float64],
    I_L_ref: float,
    I_o_ref: float,
    R_s: float,
    R_sh_ref: float,
    a_ref: float,
    alpha_sc: float,
    E_g: float = 1.121,
) -> DiodeParams:
    """Translate reference single-diode parameters to operating conditions
    using the De Soto (2006) method.

    Parameters
    ----------
    irradiance_poa : ndarray
        Effective irradiance on the plane-of-array (W/m^2).
    cell_temp : ndarray
        Cell temperature (degC).
    I_L_ref : float
        Photo-current at STC (A).
    I_o_ref : float
        Diode saturation current at STC (A).
    R_s : float
        Series resistance at STC (Ohm). Assumed constant with conditions.
    R_sh_ref : float
        Shunt resistance at STC (Ohm).
    a_ref : float
        Modified ideality factor at STC (V). Equal to
        ``n * Ns * k * T_ref / q`` where *n* is the diode ideality
        factor and *Ns* is the number of cells in series.
    alpha_sc : float
        Short-circuit current temperature coefficient (A/K). Typically
        a small positive number.
    E_g : float
        Band-gap energy of the semiconductor (eV). Default 1.121 eV
        for crystalline silicon.

    Returns
    -------
    DiodeParams
        Translated parameters at each operating point.
    """
    irradiance_poa = np.asarray(irradiance_poa, dtype=np.float64)
    cell_temp = np.asarray(cell_temp, dtype=np.float64)

    # Cell temperature in Kelvin
    T_cell_K = cell_temp + 273.15
    dT = T_cell_K - T_REF  # temperature difference

    # Effective irradiance ratio
    E_ratio = irradiance_poa / E_REF

    # Modified ideality factor scales linearly with temperature
    nNsVth = a_ref * (T_cell_K / T_REF)

    # Photo-current: scales with irradiance and temperature
    I_L = E_ratio * (I_L_ref + alpha_sc * dT)

    # Diode saturation current: Arrhenius-like temperature dependence
    E_g_J = E_g * Q_ELECTRON  # convert eV -> Joules
    I_o = I_o_ref * (T_cell_K / T_REF) ** 3 * np.exp(
        E_g_J / K_BOLTZMANN * (1.0 / T_REF - 1.0 / T_cell_K)
    )

    # Series resistance -- assumed independent of conditions
    R_s_arr = np.full_like(irradiance_poa, R_s)

    # Shunt resistance -- inversely proportional to irradiance
    R_sh = R_sh_ref / np.where(E_ratio > 0.0, E_ratio, 1.0)

    return DiodeParams(I_L=I_L, I_o=I_o, R_s=R_s_arr, R_sh=R_sh, nNsVth=nNsVth)


# ---------------------------------------------------------------------------
# Single-diode equation solver (Lambert W approach)
# ---------------------------------------------------------------------------

def single_diode_solve(
    I_L: NDArray[np.float64],
    I_o: NDArray[np.float64],
    R_s: NDArray[np.float64],
    R_sh: NDArray[np.float64],
    nNsVth: NDArray[np.float64],
) -> MPPResult:
    """Solve the single-diode equation for the maximum power point using
    the Lambert W function.

    The single-diode I-V equation is:

        I = I_L - I_o * [exp((V + I*R_s) / nNsVth) - 1] - (V + I*R_s) / R_sh

    The Lambert W analytical solution for I(V) is used, and the MPP is
    found by differentiating P = I * V and setting dP/dV = 0, again
    solved via Lambert W.

    Parameters
    ----------
    I_L, I_o, R_s, R_sh, nNsVth : ndarray
        Translated single-diode parameters (see :class:`DiodeParams`).

    Returns
    -------
    MPPResult
        Maximum-power-point current, voltage, and power.
    """
    I_L = np.asarray(I_L, dtype=np.float64)
    I_o = np.asarray(I_o, dtype=np.float64)
    R_s = np.asarray(R_s, dtype=np.float64)
    R_sh = np.asarray(R_sh, dtype=np.float64)
    nNsVth = np.asarray(nNsVth, dtype=np.float64)

    # Mask out invalid / nighttime entries
    valid = (I_L > 0.0) & (I_o > 0.0) & (nNsVth > 0.0)

    I_mp = np.zeros_like(I_L)
    V_mp = np.zeros_like(I_L)
    P_mp = np.zeros_like(I_L)

    if not np.any(valid):
        return MPPResult(I_mp=I_mp, V_mp=V_mp, P_mp=P_mp)

    # Work on valid subset only
    il = I_L[valid]
    io = I_o[valid]
    rs = R_s[valid]
    rsh = R_sh[valid]
    a = nNsVth[valid]

    # --- Open-circuit voltage (V_oc) via Lambert W ---
    # At I=0: 0 = I_L - I_o * [exp(V_oc/a) - 1] - V_oc / R_sh
    # Rearranging for Lambert W:
    #   V_oc = a * W{I_o * R_sh/a * exp[(I_L + I_o)*R_sh/a]}
    #          + (I_L - I_o)*R_sh - I_L*R_s
    arg_oc = io * rsh / a * np.exp((il + io) * rsh / a)
    arg_oc = np.minimum(arg_oc, 1e300)  # clamp to avoid overflow
    w_oc = np.real(lambertw(arg_oc))
    V_oc_v = a * w_oc + (il - io) * rsh - il * rs
    V_oc_v = np.maximum(V_oc_v, 0.0)

    # --- Maximum Power Point via Newton on P(V) ---
    # We use the Lambert W closed-form for I(V) and iterate on dP/dV = 0.
    # This is simple, robust, and fully vectorised.

    # Newton's method to find V_mp
    # Start from V = 0.8 * V_oc
    v = np.copy(V_oc_v) * 0.8

    for _ in range(50):
        # I(V) via Lambert W closed form:
        #   I = [I_L + I_o - V/R_sh] / [1 + R_s/R_sh]
        #       - (a/R_s) * W{ I_o*R_s / [a*(1+R_s/R_sh)]
        #                       * exp[(I_L*R_s + I_o*R_s + V) / (a*(1+R_s/R_sh))] }
        denom = 1.0 + rs / rsh
        z_arg_inner = (il * rs + io * rs + v) / (a * denom)
        z_arg_inner = np.clip(z_arg_inner, -500.0, 500.0)
        z = io * rs / (a * denom) * np.exp(z_arg_inner)
        z = np.minimum(z, 1e300)
        w_val = np.real(lambertw(z))

        i_v = (il + io - v / rsh) / denom - a / rs * w_val

        # Power P = V * I
        p = v * i_v

        # dI/dV: differentiate the Lambert W expression
        # dI/dV = -1/(R_sh * denom) - w_val / (R_s * denom * (1 + w_val))
        w_safe = np.where(np.abs(1.0 + w_val) < 1e-30, 1e-30, 1.0 + w_val)
        di_dv = -1.0 / (rsh * denom) - w_val / (rs * denom * w_safe)

        # dP/dV = I + V * dI/dV
        dp_dv = i_v + v * di_dv

        # d2P/dV2 for Newton step (approximate)
        # d2P/dV2 ~ 2 * dI/dV + V * d2I/dV2 ... we use secant-like:
        dv = -dp_dv / (2.0 * di_dv + 1e-30)

        v_new = v + dv
        # Keep voltage in [0, V_oc]
        v_new = np.clip(v_new, 0.0, V_oc_v)

        converged = np.abs(dv) < 1e-6
        if np.all(converged):
            v = v_new
            break
        v = v_new

    # Final I(V_mp)
    denom = 1.0 + rs / rsh
    z_arg_inner = (il * rs + io * rs + v) / (a * denom)
    z_arg_inner = np.clip(z_arg_inner, -500.0, 500.0)
    z = io * rs / (a * denom) * np.exp(z_arg_inner)
    z = np.minimum(z, 1e300)
    w_val = np.real(lambertw(z))
    i_mp_v = (il + io - v / rsh) / denom - a / rs * w_val

    v_mp_v = np.maximum(v, 0.0)
    i_mp_v = np.maximum(i_mp_v, 0.0)
    p_mp_v = v_mp_v * i_mp_v

    V_mp[valid] = v_mp_v
    I_mp[valid] = i_mp_v
    P_mp[valid] = p_mp_v

    return MPPResult(I_mp=I_mp, V_mp=V_mp, P_mp=P_mp)
