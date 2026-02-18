"""Tests for engine.network — power flow solver and grid codes."""

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
