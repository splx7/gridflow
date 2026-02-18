"""Pydantic schemas for financing analysis."""
from pydantic import BaseModel, Field


class FinancingParams(BaseModel):
    debt_fraction: float = Field(default=0.7, ge=0.0, le=1.0, description="Fraction of capital financed by debt")
    interest_rate: float = Field(default=0.06, ge=0.0, le=1.0, description="Annual interest rate on debt")
    loan_term: int = Field(default=10, ge=1, le=30, description="Loan repayment period in years")
    equity_cost: float = Field(default=0.12, ge=0.0, le=1.0, description="Required return on equity")
    tax_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Corporate tax rate")
    om_escalation: float = Field(default=0.02, ge=0.0, le=0.2, description="Annual O&M cost escalation rate")
