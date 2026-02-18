"""Tests for financing module."""
import pytest
from engine.economics.financing import compute_wacc, loan_amortization, cashflow_projection


class TestComputeWACC:
    def test_all_equity(self):
        wacc = compute_wacc(debt_fraction=0.0, interest_rate=0.06, equity_cost=0.12)
        assert wacc == pytest.approx(0.12)

    def test_all_debt(self):
        wacc = compute_wacc(debt_fraction=1.0, interest_rate=0.06, equity_cost=0.12, tax_rate=0.0)
        assert wacc == pytest.approx(0.06)

    def test_mixed_with_tax(self):
        wacc = compute_wacc(debt_fraction=0.6, interest_rate=0.08, equity_cost=0.15, tax_rate=0.25)
        # E/V * Re + D/V * Rd * (1-Tc) = 0.4*0.15 + 0.6*0.08*0.75 = 0.06 + 0.036 = 0.096
        assert wacc == pytest.approx(0.096)


class TestLoanAmortization:
    def test_basic_schedule(self):
        schedule = loan_amortization(100000, 0.05, 10)
        assert len(schedule) == 10
        assert schedule[0]["year"] == 1
        assert schedule[-1]["remaining_balance"] == pytest.approx(0.0, abs=1.0)

    def test_total_interest(self):
        schedule = loan_amortization(100000, 0.05, 10)
        total_paid = sum(e["payment"] for e in schedule)
        total_interest = sum(e["interest_payment"] for e in schedule)
        # Total paid should exceed principal
        assert total_paid > 100000
        assert total_interest > 0
        # Principal payments should sum to principal
        total_principal = sum(e["principal_payment"] for e in schedule)
        assert total_principal == pytest.approx(100000, abs=1.0)

    def test_zero_interest(self):
        schedule = loan_amortization(100000, 0.0, 5)
        assert len(schedule) == 5
        for e in schedule:
            assert e["interest_payment"] == 0.0
            assert e["payment"] == pytest.approx(20000, abs=1.0)

    def test_empty_for_zero_principal(self):
        assert loan_amortization(0, 0.05, 10) == []

    def test_empty_for_zero_term(self):
        assert loan_amortization(100000, 0.05, 0) == []


class TestCashflowProjection:
    def test_basic_projection(self):
        cost_breakdown = {
            "capital_total": 100000,
            "om_annual": {"solar_pv": 1000},
            "fuel_annual": 0,
            "grid_annual": 0,
            "replacement_years": [],
            "replacement_cost_each": 0,
        }
        result = cashflow_projection(
            cost_breakdown=cost_breakdown,
            lifetime_years=25,
            discount_rate=0.08,
            debt_fraction=0.7,
            interest_rate=0.06,
            loan_term=10,
            annual_revenue=15000,
        )
        assert "wacc" in result
        assert "loan_schedule" in result
        assert "yearly_cashflows" in result
        assert len(result["yearly_cashflows"]) == 26  # year 0 to 25
        assert result["yearly_cashflows"][0]["year"] == 0
        assert result["equity_amount"] == pytest.approx(30000, abs=1)
        assert result["debt_amount"] == pytest.approx(70000, abs=1)

    def test_breakeven_occurs(self):
        cost_breakdown = {
            "capital_total": 50000,
            "om_annual": {"solar_pv": 500},
            "fuel_annual": 0,
            "grid_annual": 0,
            "replacement_years": [],
            "replacement_cost_each": 0,
        }
        result = cashflow_projection(
            cost_breakdown=cost_breakdown,
            lifetime_years=25,
            discount_rate=0.08,
            debt_fraction=0.5,
            interest_rate=0.05,
            loan_term=10,
            annual_revenue=10000,
        )
        # With $10k revenue and $50k capital, should break even
        assert result["breakeven_year"] is not None
        assert result["breakeven_year"] <= 25

    def test_no_debt(self):
        cost_breakdown = {
            "capital_total": 100000,
            "om_annual": {},
            "fuel_annual": 0,
            "grid_annual": 0,
            "replacement_years": [],
            "replacement_cost_each": 0,
        }
        result = cashflow_projection(
            cost_breakdown=cost_breakdown,
            lifetime_years=25,
            discount_rate=0.08,
            debt_fraction=0.0,
            interest_rate=0.06,
            loan_term=10,
            annual_revenue=15000,
        )
        assert result["debt_amount"] == 0
        assert result["equity_amount"] == 100000
        assert result["loan_schedule"] == []
