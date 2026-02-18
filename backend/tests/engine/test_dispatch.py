"""Tests for engine.dispatch and engine.simulation.runner — dispatch strategies."""

from __future__ import annotations

import numpy as np
import pytest

from engine.load.load_model import generate_load_profile

HOURS_PER_YEAR = 8760


# ======================================================================
# Helper to run a quick simulation
# ======================================================================

def _run_simulation(
    components: dict,
    weather: dict,
    load_kw: np.ndarray,
    strategy: str = "load_following",
) -> dict:
    """Run SimulationRunner and return results dict."""
    from engine.simulation.runner import SimulationRunner

    runner = SimulationRunner(
        components=components,
        weather=weather,
        load_kw=load_kw,
        dispatch_strategy=strategy,
    )
    return runner.run()


# ======================================================================
# Load-following dispatch
# ======================================================================


class TestLoadFollowing:
    """Tests for the load_following dispatch strategy."""

    def test_surplus_charges_battery(self, sample_weather, sample_pv_config, sample_battery_config):
        """When RE > load, surplus should charge the battery."""
        # Small load so PV creates surplus
        load = np.full(HOURS_PER_YEAR, 1.0, dtype=np.float64)
        components = {"solar_pv": sample_pv_config, "battery": sample_battery_config}
        results = _run_simulation(components, sample_weather, load, "load_following")
        total_charge = float(np.sum(results["battery_charge_kw"]))
        assert total_charge > 0, "Battery should charge from PV surplus"

    def test_deficit_discharges_battery(self, sample_weather, sample_battery_config):
        """When load > RE and battery available, battery should discharge."""
        # No PV, only battery and load
        load = np.full(HOURS_PER_YEAR, 5.0, dtype=np.float64)
        components = {"battery": sample_battery_config}
        results = _run_simulation(components, sample_weather, load, "load_following")
        total_discharge = float(np.sum(results["battery_discharge_kw"]))
        assert total_discharge > 0, "Battery should discharge to serve load"

    def test_generator_fallback(self, sample_weather, sample_generator_config):
        """Generator should run when load exceeds RE and no battery."""
        load = np.full(HOURS_PER_YEAR, 20.0, dtype=np.float64)
        components = {"diesel_generator": sample_generator_config}
        results = _run_simulation(components, sample_weather, load, "load_following")
        total_gen = float(np.sum(results["generator_kw"]))
        assert total_gen > 0, "Generator should run to serve load"


# ======================================================================
# Cycle-charging dispatch
# ======================================================================


class TestCycleCharging:
    """Tests for the cycle_charging dispatch strategy."""

    def test_generator_charges_battery(
        self, sample_weather, sample_battery_config, sample_generator_config
    ):
        """In cycle charging, generator surplus should charge battery."""
        load = np.full(HOURS_PER_YEAR, 10.0, dtype=np.float64)
        components = {
            "battery": sample_battery_config,
            "diesel_generator": sample_generator_config,
        }
        results = _run_simulation(components, sample_weather, load, "cycle_charging")
        total_charge = float(np.sum(results["battery_charge_kw"]))
        total_gen = float(np.sum(results["generator_kw"]))
        assert total_gen > 0
        assert total_charge > 0, "Generator should charge battery in cycle-charging mode"


# ======================================================================
# Combined dispatch
# ======================================================================


class TestCombinedDispatch:
    """Tests for the combined dispatch strategy."""

    def test_combined_runs_without_error(
        self, sample_weather, sample_pv_config, sample_battery_config, sample_generator_config
    ):
        """Combined strategy should run to completion."""
        load = generate_load_profile(50_000, "residential", noise_factor=0.0)
        components = {
            "solar_pv": sample_pv_config,
            "battery": sample_battery_config,
            "diesel_generator": sample_generator_config,
        }
        results = _run_simulation(components, sample_weather, load, "combined")
        assert results["annual_load_kwh"] > 0
        assert results["dispatch_strategy"] == "combined"


# ======================================================================
# Energy balance conservation
# ======================================================================


class TestEnergyBalance:
    """Tests for energy conservation across dispatch."""

    def test_energy_balance_load_following(
        self, sample_weather, sample_pv_config, sample_battery_config, sample_generator_config
    ):
        """Annual energy totals must be consistent."""
        load = generate_load_profile(30_000, "residential", noise_factor=0.0)
        components = {
            "solar_pv": sample_pv_config,
            "battery": sample_battery_config,
            "diesel_generator": sample_generator_config,
        }
        results = _run_simulation(components, sample_weather, load, "load_following")

        # Verify: energy_served = annual_load - unmet
        annual_load = results["annual_load_kwh"]
        unmet = results["unmet_load_kwh"]
        energy_served = results["energy_served_kwh"]
        assert abs(energy_served - (annual_load - unmet)) < 1.0

        # Verify: all output arrays have correct shape
        for key in ["load_kw", "pv_output_kw", "battery_charge_kw",
                     "battery_discharge_kw", "generator_kw", "curtailed_kw"]:
            assert results[key].shape == (HOURS_PER_YEAR,), f"{key} has wrong shape"

        # Verify: renewable fraction in [0, 1]
        rf = results["renewable_fraction"]
        assert 0.0 <= rf <= 1.0, f"Renewable fraction {rf} out of range"

        # Verify: no negative time-series values
        for key in ["pv_output_kw", "battery_charge_kw", "battery_discharge_kw",
                     "generator_kw", "grid_import_kw", "grid_export_kw"]:
            assert np.all(results[key] >= -0.01), f"{key} has negative values"


# ======================================================================
# Error handling
# ======================================================================


class TestDispatchErrors:
    """Tests for dispatch error handling."""

    def test_invalid_strategy_raises(self, sample_weather):
        """Unknown dispatch strategy must raise ValueError."""
        from engine.simulation.runner import SimulationRunner

        load = np.full(HOURS_PER_YEAR, 5.0)
        with pytest.raises(ValueError, match="Unknown dispatch strategy"):
            SimulationRunner(
                components={},
                weather=sample_weather,
                load_kw=load,
                dispatch_strategy="nonexistent",
            )

    def test_wrong_load_length_raises(self, sample_weather):
        """Load array not 8760 must raise ValueError."""
        from engine.simulation.runner import SimulationRunner

        with pytest.raises(ValueError, match="8760 elements"):
            SimulationRunner(
                components={},
                weather=sample_weather,
                load_kw=np.full(100, 5.0),
                dispatch_strategy="load_following",
            )


# ======================================================================
# LP optimal dispatch
# ======================================================================


class TestOptimalDispatch:
    """Tests for the LP optimal dispatch solver."""

    def test_lp_feasibility(self):
        """LP should find a feasible solution for basic inputs."""
        from engine.dispatch.optimal import dispatch_optimal

        load = np.full(HOURS_PER_YEAR, 10.0)
        re = np.full(HOURS_PER_YEAR, 5.0)
        battery_cfg = {
            "capacity_kwh": 50,
            "max_charge_kw": 25,
            "max_discharge_kw": 25,
            "efficiency": 0.90,
            "min_soc": 0.10,
            "max_soc": 0.95,
            "initial_soc": 0.50,
        }
        gen_cfg = {
            "rated_power_kw": 30,
            "min_load_ratio": 0.30,
            "fuel_curve_a0": 0.0845,
            "fuel_curve_a1": 0.246,
            "fuel_price": 1.20,
            "om_cost_per_hour": 5.0,
        }
        result = dispatch_optimal(
            load_kw=load,
            re_output_kw=re,
            battery_config=battery_cfg,
            generator_config=gen_cfg,
        )
        assert "battery_charge" in result
        assert "unmet" in result
        # Should have minimal unmet load
        total_unmet = float(np.sum(result["unmet"]))
        # With 5kW RE + 30kW gen vs 10kW load, should be feasible
        assert total_unmet < 1.0, f"Too much unmet load: {total_unmet:.1f} kWh"

    def test_lp_cost_priority(self):
        """LP should prefer cheaper sources (RE free > battery > gen > unmet)."""
        from engine.dispatch.optimal import dispatch_optimal

        load = np.full(HOURS_PER_YEAR, 10.0)
        re = np.full(HOURS_PER_YEAR, 8.0)  # RE covers most load
        battery_cfg = {
            "capacity_kwh": 100,
            "max_charge_kw": 50,
            "max_discharge_kw": 50,
            "efficiency": 0.90,
            "min_soc": 0.10,
            "max_soc": 0.95,
            "initial_soc": 0.50,
        }
        gen_cfg = {
            "rated_power_kw": 30,
            "fuel_curve_a0": 0.0845,
            "fuel_curve_a1": 0.246,
            "fuel_price": 1.20,
            "om_cost_per_hour": 5.0,
        }
        result = dispatch_optimal(
            load_kw=load,
            re_output_kw=re,
            battery_config=battery_cfg,
            generator_config=gen_cfg,
        )
        # Generator usage should be modest since RE covers most
        gen_kwh = float(np.sum(result["generator_output"]))
        total_load = float(np.sum(load))
        # Generator should provide less than half total load (RE covers 80%)
        assert gen_kwh < total_load * 0.5, (
            f"Generator produced {gen_kwh:.0f} kWh — too much given RE={float(np.sum(re)):.0f}"
        )
