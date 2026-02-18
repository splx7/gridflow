"""Tests for engine.load.load_model — synthetic load-profile generation."""

from __future__ import annotations

import numpy as np
import pytest

from engine.load.load_model import (
    _PROFILES,
    _day_to_month,
    generate_load_profile,
    scale_profile,
)

HOURS_PER_YEAR = 8760


# ======================================================================
# Shape and basic validation
# ======================================================================


class TestGenerateLoadProfile:
    """Tests for generate_load_profile()."""

    def test_output_shape(self):
        """Profile must be 8760 elements."""
        profile = generate_load_profile(10_000, "residential", noise_factor=0.0)
        assert profile.shape == (HOURS_PER_YEAR,)

    def test_annual_energy_matches_target(self):
        """Sum of hourly kW values (1-hr steps) equals target annual kWh."""
        target = 10_000.0
        profile = generate_load_profile(target, "residential", noise_factor=0.0)
        assert abs(profile.sum() - target) < 0.01

    def test_all_values_positive(self):
        """All hourly values must be non-negative."""
        profile = generate_load_profile(10_000, "residential", noise_factor=0.1, seed=1)
        assert np.all(profile >= 0)

    def test_zero_annual_energy(self):
        """Zero annual energy should produce all-zero profile."""
        profile = generate_load_profile(0.0, "residential", noise_factor=0.0)
        assert profile.sum() == 0.0

    def test_negative_annual_energy_raises(self):
        """Negative annual_kwh must raise ValueError."""
        with pytest.raises(ValueError, match="annual_kwh must be >= 0"):
            generate_load_profile(-100, "residential")

    def test_invalid_profile_type_raises(self):
        """Unknown profile type must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown profile_type"):
            generate_load_profile(10_000, "unknown_type")


class TestProfileTypes:
    """Tests for different load profile types."""

    def test_residential_evening_peak(self):
        """Residential profile peaks in the evening (18-20h)."""
        profile = generate_load_profile(10_000, "residential", noise_factor=0.0)
        # Reshape to (365, 24) to get hourly averages
        daily = profile.reshape(365, 24)
        hourly_avg = daily.mean(axis=0)
        peak_hour = np.argmax(hourly_avg)
        assert 17 <= peak_hour <= 20, f"Residential peak at hour {peak_hour}, expected 17-20"

    def test_commercial_daytime_peak(self):
        """Commercial profile peaks during business hours (9-15h)."""
        profile = generate_load_profile(50_000, "commercial", noise_factor=0.0)
        daily = profile.reshape(365, 24)
        hourly_avg = daily.mean(axis=0)
        peak_hour = np.argmax(hourly_avg)
        assert 9 <= peak_hour <= 15, f"Commercial peak at hour {peak_hour}, expected 9-15"

    def test_industrial_flat_profile(self):
        """Industrial profile has small peak-to-trough ratio (< 1.3x)."""
        profile = generate_load_profile(100_000, "industrial", noise_factor=0.0)
        daily = profile.reshape(365, 24)
        hourly_avg = daily.mean(axis=0)
        ratio = hourly_avg.max() / hourly_avg.min()
        assert ratio < 1.30, f"Industrial peak/trough ratio {ratio:.2f}, expected < 1.3"

    def test_all_profile_types_exist(self):
        """All three profile types must be available."""
        for ptype in ["residential", "commercial", "industrial"]:
            profile = generate_load_profile(10_000, ptype, noise_factor=0.0)
            assert profile.shape == (HOURS_PER_YEAR,)


class TestNoiseAndSeed:
    """Tests for noise injection and seed reproducibility."""

    def test_seed_reproducibility(self):
        """Same seed must produce identical profiles."""
        p1 = generate_load_profile(10_000, "residential", noise_factor=0.1, seed=42)
        p2 = generate_load_profile(10_000, "residential", noise_factor=0.1, seed=42)
        np.testing.assert_array_equal(p1, p2)

    def test_different_seeds_differ(self):
        """Different seeds must produce different profiles (with noise)."""
        p1 = generate_load_profile(10_000, "residential", noise_factor=0.1, seed=1)
        p2 = generate_load_profile(10_000, "residential", noise_factor=0.1, seed=2)
        assert not np.allclose(p1, p2)

    def test_zero_noise_deterministic(self):
        """Zero noise_factor produces identical results regardless of seed."""
        p1 = generate_load_profile(10_000, "residential", noise_factor=0.0, seed=1)
        p2 = generate_load_profile(10_000, "residential", noise_factor=0.0, seed=99)
        np.testing.assert_array_equal(p1, p2)


# ======================================================================
# scale_profile
# ======================================================================


class TestScaleProfile:
    """Tests for scale_profile()."""

    def test_scaling_preserves_shape(self):
        """Scaled profile must have same shape."""
        base = np.ones(HOURS_PER_YEAR)
        scaled = scale_profile(base, 20_000)
        assert scaled.shape == (HOURS_PER_YEAR,)

    def test_scaling_matches_target(self):
        """Scaled profile sum must equal target."""
        base = np.random.default_rng(0).random(HOURS_PER_YEAR) + 0.1
        target = 15_000.0
        scaled = scale_profile(base, target)
        assert abs(scaled.sum() - target) < 0.01

    def test_wrong_length_raises(self):
        """Non-8760 array must raise ValueError."""
        with pytest.raises(ValueError, match="8760 elements"):
            scale_profile(np.ones(100), 10_000)

    def test_all_zero_profile_raises(self):
        """All-zero profile cannot be scaled."""
        with pytest.raises(ValueError, match="Cannot scale an all-zero"):
            scale_profile(np.zeros(HOURS_PER_YEAR), 10_000)


# ======================================================================
# _day_to_month boundaries
# ======================================================================


class TestDayToMonth:
    """Tests for the _day_to_month helper."""

    def test_jan_1(self):
        assert _day_to_month(0) == 0  # January

    def test_jan_31(self):
        assert _day_to_month(30) == 0  # Still January

    def test_feb_1(self):
        assert _day_to_month(31) == 1  # February

    def test_dec_31(self):
        assert _day_to_month(364) == 11  # December

    def test_all_days_valid(self):
        """Every day maps to a valid month 0-11."""
        for d in range(365):
            m = _day_to_month(d)
            assert 0 <= m <= 11, f"Day {d} mapped to month {m}"
