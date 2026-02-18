"""Tests for FREF (Fiji Rural Electrification Fund) engine components."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

from engine.load.load_model import generate_load_profile
from engine.economics.fiji_presets import (
    FIJI_PRESETS,
    apply_logistics_premium,
    battery_autonomy_kwh,
    cost_per_household,
    cyclone_derating_factor,
    diesel_displacement_pct,
)

HOURS_PER_YEAR = 8760


# ======================================================================
# Rural village load profile
# ======================================================================


class TestRuralVillageProfile:
    """Tests for the rural_village load profile type."""

    def test_profile_shape(self):
        """Rural village profile must be 8760 elements."""
        profile = generate_load_profile(
            55_000, "rural_village", noise_factor=0.0
        )
        assert profile.shape == (HOURS_PER_YEAR,)

    def test_evening_peak(self):
        """Evening peak (18-20h) must be >= 3x midday (10-14h) average."""
        profile = generate_load_profile(
            55_000, "rural_village", noise_factor=0.0
        )
        daily = profile.reshape(365, 24)
        hourly_avg = daily.mean(axis=0)
        evening_peak = hourly_avg[18:21].max()
        midday_avg = hourly_avg[10:14].mean()
        ratio = evening_peak / midday_avg
        assert ratio >= 3.0, (
            f"Evening/midday ratio {ratio:.2f}, expected >= 3.0"
        )

    def test_low_overnight(self):
        """Overnight (00-05h) should be much lower than peak."""
        profile = generate_load_profile(
            55_000, "rural_village", noise_factor=0.0
        )
        daily = profile.reshape(365, 24)
        hourly_avg = daily.mean(axis=0)
        overnight_max = hourly_avg[0:5].max()
        evening_peak = hourly_avg[18:21].max()
        assert overnight_max < 0.25 * evening_peak

    def test_southern_hemisphere_seasonal(self):
        """Southern hemisphere: Jun-Aug should have higher load than Dec-Feb."""
        profile = generate_load_profile(
            55_000, "rural_village", noise_factor=0.0, hemisphere="southern"
        )
        # Sum load by month
        monthly = []
        day = 0
        days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        for d in days_per_month:
            start = day * 24
            end = (day + d) * 24
            monthly.append(profile[start:end].sum())
            day += d

        winter_avg = np.mean([monthly[5], monthly[6], monthly[7]])  # Jun-Aug
        summer_avg = np.mean([monthly[11], monthly[0], monthly[1]])  # Dec-Feb
        assert winter_avg > summer_avg, (
            f"Winter avg {winter_avg:.0f} should exceed summer avg {summer_avg:.0f}"
        )


# ======================================================================
# Fiji cost presets
# ======================================================================


class TestFijiPresets:
    """Tests for Fiji FREF cost preset constants and functions."""

    def test_logistics_premium(self):
        """30% premium on base cost."""
        result = apply_logistics_premium(1000)
        assert result == 1300.0

    def test_logistics_premium_custom(self):
        """Custom premium percentage."""
        result = apply_logistics_premium(1000, premium_pct=50)
        assert result == 1500.0

    def test_battery_autonomy_3_days(self):
        """3-day autonomy for 150 kWh/day load."""
        daily = 150.0
        kwh = battery_autonomy_kwh(daily, autonomy_days=3, min_soc=0.10, max_soc=0.95)
        # Usable fraction = 0.85, need 450 kWh usable
        expected = 450.0 / 0.85
        assert abs(kwh - expected) < 1.0

    def test_cyclone_derating_default(self):
        """Default 5% derating → factor of 0.95."""
        factor = cyclone_derating_factor()
        assert abs(factor - 0.95) < 1e-10

    def test_cyclone_derating_custom(self):
        """Custom derating percentage."""
        factor = cyclone_derating_factor(10.0)
        assert abs(factor - 0.90) < 1e-10

    def test_diesel_displacement_full(self):
        """100% RE equals 100% displacement."""
        pct = diesel_displacement_pct(100_000, 100_000)
        assert pct == 100.0

    def test_diesel_displacement_partial(self):
        """50% RE penetration."""
        pct = diesel_displacement_pct(50_000, 100_000)
        assert abs(pct - 50.0) < 0.1

    def test_cost_per_household(self):
        """Cost split across households."""
        result = cost_per_household(100_000, 50, currency="USD")
        assert abs(result["usd"] - 2000.0) < 0.01
        assert result["fjd"] > result["usd"]  # FJD rate > 1


# ======================================================================
# FREF project template
# ======================================================================


class TestFREFTemplate:
    """Tests for the FREF village project template JSON."""

    @pytest.fixture
    def template(self):
        path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "engine", "data", "project_templates",
            "fref_village_fiji.json",
        )
        with open(os.path.normpath(path)) as f:
            return json.load(f)

    def test_template_valid_json(self, template):
        """Template loads as valid JSON."""
        assert template["name"].startswith("FREF")
        assert template["id"] == "fref_village_fiji"

    def test_template_has_fref_metadata(self, template):
        """Template includes FREF-specific metadata."""
        assert "fref_metadata" in template
        meta = template["fref_metadata"]
        assert meta["num_households"] == 50
        assert meta["autonomy_days"] == 3
        assert meta["cyclone_zone"] is True

    def test_template_components(self, template):
        """Template has PV, battery, and generator as component array."""
        comps = template["components"]
        assert isinstance(comps, list)
        types = [c["component_type"] for c in comps]
        assert "solar_pv" in types
        assert "battery" in types
        assert "diesel_generator" in types

    def test_template_location(self, template):
        """Template has Fiji coordinates (Southern hemisphere)."""
        proj = template["project"]
        assert proj["latitude"] < 0  # Southern hemisphere
        assert 170 < proj["longitude"] < 180


# ======================================================================
# Cyclone derating in runner
# ======================================================================


class TestCycloneInRunner:
    """Tests for cyclone derating applied in the simulation runner."""

    def test_cyclone_derating_reduces_output(self, sample_weather, sample_pv_config):
        """PV output should be reduced by cyclone derating percentage."""
        from engine.simulation.runner import SimulationRunner

        load = np.full(HOURS_PER_YEAR, 5.0)

        # Run without derating
        components_no_cyc = {"solar_pv": {**sample_pv_config}}
        runner1 = SimulationRunner(
            components=components_no_cyc, weather=sample_weather,
            load_kw=load, dispatch_strategy="load_following",
        )
        r1 = runner1.run()

        # Run with 5% cyclone derating
        pv_with_cyc = {**sample_pv_config, "cyclone_derating_pct": 5}
        components_cyc = {"solar_pv": pv_with_cyc}
        runner2 = SimulationRunner(
            components=components_cyc, weather=sample_weather,
            load_kw=load, dispatch_strategy="load_following",
        )
        r2 = runner2.run()

        pv1 = float(np.sum(r1["pv_output_kw"]))
        pv2 = float(np.sum(r2["pv_output_kw"]))

        # PV2 should be ~95% of PV1
        ratio = pv2 / pv1
        assert 0.94 < ratio < 0.96, (
            f"Derating ratio {ratio:.4f}, expected ~0.95"
        )
        assert r2["cyclone_derating_applied"] is True
        assert r1["cyclone_derating_applied"] is False
