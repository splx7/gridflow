"""IEC 60909 simplified three-phase short circuit analysis.

For each faulted bus k:
  1. Build Y_bus with generators replaced by subtransient reactance X"d
  2. Z_bus = inv(Y_bus)
  3. I_sc_k = V_pre / Z_bus[k,k]
  4. S_sc_k = sqrt(3) * V_nom * I_sc_k
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from engine.network.network_model import BusType, NetworkModel
from engine.network.per_unit import i_base


@dataclass
class ShortCircuitResult:
    """Short circuit results for all buses."""
    bus_results: dict[int, BusSCResult]


@dataclass
class BusSCResult:
    """Short circuit result at a single bus."""
    bus_index: int
    bus_name: str
    i_sc_ka: float   # short circuit current in kA
    s_sc_mva: float  # short circuit power in MVA
    z_th_pu: complex  # Thevenin impedance at bus


def calculate_short_circuit(
    network: NetworkModel,
    v_pre_pu: float = 1.0,
) -> ShortCircuitResult:
    """Calculate 3-phase short circuit at all buses using IEC 60909.

    Args:
        network: NetworkModel with buses and branches
        v_pre_pu: pre-fault voltage (typically 1.0 or 1.1 per IEC 60909)
    """
    n = network.n_bus
    if n == 0:
        return ShortCircuitResult(bus_results={})

    y_bus = network.build_y_bus()

    # Add generator/grid source admittance at slack/PV buses
    for bus in network.buses:
        if bus.sc_mva > 0:
            # Grid source: Z_src = V² / S_sc (in per-unit on system base)
            z_src_pu = (v_pre_pu ** 2) * network.s_base_mva / bus.sc_mva
            # Mostly reactive: X/R ≈ 10 for grid
            x_src = z_src_pu * 10.0 / math.sqrt(101.0)
            r_src = x_src / 10.0
            y_src = 1.0 / complex(r_src, x_src)
            y_bus[bus.index, bus.index] += y_src
        elif bus.bus_type == BusType.SLACK:
            # Default grid: assume large short circuit capacity (infinite bus)
            # Use a small impedance: 0.001 + j0.01 pu
            y_src = 1.0 / complex(0.001, 0.01)
            y_bus[bus.index, bus.index] += y_src

    # Z_bus = inv(Y_bus)
    try:
        z_bus = np.linalg.inv(y_bus)
    except np.linalg.LinAlgError:
        # Singular matrix — return zero results
        return ShortCircuitResult(bus_results={
            bus.index: BusSCResult(
                bus_index=bus.index, bus_name=bus.name,
                i_sc_ka=0.0, s_sc_mva=0.0, z_th_pu=0j
            )
            for bus in network.buses
        })

    bus_results = {}
    for bus in network.buses:
        k = bus.index
        z_th = z_bus[k, k]

        if abs(z_th) < 1e-15:
            i_sc_pu = 0.0
        else:
            i_sc_pu = v_pre_pu / abs(z_th)

        # Convert to physical units
        i_base_ka = i_base(bus.nominal_voltage_kv, network.s_base_mva)
        i_sc_ka = i_sc_pu * i_base_ka
        s_sc_mva = math.sqrt(3) * bus.nominal_voltage_kv * i_sc_ka

        bus_results[k] = BusSCResult(
            bus_index=k,
            bus_name=bus.name,
            i_sc_ka=round(i_sc_ka, 3),
            s_sc_mva=round(s_sc_mva, 3),
            z_th_pu=z_th,
        )

    return ShortCircuitResult(bus_results=bus_results)
