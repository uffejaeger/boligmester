from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FinanceInputs:
    gross_annual_income_dkk: int
    net_monthly_income_dkk: int
    savings_dkk: int
    existing_debt_dkk: int
    monthly_debt_payments_dkk: int
    asking_price_dkk: int
    owner_cost_monthly_dkk: int
    adults: int
    children: int
    monthly_childcare_cost_dkk: int
    nominal_interest_rate_pct: float = 4.0
    stress_interest_rate_pct: float | None = None
    mortgage_years: int = 30
    bank_loan_years: int = 10
    mortgage_share: float = 0.8
    bank_share: float = 0.15


@dataclass(slots=True)
class FinanceResult:
    debt_factor: float
    disposable_income_after_housing_dkk: int
    housing_cost_monthly_dkk: int
    loan_to_value_pct: float
    mortgage_principal_dkk: int
    bank_loan_principal_dkk: int
    down_payment_dkk: int
    stress_test_housing_cost_monthly_dkk: int
    maximum_purchase_price_dkk: int
    maximum_safe_purchase_price_dkk: int
    approval_likelihood: str
    required_monthly_buffer_dkk: int = 0
    stress_disposable_income_after_housing_dkk: int = 0
    post_purchase_liquid_assets_dkk: int = 0
    stressed_net_wealth_dkk: int | None = None
    debt_factor_status: str = "standard"
    policy_notes: list[str] = field(default_factory=list)
