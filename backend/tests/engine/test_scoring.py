"""Tests for multi-scenario scoring module."""
import pytest
from engine.economics.scoring import normalize_metrics, score_scenarios


class TestNormalizeMetrics:
    def test_lower_is_better(self):
        scenarios = [
            {"npc": 100000, "simulation_id": "a"},
            {"npc": 200000, "simulation_id": "b"},
        ]
        result = normalize_metrics(scenarios, ["npc"])
        assert result[0]["npc"] == pytest.approx(1.0)  # lower = better
        assert result[1]["npc"] == pytest.approx(0.0)

    def test_higher_is_better(self):
        scenarios = [
            {"renewable_fraction": 0.3, "simulation_id": "a"},
            {"renewable_fraction": 0.9, "simulation_id": "b"},
        ]
        result = normalize_metrics(scenarios, ["renewable_fraction"])
        assert result[0]["renewable_fraction"] == pytest.approx(0.0)  # lower = worse
        assert result[1]["renewable_fraction"] == pytest.approx(1.0)

    def test_all_same_value(self):
        scenarios = [
            {"npc": 100000, "simulation_id": "a"},
            {"npc": 100000, "simulation_id": "b"},
        ]
        result = normalize_metrics(scenarios, ["npc"])
        assert result[0]["npc"] == pytest.approx(1.0)
        assert result[1]["npc"] == pytest.approx(1.0)

    def test_none_values(self):
        scenarios = [
            {"irr": 0.1, "simulation_id": "a"},
            {"irr": None, "simulation_id": "b"},
        ]
        result = normalize_metrics(scenarios, ["irr"])
        assert result[0]["irr"] == pytest.approx(1.0)
        assert result[1]["irr"] == pytest.approx(0.0)

    def test_empty_input(self):
        assert normalize_metrics([]) == []


class TestScoreScenarios:
    def test_basic_ranking(self):
        scenarios = [
            {"simulation_id": "a", "simulation_name": "Cheap", "npc": 50000, "lcoe": 0.10, "irr": 0.12, "renewable_fraction": 0.8, "payback_years": 5, "co2_emissions_kg": 1000},
            {"simulation_id": "b", "simulation_name": "Expensive", "npc": 100000, "lcoe": 0.20, "irr": 0.05, "renewable_fraction": 0.4, "payback_years": 12, "co2_emissions_kg": 5000},
        ]
        result = score_scenarios(scenarios)
        assert len(result) == 2
        assert result[0]["rank"] == 1
        assert result[1]["rank"] == 2
        assert result[0]["simulation_name"] == "Cheap"  # better on all metrics

    def test_custom_weights(self):
        scenarios = [
            {"simulation_id": "a", "npc": 100000, "renewable_fraction": 0.9, "lcoe": 0.15, "irr": None, "payback_years": None, "co2_emissions_kg": 500},
            {"simulation_id": "b", "npc": 50000, "renewable_fraction": 0.3, "lcoe": 0.10, "irr": None, "payback_years": None, "co2_emissions_kg": 3000},
        ]
        # Heavy weight on renewable_fraction
        result = score_scenarios(scenarios, weights={"renewable_fraction": 10.0, "npc": 1.0, "lcoe": 1.0, "co2_emissions_kg": 1.0})
        # Scenario A should win because of high renewable fraction weight
        assert result[0]["simulation_id"] == "a"

    def test_scores_sum_reasonable(self):
        scenarios = [
            {"simulation_id": "a", "npc": 70000, "lcoe": 0.12, "irr": 0.08, "renewable_fraction": 0.6, "payback_years": 8, "co2_emissions_kg": 2000},
        ]
        result = score_scenarios(scenarios)
        assert len(result) == 1
        assert 0 <= result[0]["score"] <= 1.0

    def test_empty_input(self):
        assert score_scenarios([]) == []
