"""Tests for wind engine modules: weibull, power_curve, wind_resource."""
import numpy as np
import pytest

from engine.wind.weibull import weibull_params, weibull_aep, simulate_wind_turbine
from engine.wind.power_curve import PowerCurve, generic_power_curve
from engine.wind.wind_resource import height_correction, air_density_correction


class TestWeibullParams:
    def test_typical_wind_data(self):
        rng = np.random.default_rng(42)
        # Rayleigh distribution (k=2) with c=7
        ws = rng.weibull(2, size=8760) * 7
        k, c = weibull_params(ws)
        assert 1.5 < k < 2.5
        assert 5.0 < c < 9.0

    def test_constant_wind(self):
        ws = np.full(100, 8.0)
        k, c = weibull_params(ws)
        assert k == 10.0  # degenerate case
        assert abs(c - 8.0) < 0.5

    def test_too_few_values(self):
        with pytest.raises(ValueError, match="At least 2"):
            weibull_params(np.array([5.0]))

    def test_zeros_filtered(self):
        ws = np.array([0.0, 0.0, 5.0, 6.0, 7.0, 8.0])
        k, c = weibull_params(ws)
        assert k > 0
        assert c > 0


class TestWeibullAEP:
    def test_positive_energy(self):
        pc = generic_power_curve(100.0, cut_in=3.0, rated_speed=12.0, cut_out=25.0)
        aep = weibull_aep(pc, k=2.0, c=7.0)
        assert aep > 0
        # Should be less than running at rated power all year
        assert aep < 100.0 * 8760

    def test_low_wind_low_energy(self):
        pc = generic_power_curve(100.0)
        aep_low = weibull_aep(pc, k=2.0, c=3.0)
        aep_high = weibull_aep(pc, k=2.0, c=8.0)
        assert aep_high > aep_low


class TestPowerCurve:
    def test_generic_curve_shape(self):
        pc = generic_power_curve(100.0, cut_in=3.0, rated_speed=12.0, cut_out=25.0)
        assert pc.rated_power == 100.0
        assert pc.cut_in == pytest.approx(3.0)

    def test_interpolation_below_cutin(self):
        pc = generic_power_curve(100.0)
        power = pc.interpolate(np.array([1.0, 2.0]))
        np.testing.assert_array_equal(power, [0.0, 0.0])

    def test_interpolation_at_rated(self):
        pc = generic_power_curve(100.0, cut_in=3.0, rated_speed=12.0, cut_out=25.0)
        power = pc.interpolate(np.array([12.0, 15.0, 20.0]))
        np.testing.assert_allclose(power, [100.0, 100.0, 100.0], atol=0.5)

    def test_above_cutout(self):
        pc = generic_power_curve(100.0, cut_in=3.0, rated_speed=12.0, cut_out=25.0)
        power = pc.interpolate(np.array([26.0, 30.0]))
        np.testing.assert_array_equal(power, [0.0, 0.0])

    def test_invalid_speeds(self):
        with pytest.raises(ValueError):
            generic_power_curve(100.0, cut_in=15.0, rated_speed=12.0, cut_out=25.0)


class TestHeightCorrection:
    def test_log_law_increases_at_higher_hub(self):
        ws = np.array([5.0, 6.0, 7.0])
        ws_hub = height_correction(ws, measurement_height=10.0, hub_height=80.0)
        assert np.all(ws_hub > ws)

    def test_same_height_no_change(self):
        ws = np.array([5.0, 6.0, 7.0])
        ws_hub = height_correction(ws, measurement_height=10.0, hub_height=10.0)
        np.testing.assert_allclose(ws_hub, ws)

    def test_power_law(self):
        ws = np.array([5.0])
        ws_hub = height_correction(ws, measurement_height=10.0, hub_height=80.0, method="power_law")
        assert ws_hub[0] > 5.0

    def test_invalid_height(self):
        with pytest.raises(ValueError):
            height_correction(np.array([5.0]), measurement_height=-1.0, hub_height=80.0)


class TestAirDensityCorrection:
    def test_standard_conditions_no_change(self):
        ws = np.array([10.0])
        ws_corr = air_density_correction(ws, temperature=15.0, pressure=101325.0)
        np.testing.assert_allclose(ws_corr, ws, atol=0.01)

    def test_hot_reduces_density(self):
        ws = np.array([10.0])
        ws_hot = air_density_correction(ws, temperature=40.0)
        # Hot air is less dense → lower effective wind speed
        assert ws_hot[0] < 10.0

    def test_cold_increases_density(self):
        ws = np.array([10.0])
        ws_cold = air_density_correction(ws, temperature=-20.0)
        assert ws_cold[0] > 10.0


class TestSimulateWindTurbine:
    def test_basic_simulation(self):
        rng = np.random.default_rng(42)
        ws = rng.weibull(2, size=8760) * 7
        temp = np.full(8760, 20.0)
        output = simulate_wind_turbine(
            rated_power_kw=100.0,
            hub_height=80.0,
            rotor_diameter=50.0,
            wind_speed_8760=ws,
            temp_8760=temp,
        )
        assert output.shape == (8760,)
        assert np.all(output >= 0)
        assert float(np.max(output)) <= 100.0 + 1.0  # small tolerance

    def test_quantity_multiplier(self):
        rng = np.random.default_rng(42)
        ws = rng.weibull(2, size=8760) * 7
        temp = np.full(8760, 20.0)
        out_1 = simulate_wind_turbine(100.0, 80.0, 50.0, ws, temp, config={"quantity": 1})
        out_3 = simulate_wind_turbine(100.0, 80.0, 50.0, ws, temp, config={"quantity": 3})
        np.testing.assert_allclose(out_3, out_1 * 3, atol=0.01)

    def test_wrong_length(self):
        with pytest.raises(ValueError, match="8760"):
            simulate_wind_turbine(100.0, 80.0, 50.0, np.zeros(100), np.zeros(100))
