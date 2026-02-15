"""
Solar PV engine module.

Provides irradiance transposition (Perez 1990), single-diode cell modelling
(De Soto 2006), Sandia inverter modelling, and system-level 8760-hour
simulation for grid-connected photovoltaic systems.
"""

from .irradiance import (
    aoi,
    perez_transposition,
    perez_transposition_full,
    solar_position,
)
from .inverter import sandia_inverter, sandia_inverter_simple
from .single_diode import (
    DiodeParams,
    MPPResult,
    cell_temperature,
    de_soto_params,
    single_diode_solve,
)
from .pv_system import PVSystemConfig, simulate_pv

__all__ = [
    # irradiance
    "solar_position",
    "aoi",
    "perez_transposition",
    "perez_transposition_full",
    # single_diode
    "DiodeParams",
    "MPPResult",
    "cell_temperature",
    "de_soto_params",
    "single_diode_solve",
    # inverter
    "sandia_inverter",
    "sandia_inverter_simple",
    # pv_system
    "PVSystemConfig",
    "simulate_pv",
]
