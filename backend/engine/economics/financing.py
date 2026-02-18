"""Financing analysis: WACC, loan amortization, and cashflow projection.

Extends the base economics module with financing-specific calculations
for debt/equity split, tax shield, and cumulative discounted cashflows.
"""
from __future__ import annotations

import math


def compute_wacc(
    debt_fraction: float,
    interest_rate: float,
    equity_cost: float,
    tax_rate: float = 0.0,
) -> float:
    """Weighted average cost of capital.

    WACC = E/V * Re + D/V * Rd * (1 - Tc)
    """
    equity_fraction = 1.0 - debt_fraction
    wacc = equity_fraction * equity_cost + debt_fraction * interest_rate * (1.0 - tax_rate)
    return wacc


def loan_amortization(
    principal: float,
    interest_rate: float,
    loan_term: int,
) -> list[dict[str, float]]:
    """Generate a loan amortization schedule.

    Returns a list of dicts with keys: year, payment, principal_payment,
    interest_payment, remaining_balance.
    """
    if loan_term <= 0 or principal <= 0:
        return []

    if interest_rate <= 0:
        annual_payment = principal / loan_term
        schedule = []
        balance = principal
        for yr in range(1, loan_term + 1):
            schedule.append({
                "year": yr,
                "payment": round(annual_payment, 2),
                "principal_payment": round(annual_payment, 2),
                "interest_payment": 0.0,
                "remaining_balance": round(max(balance - annual_payment, 0.0), 2),
            })
            balance -= annual_payment
        return schedule

    # Standard amortization formula
    r = interest_rate
    n = loan_term
    annual_payment = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)

    schedule = []
    balance = principal
    for yr in range(1, n + 1):
        interest = balance * r
        principal_pmt = annual_payment - interest
        balance -= principal_pmt
        schedule.append({
            "year": yr,
            "payment": round(annual_payment, 2),
            "principal_payment": round(principal_pmt, 2),
            "interest_payment": round(interest, 2),
            "remaining_balance": round(max(balance, 0.0), 2),
        })

    return schedule


def cashflow_projection(
    cost_breakdown: dict,
    lifetime_years: int,
    discount_rate: float,
    debt_fraction: float = 0.7,
    interest_rate: float = 0.06,
    loan_term: int = 10,
    equity_cost: float = 0.12,
    tax_rate: float = 0.0,
    om_escalation: float = 0.02,
    annual_revenue: float = 0.0,
) -> dict:
    """Build a full cashflow projection with financing.

    Parameters
    ----------
    cost_breakdown : dict
        From compute_economics() output.
    lifetime_years : int
        Project lifetime in years.
    discount_rate : float
        Discount rate for NPV calculations.
    debt_fraction : float
        Fraction of capital financed by debt (0-1).
    interest_rate : float
        Annual interest rate on debt.
    loan_term : int
        Loan repayment period in years.
    equity_cost : float
        Required return on equity.
    tax_rate : float
        Corporate tax rate (for interest tax shield).
    om_escalation : float
        Annual O&M cost escalation rate.
    annual_revenue : float
        Annual revenue or savings from the system (for breakeven calc).

    Returns
    -------
    dict with wacc, loan_schedule, yearly_cashflows, breakeven_year, totals.
    """
    capital_total = float(cost_breakdown.get("capital_total", 0))
    om_annual_base = float(cost_breakdown.get("om_npv", 0)) / max(lifetime_years, 1) if "om_annual" not in cost_breakdown else sum(
        v for v in (cost_breakdown.get("om_annual", {}) if isinstance(cost_breakdown.get("om_annual"), dict) else {}).values()
    )
    fuel_annual = float(cost_breakdown.get("fuel_annual", 0))
    grid_annual = float(cost_breakdown.get("grid_annual", 0))
    replacement_years = cost_breakdown.get("replacement_years", [])
    replacement_cost = float(cost_breakdown.get("replacement_cost_each", 0))

    # Compute WACC
    wacc = compute_wacc(debt_fraction, interest_rate, equity_cost, tax_rate)

    # Loan schedule
    debt_amount = capital_total * debt_fraction
    equity_amount = capital_total * (1.0 - debt_fraction)
    loan_schedule = loan_amortization(debt_amount, interest_rate, loan_term)

    # Build yearly cashflows
    yearly = []
    cumulative_nominal = 0.0
    cumulative_discounted = 0.0
    breakeven_year = None

    for yr in range(0, lifetime_years + 1):
        entry: dict[str, float] = {"year": yr}

        if yr == 0:
            entry["equity_investment"] = -equity_amount
            entry["debt_drawdown"] = debt_amount
            entry["capital_outlay"] = -capital_total
            entry["om_cost"] = 0.0
            entry["fuel_cost"] = 0.0
            entry["grid_cost"] = 0.0
            entry["loan_payment"] = 0.0
            entry["interest_payment"] = 0.0
            entry["tax_shield"] = 0.0
            entry["replacement_cost"] = 0.0
            entry["revenue"] = 0.0
            entry["net_cashflow"] = -equity_amount
            entry["discount_factor"] = 1.0
            entry["discounted_cashflow"] = -equity_amount
            cumulative_nominal = -equity_amount
            cumulative_discounted = -equity_amount
        else:
            # O&M with escalation
            om = om_annual_base * (1.0 + om_escalation) ** (yr - 1)
            fuel = fuel_annual
            grid = grid_annual
            repl = replacement_cost if yr in replacement_years else 0.0

            # Loan payment
            loan_pmt = 0.0
            interest_pmt = 0.0
            if yr <= loan_term and loan_schedule:
                ls = loan_schedule[yr - 1]
                loan_pmt = ls["payment"]
                interest_pmt = ls["interest_payment"]

            # Tax shield on interest
            tax_shield = interest_pmt * tax_rate

            # Net cashflow
            revenue = annual_revenue
            net = revenue - om - fuel - grid - loan_pmt + tax_shield - repl

            df = 1.0 / (1.0 + discount_rate) ** yr

            entry["equity_investment"] = 0.0
            entry["debt_drawdown"] = 0.0
            entry["capital_outlay"] = 0.0
            entry["om_cost"] = -round(om, 2)
            entry["fuel_cost"] = -round(fuel, 2)
            entry["grid_cost"] = -round(grid, 2)
            entry["loan_payment"] = -round(loan_pmt, 2)
            entry["interest_payment"] = -round(interest_pmt, 2)
            entry["tax_shield"] = round(tax_shield, 2)
            entry["replacement_cost"] = -round(repl, 2)
            entry["revenue"] = round(revenue, 2)
            entry["net_cashflow"] = round(net, 2)
            entry["discount_factor"] = round(df, 6)
            entry["discounted_cashflow"] = round(net * df, 2)

            cumulative_nominal += net
            cumulative_discounted += net * df

        entry["cumulative_nominal"] = round(cumulative_nominal, 2)
        entry["cumulative_discounted"] = round(cumulative_discounted, 2)

        if breakeven_year is None and cumulative_discounted >= 0 and yr > 0:
            breakeven_year = yr

        yearly.append(entry)

    return {
        "wacc": round(wacc, 6),
        "debt_amount": round(debt_amount, 2),
        "equity_amount": round(equity_amount, 2),
        "loan_schedule": loan_schedule,
        "yearly_cashflows": yearly,
        "breakeven_year": breakeven_year,
        "total_debt_service": round(sum(e["payment"] for e in loan_schedule), 2),
        "total_interest": round(sum(e["interest_payment"] for e in loan_schedule), 2),
    }
