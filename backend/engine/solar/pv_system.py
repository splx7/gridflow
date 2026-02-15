"""
System-level PV simulation module.

Chains the irradiance transposition, cell temperature estimation,
single-diode module model, and inverter model into a complete hourly
(8760-hour) annual simulation for a grid-connected PV system.

All intermediate arrays are 8760-element numpy vectors processed in a
fully vectorised manner (no Python-level hour loops).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .irradiance import (
    perez_transposition_full,
    solar_position,
)
from .single_diode import (
    DiodeParams,
    cell_temperature,
    de_soto_params,
    single_diode_solve,
)
from .inverter import sandia_inverter

HOURS_PER_YEAR: int = 8760


# ---------------------------------------------------------------------------
# System configuration with sensible defaults
# ---------------------------------------------------------------------------

@dataclass
class PVSystemConfig:
    """Configuration parameters for a PV system simulation.

    Default values represent a typical crystalline-silicon rooftop
    system with a string inverter.

    Module parameters (De Soto / CEC single-diode)
    -----------------------------------------------
    All *_ref* values are at Standard Test Conditions (STC):
    irradiance 1000 W/m^2, cell temperature 25 degC.
    """

    # --- Module (De Soto single-diode) ---
    I_L_ref: float = 9.68           # photo-current at STC (A)
    I_o_ref: float = 2.30e-10       # diode saturation current at STC (A)
    R_s: float = 0.37               # series resistance (Ohm)
    R_sh_ref: float = 550.0         # shunt resistance at STC (Ohm)
    a_ref: float = 1.80             # modified ideality voltage (V)
    alpha_sc: float = 0.004         # Isc temp coefficient (A/K)
    E_g: float = 1.121              # band-gap energy (eV), c-Si
    NOCT: float = 45.0              # nominal operating cell temp (degC)
    modules_per_string: int = 12    # modules in series per string
    strings: int = 1                # parallel strings

    # --- Inverter (Sandia model) ---
    Paco: float = 5000.0            # rated AC output (W)
    Pdco: float = 5250.0            # DC power at rated AC (W)
    Vdco: float = 400.0             # reference DC voltage (V)
    Pso: float = 25.0               # self-consumption / tare (W)
    C0: float = -4.0e-5             # Sandia C0 (1/W)
    C1: float = -2.0e-5             # Sandia C1 (1/V)
    C2: float = 1.0e-3              # Sandia C2 (1/V)
    C3: float = -1.0e-3             # Sandia C3 (1/V)

    # --- System losses (dimensionless fractions, 0-1) ---
    soiling_loss: float = 0.02      # soiling / dust
    shading_loss: float = 0.03      # near-field shading
    wiring_loss: float = 0.02       # DC wiring / mismatch
    availability_loss: float = 0.01 # unplanned outages
    lid_loss: float = 0.015         # light-induced degradation (year 1)

    # --- Degradation ---
    annual_degradation: float = 0.005  # fractional per year (0.5 %/yr)
    system_age_years: float = 0.0      # age at simulation start

    # --- Ground albedo ---
    albedo: float = 0.2

    # --- DC/AC ratio (informational, derived at runtime) ---
    dc_ac_ratio: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        if self.Paco > 0:
            self.dc_ac_ratio = self.Pdco / self.Paco


# ---------------------------------------------------------------------------
# Helper: hour-of-year vectors
# ---------------------------------------------------------------------------

def _hour_of_year_vectors() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return ``(day_of_year, hour_of_day)`` arrays each of length 8760.

    ``day_of_year`` ranges from 1 to 365 (non-leap year).
    ``hour_of_day`` ranges from 0.5 to 23.5 (mid-hour convention).
    """
    hours = np.arange(HOURS_PER_YEAR, dtype=np.float64)
    day_of_year = np.floor(hours / 24.0) + 1.0  # 1-indexed
    hour_of_day = (hours % 24) + 0.5             # mid-hour
    return day_of_year, hour_of_day


# ---------------------------------------------------------------------------
# Main simulation entry point
# ---------------------------------------------------------------------------

def simulate_pv(
    capacity_kwp: float,
    tilt: float,
    azimuth: float,
    latitude: float,
    longitude: float,
    ghi_8760: NDArray[np.float64],
    dni_8760: NDArray[np.float64],
    dhi_8760: NDArray[np.float64],
    temp_8760: NDArray[np.float64],
    config: PVSystemConfig | dict[str, Any] | None = None,
) -> NDArray[np.float64]:
    """Run an 8760-hour annual PV system simulation.

    Processing chain
    ~~~~~~~~~~~~~~~~
    1. Solar geometry (zenith, azimuth) via Spencer's equations.
    2. Perez transposition: GHI/DNI/DHI -> plane-of-array irradiance.
    3. Cell temperature (NOCT model).
    4. Single-diode module model (De Soto) -> DC power per module.
    5. Scale to system DC power (modules * strings).
    6. Sandia inverter model -> AC power.
    7. Apply BOS / system losses (soiling, shading, wiring, etc.).
    8. Apply annual degradation derating.

    Parameters
    ----------
    capacity_kwp : float
        Nameplate DC capacity of the system (kWp at STC).  Used to
        automatically scale module count if the default module rating
        doesn't match, by adjusting ``strings`` in the config.
    tilt : float
        Surface tilt angle from horizontal (degrees).
    azimuth : float
        Surface azimuth, clockwise from north (degrees). 180 = south.
    latitude : float
        Site latitude (degrees, positive north).
    longitude : float
        Site longitude (degrees, positive east).
    ghi_8760 : ndarray, shape (8760,)
        Global horizontal irradiance timeseries (W/m^2).
    dni_8760 : ndarray, shape (8760,)
        Direct normal irradiance timeseries (W/m^2).
    dhi_8760 : ndarray, shape (8760,)
        Diffuse horizontal irradiance timeseries (W/m^2).
    temp_8760 : ndarray, shape (8760,)
        Ambient dry-bulb temperature timeseries (degC).
    config : PVSystemConfig or dict or None
        System configuration. If a ``dict``, it is unpacked into
        :class:`PVSystemConfig`. If ``None``, default values are used.

    Returns
    -------
    ac_output_kw : ndarray, shape (8760,)
        Net AC power output of the PV system (kW) for each hour.
        Night-time values are zero (tare losses are included but
        clipped to zero for the grid-facing output).

    Raises
    ------
    ValueError
        If any input irradiance array does not have exactly 8760
        elements.
    """
    # ---- Validate inputs ----
    ghi_8760 = np.asarray(ghi_8760, dtype=np.float64)
    dni_8760 = np.asarray(dni_8760, dtype=np.float64)
    dhi_8760 = np.asarray(dhi_8760, dtype=np.float64)
    temp_8760 = np.asarray(temp_8760, dtype=np.float64)

    for name, arr in [
        ("ghi_8760", ghi_8760),
        ("dni_8760", dni_8760),
        ("dhi_8760", dhi_8760),
        ("temp_8760", temp_8760),
    ]:
        if arr.shape != (HOURS_PER_YEAR,):
            raise ValueError(
                f"{name} must have shape ({HOURS_PER_YEAR},), "
                f"got {arr.shape}"
            )

    # ---- Configuration ----
    if config is None:
        cfg = PVSystemConfig()
    elif isinstance(config, dict):
        cfg = PVSystemConfig(**config)
    else:
        cfg = config

    # ---- Auto-scale module count to match capacity_kwp ----
    # Rough module STC power: I_L_ref * Vmp_approx (use a_ref * modules_per_string / 2)
    # More precisely: use the single-diode model at STC to get P_mp_ref
    # For scaling purposes, use capacity directly.
    stc_params = de_soto_params(
        irradiance_poa=np.array([1000.0]),
        cell_temp=np.array([25.0]),
        I_L_ref=cfg.I_L_ref,
        I_o_ref=cfg.I_o_ref,
        R_s=cfg.R_s,
        R_sh_ref=cfg.R_sh_ref,
        a_ref=cfg.a_ref,
        alpha_sc=cfg.alpha_sc,
        E_g=cfg.E_g,
    )
    stc_mpp = single_diode_solve(
        stc_params.I_L, stc_params.I_o, stc_params.R_s,
        stc_params.R_sh, stc_params.nNsVth,
    )
    module_pmp_stc = float(stc_mpp.P_mp[0])  # watts per module

    if module_pmp_stc > 0:
        total_modules_needed = capacity_kwp * 1000.0 / module_pmp_stc
        modules_per_string = cfg.modules_per_string
        strings_needed = max(1, int(np.round(total_modules_needed / modules_per_string)))
    else:
        modules_per_string = cfg.modules_per_string
        strings_needed = cfg.strings

    # Scale inverter capacity to match DC capacity (maintain DC/AC ratio)
    system_dc_stc_w = strings_needed * modules_per_string * module_pmp_stc
    if cfg.dc_ac_ratio > 0:
        Paco_scaled = system_dc_stc_w / cfg.dc_ac_ratio
    else:
        Paco_scaled = system_dc_stc_w / 1.10  # default 1.1 DC/AC

    Pdco_scaled = Paco_scaled * (cfg.Pdco / cfg.Paco) if cfg.Paco > 0 else Paco_scaled * 1.05
    Pso_scaled = cfg.Pso * (Paco_scaled / cfg.Paco) if cfg.Paco > 0 else cfg.Pso

    # ---- 1. Solar position ----
    day_of_year, hour_of_day = _hour_of_year_vectors()
    solar_zenith, solar_azimuth = solar_position(
        day_of_year, hour_of_day, latitude, longitude,
    )

    # ---- 2. Perez transposition ----
    poa = perez_transposition_full(
        ghi_8760, dni_8760, dhi_8760,
        solar_zenith, solar_azimuth,
        tilt, azimuth,
        day_of_year,
    )

    # Nighttime mask: set POA to zero where sun is below horizon
    nighttime = (solar_zenith >= 90.0) | (poa <= 0.0)
    poa[nighttime] = 0.0

    # ---- 3. Cell temperature ----
    t_cell = cell_temperature(poa, temp_8760, noct=cfg.NOCT)

    # ---- 4. Single-diode model (per module) ----
    # Translate parameters to operating conditions
    diode_params = de_soto_params(
        irradiance_poa=poa,
        cell_temp=t_cell,
        I_L_ref=cfg.I_L_ref,
        I_o_ref=cfg.I_o_ref,
        R_s=cfg.R_s,
        R_sh_ref=cfg.R_sh_ref,
        a_ref=cfg.a_ref,
        alpha_sc=cfg.alpha_sc,
        E_g=cfg.E_g,
    )

    # Zero out diode params where nighttime to avoid numerical issues
    diode_params_IL = np.where(nighttime, 0.0, diode_params.I_L)
    diode_params_Io = np.where(nighttime, 0.0, diode_params.I_o)
    diode_params_Rs = np.where(nighttime, 0.0, diode_params.R_s)
    diode_params_Rsh = np.where(nighttime, 1e10, diode_params.R_sh)
    diode_params_nNsVth = np.where(nighttime, 0.0, diode_params.nNsVth)

    mpp = single_diode_solve(
        diode_params_IL,
        diode_params_Io,
        diode_params_Rs,
        diode_params_Rsh,
        diode_params_nNsVth,
    )

    # ---- 5. Scale to system level ----
    # P_dc_module is per-module. System has modules_per_string in series
    # (voltage adds) and strings_needed in parallel (current adds).
    # The single-diode model already gives per-module P_mp.
    p_dc_system = mpp.P_mp * modules_per_string * strings_needed  # watts
    v_dc_system = mpp.V_mp * modules_per_string                   # volts

    # ---- 6. Inverter model ----
    p_ac = sandia_inverter(
        p_dc=p_dc_system,
        v_dc=v_dc_system,
        Paco=Paco_scaled,
        Pdco=Pdco_scaled,
        Vdco=cfg.Vdco * modules_per_string / cfg.modules_per_string,
        Pso=Pso_scaled,
        C0=cfg.C0,
        C1=cfg.C1,
        C2=cfg.C2,
        C3=cfg.C3,
    )

    # ---- 7. System losses (BOS derate) ----
    bos_derate = (
        (1.0 - cfg.soiling_loss)
        * (1.0 - cfg.shading_loss)
        * (1.0 - cfg.wiring_loss)
        * (1.0 - cfg.availability_loss)
        * (1.0 - cfg.lid_loss)
    )
    p_ac = p_ac * bos_derate

    # ---- 8. Annual degradation ----
    degradation_factor = (1.0 - cfg.annual_degradation) ** cfg.system_age_years
    p_ac = p_ac * degradation_factor

    # ---- Clip night-time tare to zero for grid output ----
    p_ac = np.maximum(p_ac, 0.0)

    # ---- Convert W -> kW ----
    ac_output_kw = p_ac / 1000.0

    return ac_output_kw
