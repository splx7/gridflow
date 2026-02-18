"""Shared test fixtures for GridFlow engine and API tests."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

HOURS_PER_YEAR = 8760


# ======================================================================
# Weather fixtures
# ======================================================================

@pytest.fixture
def sample_weather() -> dict[str, NDArray[np.float64]]:
    """Synthetic weather data resembling a tropical location (Nairobi-ish).

    Provides 8760-element arrays for GHI, DNI, DHI, temperature, and wind speed.
    """
    rng = np.random.default_rng(42)
    hours = np.arange(HOURS_PER_YEAR, dtype=np.float64)
    hour_of_day = hours % 24

    # Solar: bell curve during daytime (6-18), zero at night
    solar_mask = (hour_of_day >= 6) & (hour_of_day <= 18)
    solar_shape = np.where(
        solar_mask,
        np.sin(np.pi * (hour_of_day - 6) / 12),
        0.0,
    )

    ghi = solar_shape * 800 + rng.normal(0, 20, HOURS_PER_YEAR)
    ghi = np.clip(ghi, 0, 1200).astype(np.float64)

    dni = ghi * 0.6
    dhi = ghi * 0.4

    # Temperature: 20-30°C diurnal cycle
    temperature = 25.0 + 5.0 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
    temperature += rng.normal(0, 1, HOURS_PER_YEAR)
    temperature = temperature.astype(np.float64)

    wind_speed = (4.0 + rng.exponential(2.0, HOURS_PER_YEAR)).astype(np.float64)

    return {
        "ghi": ghi,
        "dni": dni,
        "dhi": dhi,
        "temperature": temperature,
        "wind_speed": wind_speed,
    }


# ======================================================================
# Load fixtures
# ======================================================================

@pytest.fixture
def sample_load_residential() -> NDArray[np.float64]:
    """Deterministic residential load profile, 10,000 kWh/yr."""
    from engine.load.load_model import generate_load_profile

    return generate_load_profile(
        annual_kwh=10_000.0,
        profile_type="residential",
        noise_factor=0.0,
        seed=42,
    )


@pytest.fixture
def sample_load_commercial() -> NDArray[np.float64]:
    """Deterministic commercial load profile, 50,000 kWh/yr."""
    from engine.load.load_model import generate_load_profile

    return generate_load_profile(
        annual_kwh=50_000.0,
        profile_type="commercial",
        noise_factor=0.0,
        seed=42,
    )


# ======================================================================
# Component config fixtures
# ======================================================================

@pytest.fixture
def sample_pv_config() -> dict:
    """15 kWp PV system config for Nairobi."""
    return {
        "capacity_kwp": 15.0,
        "tilt": 15.0,
        "azimuth": 0.0,  # North-facing for southern hemisphere
        "latitude": -1.29,
        "longitude": 36.82,
        "capital_cost_per_kw": 650.0,
        "om_cost_per_kw_year": 10.0,
        "lifetime_years": 25,
    }


@pytest.fixture
def sample_battery_config() -> dict:
    """100 kWh LFP battery config."""
    return {
        "capacity_kwh": 100.0,
        "max_charge_rate_kw": 50.0,
        "max_discharge_rate_kw": 50.0,
        "round_trip_efficiency": 0.90,
        "min_soc": 0.10,
        "max_soc": 0.95,
        "initial_soc": 0.50,
        "cycle_life": 5000,
        "daily_cycles": 1.0,
        "capital_cost_per_kwh": 350.0,
        "om_cost_annual": 500.0,
        "lifetime_years": 15,
        "chemistry": "lfp",
    }


@pytest.fixture
def sample_generator_config() -> dict:
    """30 kW backup diesel generator config."""
    return {
        "rated_power_kw": 30.0,
        "min_load_ratio": 0.30,
        "fuel_price": 1.20,
        "fuel_curve": {"a0": 0.0845, "a1": 0.246},
        "om_cost_per_hour": 5.0,
        "start_cost": 15.0,
        "capital_cost": 15_000.0,
        "om_cost_annual": 1_000.0,
        "lifetime_years": 20,
    }


@pytest.fixture
def sample_grid_config() -> dict:
    """Grid connection config with flat tariff."""
    return {
        "max_import_kw": 100.0,
        "max_export_kw": 50.0,
        "tariff": {
            "type": "flat",
            "buy_rate": 0.12,
            "sell_rate": 0.04,
        },
        "sell_back_enabled": True,
        "buy_rate": 0.12,
        "tariff_buy_rate": 0.12,
    }


@pytest.fixture
def sample_components(
    sample_pv_config,
    sample_battery_config,
    sample_generator_config,
    sample_grid_config,
) -> dict[str, dict]:
    """Complete component configuration dict for simulation."""
    return {
        "solar_pv": sample_pv_config,
        "battery": sample_battery_config,
        "diesel_generator": sample_generator_config,
        "grid_connection": sample_grid_config,
    }
