"""Tests for NASA POWER weather correction module."""

import numpy as np
import pytest

from engine.weather.nasa_power import (
    MONTH_HOURS,
    _MONTH_OFFSETS,
    apply_monthly_correction,
    inject_cyclone_events,
)


def _make_synthetic_pvgis(ghi_mean: float = 200.0, temp_mean: float = 15.0) -> dict[str, np.ndarray]:
    """Create synthetic 8760-hour PVGIS-like data with known monthly pattern."""
    rng = np.random.default_rng(123)
    ghi = np.full(8760, ghi_mean, dtype=np.float64)
    # Add some diurnal variation
    for h in range(8760):
        hour_of_day = h % 24
        if hour_of_day < 6 or hour_of_day > 18:
            ghi[h] = 0.0
        else:
            ghi[h] = ghi_mean * (1.0 + 0.5 * np.sin(np.pi * (hour_of_day - 6) / 12))

    return {
        "ghi": ghi,
        "dni": ghi * 0.6,
        "dhi": ghi * 0.4,
        "temperature": np.full(8760, temp_mean) + rng.normal(0, 2, 8760),
        "wind_speed": np.full(8760, 4.0) + rng.normal(0, 1, 8760),
    }


def _make_nasa_monthly(ghi_values: list[float], temp_values: list[float]) -> dict:
    """Create NASA POWER-like monthly data."""
    return {
        "ghi": ghi_values,
        "dni": [v * 0.6 for v in ghi_values],
        "dhi": [v * 0.4 for v in ghi_values],
        "temperature": temp_values,
        "temp_max": [t + 5 for t in temp_values],
        "temp_min": [t - 5 for t in temp_values],
        "wind_speed": [4.0] * 12,
    }


class TestMonthOffsets:
    def test_total_hours(self):
        assert sum(MONTH_HOURS) == 8760

    def test_offsets_cover_full_year(self):
        assert _MONTH_OFFSETS[0][0] == 0
        assert _MONTH_OFFSETS[-1][1] == 8760

    def test_offsets_contiguous(self):
        for i in range(11):
            assert _MONTH_OFFSETS[i][1] == _MONTH_OFFSETS[i + 1][0]


class TestApplyMonthlyCorrection:
    def test_basic_scaling(self):
        """Scale factors should adjust PVGIS monthly GHI to match NASA."""
        pvgis = _make_synthetic_pvgis(ghi_mean=200.0, temp_mean=15.0)
        # NASA says GHI should be 50% higher across all months
        pvgis_monthly_avg = []
        for m in range(12):
            start, end = _MONTH_OFFSETS[m]
            pvgis_monthly_avg.append(float(np.mean(pvgis["ghi"][start:end])))

        nasa_ghi = [avg * 1.5 for avg in pvgis_monthly_avg]
        nasa = _make_nasa_monthly(nasa_ghi, [25.0] * 12)

        corrected, metadata = apply_monthly_correction(pvgis, nasa)

        # Check GHI was scaled up
        for m in range(12):
            start, end = _MONTH_OFFSETS[m]
            corrected_avg = float(np.mean(corrected["ghi"][start:end]))
            # Should be close to NASA target (within rounding)
            assert abs(corrected_avg - nasa_ghi[m]) < 1.0, (
                f"Month {m+1}: corrected={corrected_avg:.1f} vs nasa={nasa_ghi[m]:.1f}"
            )

    def test_scale_factor_clamping(self):
        """Scale factors should be clamped to [0.5, 2.0]."""
        pvgis = _make_synthetic_pvgis(ghi_mean=200.0)
        pvgis_monthly_avg = []
        for m in range(12):
            start, end = _MONTH_OFFSETS[m]
            pvgis_monthly_avg.append(float(np.mean(pvgis["ghi"][start:end])))

        # Make NASA GHI 5x higher (should clamp to 2.0)
        nasa_ghi = [avg * 5.0 for avg in pvgis_monthly_avg]
        nasa = _make_nasa_monthly(nasa_ghi, [25.0] * 12)

        _, metadata = apply_monthly_correction(pvgis, nasa)

        for sf in metadata["scale_factors"]:
            assert 0.5 <= sf <= 2.0

    def test_temperature_shift(self):
        """Temperature should be shifted to match NASA monthly mean."""
        pvgis = _make_synthetic_pvgis(temp_mean=15.0)
        nasa_temp = [25.0] * 12  # NASA says 25C
        pvgis_monthly_avg = []
        for m in range(12):
            start, end = _MONTH_OFFSETS[m]
            pvgis_monthly_avg.append(float(np.mean(pvgis["ghi"][start:end])))

        nasa = _make_nasa_monthly(pvgis_monthly_avg, nasa_temp)

        corrected, metadata = apply_monthly_correction(pvgis, nasa)

        # Check temperature was shifted
        for m in range(12):
            start, end = _MONTH_OFFSETS[m]
            corrected_temp_avg = float(np.mean(corrected["temperature"][start:end]))
            assert abs(corrected_temp_avg - 25.0) < 0.5, (
                f"Month {m+1}: corrected_temp={corrected_temp_avg:.1f}"
            )

    def test_no_negative_irradiance(self):
        """Corrected irradiance should never be negative."""
        pvgis = _make_synthetic_pvgis()
        # Extremely low NASA GHI → scale factor = 0.5 (clamped)
        nasa = _make_nasa_monthly([1.0] * 12, [25.0] * 12)

        corrected, _ = apply_monthly_correction(pvgis, nasa)

        assert np.all(corrected["ghi"] >= 0)
        assert np.all(corrected["dni"] >= 0)
        assert np.all(corrected["dhi"] >= 0)

    def test_metadata_structure(self):
        """Metadata should contain expected keys."""
        pvgis = _make_synthetic_pvgis()
        pvgis_monthly_avg = []
        for m in range(12):
            start, end = _MONTH_OFFSETS[m]
            pvgis_monthly_avg.append(float(np.mean(pvgis["ghi"][start:end])))
        nasa = _make_nasa_monthly(pvgis_monthly_avg, [25.0] * 12)

        _, metadata = apply_monthly_correction(pvgis, nasa)

        assert "correction_source" in metadata
        assert "scale_factors" in metadata
        assert "temp_shifts" in metadata
        assert len(metadata["scale_factors"]) == 12
        assert len(metadata["temp_shifts"]) == 12
        assert len(metadata["pvgis_monthly_ghi_avg"]) == 12
        assert len(metadata["corrected_monthly_ghi_avg"]) == 12

    def test_zero_pvgis_ghi_no_crash(self):
        """If PVGIS GHI is zero for a month, scale factor defaults to 1.0."""
        pvgis = _make_synthetic_pvgis()
        # Zero out January
        start, end = _MONTH_OFFSETS[0]
        pvgis["ghi"][start:end] = 0.0
        pvgis["dni"][start:end] = 0.0
        pvgis["dhi"][start:end] = 0.0

        pvgis_monthly_avg = []
        for m in range(12):
            s, e = _MONTH_OFFSETS[m]
            pvgis_monthly_avg.append(float(np.mean(pvgis["ghi"][s:e])))

        nasa = _make_nasa_monthly([100.0] * 12, [25.0] * 12)

        corrected, metadata = apply_monthly_correction(pvgis, nasa)
        # January scale factor should be 1.0 (default when pvgis=0)
        assert metadata["scale_factors"][0] == 1.0
        # No NaN/inf in output
        assert np.all(np.isfinite(corrected["ghi"]))

    def test_identity_correction(self):
        """If NASA matches PVGIS, data should be nearly unchanged."""
        pvgis = _make_synthetic_pvgis()
        pvgis_monthly_avg = []
        pvgis_temp_avg = []
        for m in range(12):
            start, end = _MONTH_OFFSETS[m]
            pvgis_monthly_avg.append(float(np.mean(pvgis["ghi"][start:end])))
            pvgis_temp_avg.append(float(np.mean(pvgis["temperature"][start:end])))

        nasa = _make_nasa_monthly(pvgis_monthly_avg, pvgis_temp_avg)

        corrected, metadata = apply_monthly_correction(pvgis, nasa)

        # Scale factors should all be ~1.0
        for sf in metadata["scale_factors"]:
            assert abs(sf - 1.0) < 0.01

        # GHI should be essentially unchanged
        assert np.allclose(corrected["ghi"], pvgis["ghi"], atol=0.1)


class TestInjectCycloneEvents:
    def test_creates_events(self):
        """Should create the requested number of events."""
        data = _make_synthetic_pvgis()
        modified, events = inject_cyclone_events(data, lat=-18.0, num_events=2)
        assert len(events) == 2

    def test_ghi_drops_during_events(self):
        """GHI should be significantly lower during cyclone events."""
        data = _make_synthetic_pvgis(ghi_mean=200.0)
        original_ghi = data["ghi"].copy()
        modified, events = inject_cyclone_events(data, lat=-18.0, num_events=2)

        for event in events:
            start = event["start_hour"]
            end = event["end_hour"]
            # Only compare daytime hours (where original GHI > 0)
            daytime_mask = original_ghi[start:end] > 0
            if daytime_mask.any():
                ratio = modified["ghi"][start:end][daytime_mask].mean() / original_ghi[start:end][daytime_mask].mean()
                assert ratio < 0.3, f"Event GHI ratio should be <0.3, got {ratio:.2f}"

    def test_wind_spikes_during_events(self):
        """Wind speed should be elevated during cyclone events."""
        data = _make_synthetic_pvgis()
        modified, events = inject_cyclone_events(data, lat=-18.0, num_events=2)

        for event in events:
            start = event["start_hour"]
            end = event["end_hour"]
            avg_wind = float(np.mean(modified["wind_speed"][start:end]))
            assert avg_wind > 10.0, f"Expected high wind, got {avg_wind:.1f} m/s"

    def test_events_in_cyclone_season(self):
        """Events should be placed in Nov-Apr (cyclone season)."""
        data = _make_synthetic_pvgis()
        _, events = inject_cyclone_events(data, lat=-18.0, num_events=4, seed=99)

        for event in events:
            day = event["start_day"]
            # Should be in Jan-Apr (days 0-119) or Nov-Dec (days 304-364)
            in_season = (day < 120) or (day >= 304)
            assert in_season, f"Event at day {day} is outside cyclone season"

    def test_reproducible_with_seed(self):
        """Same seed should produce identical events."""
        data1 = _make_synthetic_pvgis()
        data2 = _make_synthetic_pvgis()

        _, events1 = inject_cyclone_events(data1, lat=-18.0, seed=42)
        _, events2 = inject_cyclone_events(data2, lat=-18.0, seed=42)

        assert events1 == events2

    def test_no_negative_values(self):
        """Output should have no negative irradiance or wind."""
        data = _make_synthetic_pvgis()
        modified, _ = inject_cyclone_events(data, lat=-18.0, num_events=3)

        assert np.all(modified["ghi"] >= 0)
        assert np.all(modified["dni"] >= 0)
        assert np.all(modified["dhi"] >= 0)
        assert np.all(modified["wind_speed"] >= 0)

    def test_event_metadata_structure(self):
        """Event metadata should contain expected fields."""
        data = _make_synthetic_pvgis()
        _, events = inject_cyclone_events(data, lat=-18.0, num_events=1)

        event = events[0]
        assert "event_index" in event
        assert "start_day" in event
        assert "duration_days" in event
        assert "ghi_factor" in event
        assert "wind_speed_ms" in event
        assert 0.1 <= event["ghi_factor"] <= 0.2
        assert 15.0 <= event["wind_speed_ms"] <= 25.0
