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

def _iv_at_v(
    v: NDArray[np.float64],
    il: NDArray[np.float64],
    io: NDArray[np.float64],
    rs: NDArray[np.float64],
    rsh: NDArray[np.float64],
    a: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Evaluate current I at voltage V using Newton iteration on the implicit
    single-diode equation.  More numerically stable than the Lambert W
    closed-form for typical module parameters."""
    # Initial guess: I ≈ I_L - V/R_sh
    i = np.copy(il) - v / rsh

    for _ in range(30):
        vd = v + i * rs  # diode voltage
        exp_vd = np.exp(np.clip(vd / a, -500.0, 500.0))
        f = il - io * (exp_vd - 1.0) - vd / rsh - i
        df = -io * rs / a * exp_vd - rs / rsh - 1.0
        di = -f / df
        i = i + di
        if np.all(np.abs(di) < 1e-10):
            break

    return np.maximum(i, 0.0)


def single_diode_solve(
    I_L: NDArray[np.float64],
    I_o: NDArray[np.float64],
    R_s: NDArray[np.float64],
    R_sh: NDArray[np.float64],
    nNsVth: NDArray[np.float64],
) -> MPPResult:
    """Solve the single-diode equation for the maximum power point.

    Uses a numerically stable Newton iteration on the implicit I-V
    equation rather than the Lambert W closed form (which overflows
    for typical module-level parameter ranges).

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

    il = I_L[valid]
    io = I_o[valid]
    rs = R_s[valid]
    rsh = R_sh[valid]
    a = nNsVth[valid]

    # --- V_oc via Newton (numerically stable) ---
    # At I=0: f(V) = I_L - I_o*(exp(V/a)-1) - V/R_sh = 0
    v_oc = a * np.log(np.maximum(il / io, 1.0))  # initial guess
    for _ in range(30):
        exp_v = np.exp(np.clip(v_oc / a, -500.0, 500.0))
        f = il - io * (exp_v - 1.0) - v_oc / rsh
        df = -io / a * exp_v - 1.0 / rsh
        dv = -f / df
        v_oc = v_oc + dv
        if np.all(np.abs(dv) < 1e-8):
            break
    v_oc = np.maximum(v_oc, 0.0)

    # --- MPP via vectorised bisection on dP/dV = 0 ---
    # P(V) is unimodal on [0, V_oc], so we can use ternary search
    v_lo = np.zeros_like(v_oc)
    v_hi = np.copy(v_oc)

    for _ in range(60):
        v1 = v_lo + (v_hi - v_lo) / 3.0
        v2 = v_hi - (v_hi - v_lo) / 3.0
        p1 = v1 * _iv_at_v(v1, il, io, rs, rsh, a)
        p2 = v2 * _iv_at_v(v2, il, io, rs, rsh, a)
        mask = p1 < p2
        v_lo = np.where(mask, v1, v_lo)
        v_hi = np.where(~mask, v2, v_hi)
        if np.all((v_hi - v_lo) < 1e-6):
            break

    v = (v_lo + v_hi) / 2.0
    i_mp_v = _iv_at_v(v, il, io, rs, rsh, a)

    v_mp_v = np.maximum(v, 0.0)
    i_mp_v = np.maximum(i_mp_v, 0.0)
    p_mp_v = v_mp_v * i_mp_v

    V_mp[valid] = v_mp_v
    I_mp[valid] = i_mp_v
    P_mp[valid] = p_mp_v

    return MPPResult(I_mp=I_mp, V_mp=V_mp, P_mp=P_mp)
