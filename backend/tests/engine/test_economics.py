"""Tests for engine.economics.metrics — NPC, LCOE, IRR, payback."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.economics.metrics import (
    BATTERY_EOL_THRESHOLD,
    _annuity_factor,
    _battery_replacement_cost,
    _battery_replacement_years,
    _capital_costs,
    _discount_factor,
    _om_annual,
    _annual_fuel_cost,
    compute_economics,
)


# ======================================================================
# Discount factor
# ======================================================================


class TestDiscountFactor:
    """Tests for _discount_factor()."""

    def test_year_zero(self):
        """DF at year 0 is always 1.0."""
        assert _discount_factor(0.08, 0) == 1.0

    def test_known_value(self):
        """8% rate, year 5: 1/(1.08)^5."""
        expected = 1.0 / (1.08**5)
        assert abs(_discount_factor(0.08, 5) - expected) < 1e-10

    def test_zero_rate(self):
        """Zero discount rate: DF is always 1.0."""
        assert _discount_factor(0.0, 10) == 1.0


# ======================================================================
# Annuity factor
# ======================================================================


class TestAnnuityFactor:
    """Tests for _annuity_factor()."""

    def test_zero_rate(self):
        """Zero discount rate: annuity factor equals number of years."""
        assert _annuity_factor(0.0, 25) == 25.0

    def test_known_value(self):
        """8% rate, 25 years: known PV annuity factor."""
        af = _annuity_factor(0.08, 25)
        # PV annuity = (1 - (1+r)^-N) / r
        expected = (1 - (1.08) ** (-25)) / 0.08
        assert abs(af - expected) < 1e-6

    def test_one_year(self):
        """Single year: annuity factor = 1/(1+r)."""
        af = _annuity_factor(0.10, 1)
        assert abs(af - 1.0 / 1.10) < 1e-10


# ======================================================================
# Capital costs
# ======================================================================


class TestCapitalCosts:
    """Tests for _capital_costs()."""

    def test_flat_capital_cost(self):
        """Direct capital_cost key is used."""
        components = {"diesel_generator": {"capital_cost": 15_000}}
        costs = _capital_costs(components)
        assert costs["diesel_generator"] == 15_000

    def test_per_kw_capital(self):
        """capital_cost_per_kw × capacity_kw."""
        components = {"solar_pv": {"capital_cost_per_kw": 650, "capacity_kw": 15}}
        costs = _capital_costs(components)
        assert costs["solar_pv"] == 650 * 15

    def test_per_kwh_capital(self):
        """capital_cost_per_kwh × capacity_kwh."""
        components = {"battery": {"capital_cost_per_kwh": 350, "capacity_kwh": 100}}
        costs = _capital_costs(components)
        assert costs["battery"] == 350 * 100

    def test_no_cost_key(self):
        """Missing cost keys default to 0."""
        components = {"solar_pv": {"capacity_kw": 15}}
        costs = _capital_costs(components)
        assert costs["solar_pv"] == 0.0


# ======================================================================
# O&M costs
# ======================================================================


class TestOMCosts:
    """Tests for _om_annual()."""

    def test_flat_om(self):
        """Direct om_cost_annual key."""
        components = {"battery": {"om_cost_annual": 500}}
        costs = _om_annual(components)
        assert costs["battery"] == 500

    def test_per_kw_om(self):
        """om_cost_per_kw_year × capacity_kw."""
        components = {"solar_pv": {"om_cost_per_kw_year": 10, "capacity_kw": 15}}
        costs = _om_annual(components)
        assert costs["solar_pv"] == 150


# ======================================================================
# Fuel costs
# ======================================================================


class TestFuelCosts:
    """Tests for _annual_fuel_cost()."""

    def test_no_generator(self):
        """No diesel_generator: fuel cost is 0."""
        cost, litres = _annual_fuel_cost({}, {}, 0.0)
        assert cost == 0.0
        assert litres == 0.0

    def test_with_fuel_array(self):
        """Fuel array is summed and multiplied by price."""
        fuel_arr = np.full(8760, 2.0)  # 2 L/hr
        results = {"generator_fuel_l": fuel_arr}
        components = {"diesel_generator": {"fuel_price": 1.50}}
        cost, litres = _annual_fuel_cost(results, components, 0.0)
        assert abs(litres - 2.0 * 8760) < 1
        assert abs(cost - litres * 1.50) < 1


# ======================================================================
# Battery replacement
# ======================================================================


class TestBatteryReplacement:
    """Tests for battery replacement timing and cost."""

    def test_replacement_timing(self):
        """5000 cycle life, 1 cycle/day → ~13.7 years → replacement at year 14."""
        components = {
            "battery": {
                "cycle_life": 5000,
                "capacity_kwh": 100,
                "daily_cycles": 1.0,
            }
        }
        years = _battery_replacement_years(components, 25)
        assert len(years) > 0
        # First replacement around year 14
        assert 13 <= years[0] <= 15

    def test_no_battery(self):
        """No battery config: empty replacement list."""
        years = _battery_replacement_years({}, 25)
        assert years == []

    def test_replacement_cost_from_capital(self):
        """Falls back to capital cost when no explicit replacement_cost."""
        components = {"battery": {"capital_cost_per_kwh": 350, "capacity_kwh": 100}}
        cost = _battery_replacement_cost(components)
        assert cost == 35_000


# ======================================================================
# Full economics computation
# ======================================================================


class TestComputeEconomics:
    """Tests for compute_economics()."""

    def test_npc_positive(self):
        """NPC must be positive for any real system."""
        results = {"load_kw": np.full(8760, 10.0)}
        components = {
            "solar_pv": {"capital_cost": 50_000, "om_cost_annual": 500},
        }
        econ = compute_economics(results, components, lifetime_years=25, discount_rate=0.08)
        assert econ["npc"] > 0

    def test_lcoe_reasonable(self):
        """LCOE should be within a plausible range ($0.01–$1.00/kWh)."""
        load = np.full(8760, 10.0)  # 10 kW constant = 87,600 kWh/yr
        results = {"load_kw": load}
        components = {
            "solar_pv": {"capital_cost": 50_000, "om_cost_annual": 500},
        }
        econ = compute_economics(results, components, lifetime_years=25, discount_rate=0.08)
        assert 0.01 < econ["lcoe"] < 1.00

    def test_zero_load_lcoe_zero(self):
        """Zero load → LCOE is 0 (no energy served)."""
        results = {"load_kw": np.zeros(8760)}
        components = {"solar_pv": {"capital_cost": 10_000}}
        econ = compute_economics(results, components)
        assert econ["lcoe"] == 0.0

    def test_irr_with_grid_savings(self):
        """System with grid savings should have a positive IRR."""
        load = np.full(8760, 10.0)
        results = {"load_kw": load}
        components = {
            "solar_pv": {"capital_cost": 50_000, "om_cost_annual": 500},
            "grid_connection": {"buy_rate": 0.20},
        }
        econ = compute_economics(results, components, lifetime_years=25, discount_rate=0.08)
        # With a buy rate of $0.20/kWh and 87600 kWh/yr, savings vs capital should yield positive IRR
        if econ["irr"] is not None:
            assert econ["irr"] > 0

    def test_payback_finite_with_savings(self):
        """System with net savings should have finite payback."""
        load = np.full(8760, 10.0)
        results = {"load_kw": load}
        components = {
            "solar_pv": {"capital_cost": 50_000, "om_cost_annual": 500},
            "grid_connection": {"buy_rate": 0.20},
        }
        econ = compute_economics(results, components, lifetime_years=25, discount_rate=0.08)
        assert econ["payback_years"] < float("inf")

    def test_cost_breakdown_keys(self):
        """Cost breakdown must have all expected keys."""
        results = {"load_kw": np.full(8760, 5.0)}
        components = {"solar_pv": {"capital_cost": 10_000}}
        econ = compute_economics(results, components)
        breakdown = econ["cost_breakdown"]
        assert "capital_total" in breakdown
        assert "om_npv" in breakdown
        assert "fuel_npv" in breakdown
        assert "replacement_npv" in breakdown
        assert "salvage_npv" in breakdown

    def test_annual_costs_length(self):
        """Annual costs array must have lifetime+1 entries (year 0 through N)."""
        results = {"load_kw": np.full(8760, 5.0)}
        components = {"solar_pv": {"capital_cost": 10_000}}
        econ = compute_economics(results, components, lifetime_years=20)
        assert len(econ["annual_costs"]) == 21  # years 0-20
