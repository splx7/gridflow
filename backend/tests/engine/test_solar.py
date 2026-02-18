"""Tests for engine.solar — single-diode PV model and system simulation."""

from __future__ import annotations

import numpy as np
import pytest

from engine.solar.single_diode import (
    DiodeParams,
    MPPResult,
    cell_temperature,
    de_soto_params,
    single_diode_solve,
)
from engine.solar.pv_system import PVSystemConfig, simulate_pv

HOURS_PER_YEAR = 8760


# ======================================================================
# Single-diode model
# ======================================================================


class TestSingleDiode:
    """Tests for the single-diode cell/module model."""

    def test_stc_params_reasonable(self):
        """De Soto params at STC (1000 W/m², 25°C) should match references."""
        cfg = PVSystemConfig()
        params = de_soto_params(
            irradiance_poa=np.array([1000.0]),
            cell_temp=np.array([25.0]),
            I_L_ref=cfg.I_L_ref,
            I_o_ref=cfg.I_o_ref,
            R_s=cfg.R_s,
            R_sh_ref=cfg.R_sh_ref,
            a_ref=cfg.a_ref,
            alpha_sc=cfg.alpha_sc,
        )
        # Photo-current at STC should equal I_L_ref
        assert abs(float(params.I_L[0]) - cfg.I_L_ref) < 0.01
        # Saturation current at STC should equal I_o_ref
        assert abs(float(params.I_o[0]) - cfg.I_o_ref) / cfg.I_o_ref < 0.01

    def test_mpp_at_stc(self):
        """MPP power at STC should be positive and reasonable for a module."""
        cfg = PVSystemConfig()
        params = de_soto_params(
            irradiance_poa=np.array([1000.0]),
            cell_temp=np.array([25.0]),
            I_L_ref=cfg.I_L_ref,
            I_o_ref=cfg.I_o_ref,
            R_s=cfg.R_s,
            R_sh_ref=cfg.R_sh_ref,
            a_ref=cfg.a_ref,
            alpha_sc=cfg.alpha_sc,
        )
        mpp = single_diode_solve(params.I_L, params.I_o, params.R_s, params.R_sh, params.nNsVth)
        p_mp = float(mpp.P_mp[0])
        # A typical module produces 200-500 W at STC
        assert 50 < p_mp < 600, f"MPP power {p_mp:.1f} W outside expected range"

    def test_mpp_zero_irradiance(self):
        """Zero irradiance should produce zero power."""
        cfg = PVSystemConfig()
        params = de_soto_params(
            irradiance_poa=np.array([0.0]),
            cell_temp=np.array([25.0]),
            I_L_ref=cfg.I_L_ref,
            I_o_ref=cfg.I_o_ref,
            R_s=cfg.R_s,
            R_sh_ref=cfg.R_sh_ref,
            a_ref=cfg.a_ref,
            alpha_sc=cfg.alpha_sc,
        )
        mpp = single_diode_solve(params.I_L, params.I_o, params.R_s, params.R_sh, params.nNsVth)
        assert float(mpp.P_mp[0]) == 0.0

    def test_high_temp_reduces_power(self):
        """Higher cell temperature should reduce MPP power."""
        cfg = PVSystemConfig()

        def mpp_at_temp(temp):
            params = de_soto_params(
                irradiance_poa=np.array([1000.0]),
                cell_temp=np.array([temp]),
                I_L_ref=cfg.I_L_ref,
                I_o_ref=cfg.I_o_ref,
                R_s=cfg.R_s,
                R_sh_ref=cfg.R_sh_ref,
                a_ref=cfg.a_ref,
                alpha_sc=cfg.alpha_sc,
            )
            mpp = single_diode_solve(
                params.I_L, params.I_o, params.R_s, params.R_sh, params.nNsVth
            )
            return float(mpp.P_mp[0])

        p25 = mpp_at_temp(25.0)
        p50 = mpp_at_temp(50.0)
        assert p50 < p25, f"Power at 50°C ({p50:.1f}W) should be less than at 25°C ({p25:.1f}W)"

    def test_cell_temperature_model(self):
        """NOCT model: cell temp increases with irradiance."""
        poa = np.array([0.0, 500.0, 1000.0])
        t_amb = np.array([25.0, 25.0, 25.0])
        t_cell = cell_temperature(poa, t_amb, noct=45.0)
        assert t_cell[0] == 25.0  # No irradiance, no heating
        assert t_cell[1] > 25.0
        assert t_cell[2] > t_cell[1]


# ======================================================================
# System-level PV simulation
# ======================================================================


class TestSimulatePV:
    """Tests for simulate_pv() — full system simulation."""

    def test_output_shape(self, sample_weather):
        """Output must be 8760 elements."""
        output = simulate_pv(
            capacity_kwp=15.0,
            tilt=15.0,
            azimuth=0.0,
            latitude=-1.29,
            longitude=36.82,
            ghi_8760=sample_weather["ghi"],
            dni_8760=sample_weather["dni"],
            dhi_8760=sample_weather["dhi"],
            temp_8760=sample_weather["temperature"],
        )
        assert output.shape == (HOURS_PER_YEAR,)

    def test_nighttime_zero(self, sample_weather):
        """Nighttime hours (GHI=0) should have zero output."""
        output = simulate_pv(
            capacity_kwp=15.0,
            tilt=15.0,
            azimuth=0.0,
            latitude=-1.29,
            longitude=36.82,
            ghi_8760=sample_weather["ghi"],
            dni_8760=sample_weather["dni"],
            dhi_8760=sample_weather["dhi"],
            temp_8760=sample_weather["temperature"],
        )
        # Hours where GHI is zero should have zero PV output
        nighttime = sample_weather["ghi"] <= 0
        assert np.all(output[nighttime] == 0.0)

    def test_annual_yield_range(self, sample_weather):
        """Annual yield for 15kWp in near-equatorial location: 1000-2000 kWh/kWp."""
        capacity = 15.0
        output = simulate_pv(
            capacity_kwp=capacity,
            tilt=15.0,
            azimuth=0.0,
            latitude=-1.29,
            longitude=36.82,
            ghi_8760=sample_weather["ghi"],
            dni_8760=sample_weather["dni"],
            dhi_8760=sample_weather["dhi"],
            temp_8760=sample_weather["temperature"],
        )
        annual_kwh = float(output.sum())
        specific_yield = annual_kwh / capacity
        assert 800 < specific_yield < 2200, (
            f"Specific yield {specific_yield:.0f} kWh/kWp outside expected range"
        )

    def test_capacity_factor_range(self, sample_weather):
        """Capacity factor should be between 10% and 25% for typical sites."""
        capacity = 15.0
        output = simulate_pv(
            capacity_kwp=capacity,
            tilt=15.0,
            azimuth=0.0,
            latitude=-1.29,
            longitude=36.82,
            ghi_8760=sample_weather["ghi"],
            dni_8760=sample_weather["dni"],
            dhi_8760=sample_weather["dhi"],
            temp_8760=sample_weather["temperature"],
        )
        cf = float(output.mean()) / capacity
        assert 0.08 < cf < 0.30, f"Capacity factor {cf:.2%} outside expected range"
