"""Network topology model and Y-bus matrix construction.

Builds the bus admittance matrix (Y-bus) from bus and branch data,
following IEEE 399 conventions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from engine.network.per_unit import cable_z_pu, transformer_z_pu, inverter_z_pu


class BusType(str, Enum):
    SLACK = "slack"
    PV = "pv"
    PQ = "pq"


@dataclass
class BusData:
    """Single bus definition."""
    index: int
    name: str
    bus_type: BusType
    nominal_voltage_kv: float
    base_mva: float = 1.0
    # Specified values (per-unit on system base)
    v_setpoint_pu: float = 1.0
    theta_deg: float = 0.0
    p_gen_pu: float = 0.0
    q_gen_pu: float = 0.0
    p_load_pu: float = 0.0
    q_load_pu: float = 0.0
    # Voltage limits
    v_min_pu: float = 0.95
    v_max_pu: float = 1.05
    # Short-circuit contribution (grid)
    sc_mva: float = 0.0


@dataclass
class BranchData:
    """Single branch (cable, line, or transformer)."""
    index: int
    name: str
    from_bus: int  # bus index
    to_bus: int    # bus index
    branch_type: str  # "cable", "line", "transformer"
    z_pu: complex = 0 + 0j
    # For charging susceptance (cables)
    b_pu: float = 0.0
    # Tap ratio (transformers only, 1.0 for cables)
    tap: complex = 1.0 + 0j
    # Rating
    rating_mva: float = 0.0
    # Original config for reporting
    config: dict = field(default_factory=dict)


@dataclass
class NetworkModel:
    """Complete network model with Y-bus construction."""
    buses: list[BusData] = field(default_factory=list)
    branches: list[BranchData] = field(default_factory=list)
    s_base_mva: float = 1.0

    @property
    def n_bus(self) -> int:
        return len(self.buses)

    @property
    def slack_bus(self) -> int:
        """Index of the slack bus."""
        for bus in self.buses:
            if bus.bus_type == BusType.SLACK:
                return bus.index
        raise ValueError("No slack bus defined in network")

    @property
    def pv_buses(self) -> list[int]:
        return [b.index for b in self.buses if b.bus_type == BusType.PV]

    @property
    def pq_buses(self) -> list[int]:
        return [b.index for b in self.buses if b.bus_type == BusType.PQ]

    def build_y_bus(self) -> np.ndarray:
        """Construct the bus admittance matrix Y-bus.

        For each branch with impedance z and tap ratio t:
        - Y_ii += y/|t|² + jB/2
        - Y_jj += y + jB/2
        - Y_ij -= y/t*
        - Y_ji -= y/t
        """
        n = self.n_bus
        y_bus = np.zeros((n, n), dtype=complex)

        for br in self.branches:
            i = br.from_bus
            j = br.to_bus
            if abs(br.z_pu) < 1e-12:
                continue

            y = 1.0 / br.z_pu
            t = br.tap

            y_bus[i, i] += y / (abs(t) ** 2) + 1j * br.b_pu / 2
            y_bus[j, j] += y + 1j * br.b_pu / 2
            y_bus[i, j] -= y / np.conj(t)
            y_bus[j, i] -= y / t

        return y_bus

    def get_bus_by_index(self, idx: int) -> BusData:
        for bus in self.buses:
            if bus.index == idx:
                return bus
        raise ValueError(f"Bus index {idx} not found")


def build_network_from_config(
    buses_config: list[dict],
    branches_config: list[dict],
    s_base_mva: float = 1.0,
) -> NetworkModel:
    """Build a NetworkModel from configuration dictionaries.

    Args:
        buses_config: list of bus dicts with keys:
            name, bus_type, nominal_voltage_kv, config (optional)
        branches_config: list of branch dicts with keys:
            name, branch_type, from_bus_idx, to_bus_idx, config
        s_base_mva: system base MVA
    """
    buses = []
    for i, bc in enumerate(buses_config):
        cfg = bc.get("config", {})
        buses.append(BusData(
            index=i,
            name=bc["name"],
            bus_type=BusType(bc["bus_type"]),
            nominal_voltage_kv=bc["nominal_voltage_kv"],
            base_mva=s_base_mva,
            v_setpoint_pu=cfg.get("voltage_setpoint_pu", 1.0),
            v_min_pu=cfg.get("min_voltage_pu", 0.95),
            v_max_pu=cfg.get("max_voltage_pu", 1.05),
            sc_mva=cfg.get("sc_mva", 0.0),
        ))

    branches = []
    for i, brc in enumerate(branches_config):
        cfg = brc.get("config", {})
        from_idx = brc["from_bus_idx"]
        to_idx = brc["to_bus_idx"]
        branch_type = brc["branch_type"]

        if branch_type == "transformer":
            z_pu = transformer_z_pu(
                impedance_pct=cfg.get("impedance_pct", 6.0),
                rating_kva=cfg.get("rating_kva", 1000.0),
                s_base_mva=s_base_mva,
                x_r_ratio=cfg.get("x_r_ratio", 10.0),
            )
            tap = complex(cfg.get("tap_ratio", 1.0), 0)
            rating_mva = cfg.get("rating_kva", 1000.0) / 1000.0
            b_pu = 0.0
        elif branch_type == "inverter":
            z_pu = inverter_z_pu(
                efficiency=cfg.get("efficiency", 0.96),
                rating_kw=cfg.get("rated_power_kw", 100.0),
                s_base_mva=s_base_mva,
            )
            tap = 1.0 + 0j
            b_pu = 0.0
            rating_mva = cfg.get("rated_power_kw", 100.0) / 1000.0
        else:
            # Cable or line — use LV side voltage as base
            v_base = buses[to_idx].nominal_voltage_kv
            z_pu = cable_z_pu(
                r_ohm_per_km=cfg.get("r_ohm_per_km", 0.2),
                x_ohm_per_km=cfg.get("x_ohm_per_km", 0.08),
                length_km=cfg.get("length_km", 0.1),
                v_base_kv=v_base,
                s_base_mva=s_base_mva,
            )
            b_pu = cfg.get("b_pu", 0.0)
            tap = 1.0 + 0j
            ampacity = cfg.get("ampacity_a", 0.0)
            rating_mva = (
                np.sqrt(3) * v_base * ampacity / 1000.0
                if ampacity > 0 else 0.0
            )

        branches.append(BranchData(
            index=i,
            name=brc["name"],
            from_bus=from_idx,
            to_bus=to_idx,
            branch_type=branch_type,
            z_pu=z_pu,
            b_pu=b_pu,
            tap=tap,
            rating_mva=rating_mva,
            config=cfg,
        ))

    return NetworkModel(buses=buses, branches=branches, s_base_mva=s_base_mva)
