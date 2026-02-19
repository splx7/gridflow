"""Tests for engine.network — power flow solver, grid codes, and topology."""

from __future__ import annotations

import numpy as np
import pytest

from engine.network.network_model import (
    BranchData,
    BusData,
    BusType,
    NetworkModel,
)
from engine.network.power_flow import solve_power_flow, dc_power_flow
from engine.network.grid_codes import (
    FIJI_GRID_CODE,
    IEC_DEFAULT,
    IEEE_1547,
    PROFILES,
    VoltageLimits,
    get_profile,
    list_profiles,
    build_custom_profile,
)
from engine.network.topology_generator import (
    generate_radial_topology,
    DEFAULT_POWER_FACTORS,
)
from engine.network.network_runner import _resolve_bus_indices


# ======================================================================
# Helper: build simple test networks
# ======================================================================


def _two_bus_network(p_load_pu: float = 0.5, r_pu: float = 0.01, x_pu: float = 0.05) -> NetworkModel:
    """Create a minimal 2-bus network: slack + PQ load."""
    buses = [
        BusData(index=0, name="Slack", bus_type=BusType.SLACK, nominal_voltage_kv=0.4,
                v_setpoint_pu=1.0, p_load_pu=0.0),
        BusData(index=1, name="Load", bus_type=BusType.PQ, nominal_voltage_kv=0.4,
                p_load_pu=p_load_pu, q_load_pu=p_load_pu * 0.3),
    ]
    branches = [
        BranchData(index=0, name="Cable1", from_bus=0, to_bus=1, branch_type="cable",
                   z_pu=complex(r_pu, x_pu), rating_mva=0.5),
    ]
    return NetworkModel(buses=buses, branches=branches, s_base_mva=1.0)


def _three_bus_pv_network(pv_gen_pu: float = 0.3) -> NetworkModel:
    """Create a 3-bus network: slack + PQ load + PV generator bus."""
    buses = [
        BusData(index=0, name="Grid", bus_type=BusType.SLACK, nominal_voltage_kv=11.0,
                v_setpoint_pu=1.0),
        BusData(index=1, name="Load", bus_type=BusType.PQ, nominal_voltage_kv=0.4,
                p_load_pu=0.5, q_load_pu=0.15),
        BusData(index=2, name="PV", bus_type=BusType.PQ, nominal_voltage_kv=0.4,
                p_gen_pu=pv_gen_pu, q_gen_pu=0.0),
    ]
    branches = [
        BranchData(index=0, name="Transformer", from_bus=0, to_bus=1, branch_type="transformer",
                   z_pu=complex(0.005, 0.05), tap=1.0+0j, rating_mva=1.0),
        BranchData(index=1, name="Cable_LV", from_bus=1, to_bus=2, branch_type="cable",
                   z_pu=complex(0.02, 0.01), rating_mva=0.3),
    ]
    return NetworkModel(buses=buses, branches=branches, s_base_mva=1.0)


# ======================================================================
# Power flow solver
# ======================================================================


class TestPowerFlow:
    """Tests for the Newton-Raphson AC power flow solver."""

    def test_two_bus_converges(self):
        """Simple 2-bus system should converge."""
        network = _two_bus_network()
        result = solve_power_flow(network)
        assert result.converged
        assert result.max_mismatch < 1e-6

    def test_two_bus_voltage_drop(self):
        """Load bus voltage should be < 1.0 pu (voltage drop across cable)."""
        network = _two_bus_network(p_load_pu=0.5)
        result = solve_power_flow(network)
        v_load = result.voltage_pu[1]
        assert v_load < 1.0, f"Load bus voltage {v_load:.4f} should be < 1.0"
        assert v_load > 0.8, f"Load bus voltage {v_load:.4f} unreasonably low"

    def test_three_bus_with_pv(self):
        """3-bus network with PV should converge."""
        network = _three_bus_pv_network()
        result = solve_power_flow(network)
        assert result.converged

    def test_convergence_fast(self):
        """Should converge in fewer than 10 iterations for small networks."""
        network = _two_bus_network()
        result = solve_power_flow(network)
        assert result.iterations < 10, f"Took {result.iterations} iterations"

    def test_voltage_drop_proportional_to_load(self):
        """Higher load should cause more voltage drop."""
        net_light = _two_bus_network(p_load_pu=0.1)
        net_heavy = _two_bus_network(p_load_pu=0.8)
        r_light = solve_power_flow(net_light)
        r_heavy = solve_power_flow(net_heavy)
        drop_light = 1.0 - r_light.voltage_pu[1]
        drop_heavy = 1.0 - r_heavy.voltage_pu[1]
        assert drop_heavy > drop_light, (
            f"Heavy load drop ({drop_heavy:.4f}) should exceed light load ({drop_light:.4f})"
        )

    def test_branch_flow_conservation(self):
        """Sum of branch losses should be small relative to total flow."""
        network = _two_bus_network(p_load_pu=0.3)
        result = solve_power_flow(network)
        if result.branch_flows:
            bf = result.branch_flows[0]
            # Losses should be non-negative and small
            assert bf.loss_p_pu >= -1e-6, f"Negative P loss: {bf.loss_p_pu}"
            assert bf.loss_p_pu < 0.1, f"Excessive P loss: {bf.loss_p_pu}"

    def test_ybus_symmetry(self):
        """Y-bus matrix should be symmetric for networks without phase shifters."""
        network = _three_bus_pv_network()
        y_bus = network.build_y_bus()
        np.testing.assert_allclose(
            y_bus, y_bus.T, atol=1e-10,
            err_msg="Y-bus matrix is not symmetric",
        )

    def test_overload_detection(self):
        """Heavy load should produce high branch loading percentage."""
        network = _two_bus_network(p_load_pu=0.8)
        network.branches[0].rating_mva = 0.3  # Set low rating to trigger overload
        result = solve_power_flow(network)
        if result.branch_flows:
            bf = result.branch_flows[0]
            assert bf.loading_pct > 50, f"Loading {bf.loading_pct:.1f}% expected > 50%"

    def test_dc_power_flow_fallback(self):
        """DC power flow should provide approximate solution."""
        network = _two_bus_network(p_load_pu=0.3)
        result = dc_power_flow(network)
        assert result.converged
        # DC approximation: V ≈ 1.0, angles should be close to zero
        assert abs(result.voltage_angle_rad[0]) < 0.01


# ======================================================================
# Grid code profiles
# ======================================================================


class TestGridCodes:
    """Tests for grid code compliance profiles."""

    def test_fiji_voltage_limits(self):
        """Fiji grid code has specific voltage limits."""
        assert FIJI_GRID_CODE.voltage.normal_min == 0.94
        assert FIJI_GRID_CODE.voltage.normal_max == 1.06

    def test_iec_voltage_limits(self):
        """IEC default has ±5% normal voltage band."""
        assert IEC_DEFAULT.voltage.normal_min == 0.95
        assert IEC_DEFAULT.voltage.normal_max == 1.05

    def test_ieee_1547_frequency(self):
        """IEEE 1547 is a 60 Hz standard."""
        assert IEEE_1547.frequency.nominal_hz == 60.0

    def test_voltage_check_normal_pass(self):
        """Voltage within normal limits should return None."""
        vl = VoltageLimits(normal_min=0.95, normal_max=1.05)
        assert vl.check_normal(1.00) is None
        assert vl.check_normal(0.95) is None
        assert vl.check_normal(1.05) is None

    def test_voltage_check_normal_fail(self):
        """Voltage outside normal limits should return violation type."""
        vl = VoltageLimits(normal_min=0.95, normal_max=1.05)
        assert vl.check_normal(0.90) == "low"
        assert vl.check_normal(1.10) == "high"

    def test_get_profile(self):
        """get_profile returns correct profile."""
        fiji = get_profile("fiji")
        assert fiji.name == "Fiji Grid Code"

    def test_get_profile_invalid(self):
        """Unknown profile name raises KeyError."""
        with pytest.raises(KeyError, match="Unknown grid code profile"):
            get_profile("nonexistent")

    def test_list_profiles(self):
        """list_profiles returns all registered profiles."""
        profiles = list_profiles()
        keys = {p["key"] for p in profiles}
        assert "iec_default" in keys
        assert "fiji" in keys
        assert "ieee_1547" in keys

    def test_build_custom_profile(self):
        """Custom profile uses provided values."""
        custom = build_custom_profile({
            "name": "Test Custom",
            "voltage_limits": {"normal": [0.93, 1.07]},
            "thermal_limit_pct": 85.0,
        })
        assert custom.name == "Test Custom"
        assert custom.voltage.normal_min == 0.93
        assert custom.voltage.normal_max == 1.07
        assert custom.thermal_limit_pct == 85.0

    def test_fiji_thermal_conservative(self):
        """Fiji grid code is more conservative on thermal loading (90%)."""
        assert FIJI_GRID_CODE.thermal_limit_pct == 90.0
        assert IEC_DEFAULT.thermal_limit_pct == 100.0

    def test_profile_to_dict(self):
        """to_dict should produce JSON-serializable output."""
        d = FIJI_GRID_CODE.to_dict()
        assert d["name"] == "Fiji Grid Code"
        assert "voltage_limits" in d
        assert "frequency_limits" in d


# ======================================================================
# Topology generator — load buses
# ======================================================================

def _base_components():
    """Minimal component set for topology tests."""
    return [
        {
            "id": "pv-1",
            "component_type": "solar_pv",
            "name": "PV Array 1",
            "config": {"capacity_kw": 10},
        },
    ]


class TestTopologyLoadBuses:
    """Tests for per-profile load bus generation in topology_generator."""

    def test_topology_multiple_loads(self):
        """Two load profiles produce two load buses with correct fractions."""
        profiles = [
            {"id": "lp-1", "name": "Village", "profile_type": "rural_village", "annual_kwh": 6000},
            {"id": "lp-2", "name": "Water Pump", "profile_type": "water_pump", "annual_kwh": 4000},
        ]
        topo = generate_radial_topology(_base_components(), profiles)

        # Should have load buses (name starts with "Load:")
        load_buses = [b for b in topo["buses"] if b["name"].startswith("Load:")]
        assert len(load_buses) == 2

        # Load allocations should reference load bus indices (not main AC bus)
        allocs = topo["load_allocations"]
        assert len(allocs) == 2

        # Fractions should sum to 1.0
        total_fraction = sum(a["fraction"] for a in allocs)
        assert abs(total_fraction - 1.0) < 0.01

        # Fractions proportional to annual_kwh
        village_alloc = next(a for a in allocs if a["load_profile_id"] == "lp-1")
        pump_alloc = next(a for a in allocs if a["load_profile_id"] == "lp-2")
        assert abs(village_alloc["fraction"] - 0.6) < 0.01  # 6000/10000
        assert abs(pump_alloc["fraction"] - 0.4) < 0.01    # 4000/10000

        # Power factors differ by type
        assert village_alloc["power_factor"] == 0.88  # rural_village
        assert pump_alloc["power_factor"] == 0.75     # water_pump

    def test_topology_single_load(self):
        """Single load profile still gets a dedicated load bus."""
        profiles = [
            {"id": "lp-1", "name": "Residential", "profile_type": "residential", "annual_kwh": 8000},
        ]
        topo = generate_radial_topology(_base_components(), profiles)

        load_buses = [b for b in topo["buses"] if b["name"].startswith("Load:")]
        assert len(load_buses) == 1

        allocs = topo["load_allocations"]
        assert len(allocs) == 1
        assert allocs[0]["fraction"] == 1.0
        assert allocs[0]["power_factor"] == 0.90  # residential

        # Load bus should have is_load_bus config
        assert load_buses[0]["config"].get("is_load_bus") is True

    def test_topology_no_loads(self):
        """No load profiles → no load buses or allocations."""
        topo = generate_radial_topology(_base_components(), [])

        load_buses = [b for b in topo["buses"] if b["name"].startswith("Load:")]
        assert len(load_buses) == 0
        assert len(topo["load_allocations"]) == 0

    def test_load_power_factor_lookup(self):
        """Verify power factor lookup for each known load type."""
        assert DEFAULT_POWER_FACTORS["residential"] == 0.90
        assert DEFAULT_POWER_FACTORS["commercial"] == 0.85
        assert DEFAULT_POWER_FACTORS["industrial"] == 0.80
        assert DEFAULT_POWER_FACTORS["rural_village"] == 0.88
        assert DEFAULT_POWER_FACTORS["water_pump"] == 0.75
        assert DEFAULT_POWER_FACTORS["motor"] == 0.80

    def test_load_bus_has_cable_branch(self):
        """Each load bus should have a cable branch from main AC bus."""
        profiles = [
            {"id": "lp-1", "name": "Village", "profile_type": "rural_village", "annual_kwh": 5000},
        ]
        topo = generate_radial_topology(_base_components(), profiles)

        load_bus_idx = next(
            i for i, b in enumerate(topo["buses"]) if b["name"].startswith("Load:")
        )
        # Find cable branch to load bus
        feeder = [
            br for br in topo["branches"]
            if br["to_bus_idx"] == load_bus_idx and br["branch_type"] == "cable"
        ]
        assert len(feeder) == 1
        assert "Feeder" in feeder[0]["name"]


# ======================================================================
# Multi-component bus map resolution
# ======================================================================

class TestMultiComponentBusMap:
    """Tests for _resolve_bus_indices and multi-component generation."""

    def test_resolve_list(self):
        """List value returns as-is."""
        bus_map = {"solar_pv": [1, 3]}
        assert _resolve_bus_indices(bus_map, "solar_pv") == [1, 3]

    def test_resolve_int_legacy(self):
        """Single int value wraps in list (backward compat)."""
        bus_map = {"solar_pv": 2}
        assert _resolve_bus_indices(bus_map, "solar_pv") == [2]

    def test_resolve_missing(self):
        """Missing key returns empty list."""
        bus_map = {"solar_pv": [1]}
        assert _resolve_bus_indices(bus_map, "wind_turbine") == []

    def test_two_pv_arrays_get_separate_buses(self):
        """Two PV arrays should get separate DC buses in topology."""
        comps = [
            {"id": "pv-1", "component_type": "solar_pv", "name": "PV Array 1",
             "config": {"capacity_kw": 10}},
            {"id": "pv-2", "component_type": "solar_pv", "name": "PV Array 2",
             "config": {"capacity_kw": 15}},
        ]
        profiles = [{"id": "lp-1", "name": "Load", "profile_type": "commercial", "annual_kwh": 5000}]
        topo = generate_radial_topology(comps, profiles)

        # Each PV should be assigned to its own DC bus
        pv_assignments = [a for a in topo["component_assignments"] if a["component_id"] in ("pv-1", "pv-2")]
        assert len(pv_assignments) == 2
        bus_indices = [a["bus_idx"] for a in pv_assignments]
        assert bus_indices[0] != bus_indices[1], "Two PV arrays must have different bus indices"
