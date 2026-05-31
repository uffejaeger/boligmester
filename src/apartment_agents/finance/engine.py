from __future__ import annotations

from dataclasses import dataclass
from math import pow

from apartment_agents.finance.models import FinanceInputs, FinanceResult


@dataclass(slots=True)
class AffordabilityPolicy:
    minimum_down_payment_ratio: float = 0.05
    maximum_debt_factor: float = 4.0
    minimum_monthly_buffer_dkk_single: int = 9000
    minimum_monthly_buffer_dkk_couple: int = 14000
    minimum_monthly_buffer_per_child_dkk: int = 2500

    def required_monthly_buffer(self, adults: int, children: int) -> int:
        base = (
            self.minimum_monthly_buffer_dkk_single
            if adults <= 1
            else self.minimum_monthly_buffer_dkk_couple
        )
        return base + children * self.minimum_monthly_buffer_per_child_dkk


class DanishCreditEngine:
    """Deterministic credit calculations only. No LLM-generated numbers."""

    def __init__(self, policy: AffordabilityPolicy | None = None) -> None:
        self.policy = policy or AffordabilityPolicy()

    def evaluate(self, inputs: FinanceInputs) -> FinanceResult:
        down_payment_dkk = max(
            int(inputs.asking_price_dkk * self.policy.minimum_down_payment_ratio),
            0,
        )
        mortgage_principal_dkk = int(inputs.asking_price_dkk * inputs.mortgage_share)
        bank_loan_principal_dkk = int(inputs.asking_price_dkk * inputs.bank_share)

        debt_factor = self._calculate_debt_factor(
            mortgage_principal_dkk=mortgage_principal_dkk,
            bank_loan_principal_dkk=bank_loan_principal_dkk,
            existing_debt_dkk=inputs.existing_debt_dkk,
            gross_annual_income_dkk=inputs.gross_annual_income_dkk,
        )

        housing_cost_monthly_dkk = self._calculate_monthly_housing_cost(
            mortgage_principal_dkk=mortgage_principal_dkk,
            bank_loan_principal_dkk=bank_loan_principal_dkk,
            owner_cost_monthly_dkk=inputs.owner_cost_monthly_dkk,
            mortgage_rate_pct=inputs.nominal_interest_rate_pct,
            bank_rate_pct=inputs.nominal_interest_rate_pct + 1.5,
            mortgage_years=inputs.mortgage_years,
            bank_loan_years=inputs.bank_loan_years,
        )
        stress_housing_cost_monthly_dkk = self._calculate_monthly_housing_cost(
            mortgage_principal_dkk=mortgage_principal_dkk,
            bank_loan_principal_dkk=bank_loan_principal_dkk,
            owner_cost_monthly_dkk=inputs.owner_cost_monthly_dkk,
            mortgage_rate_pct=inputs.stress_interest_rate_pct,
            bank_rate_pct=inputs.stress_interest_rate_pct + 1.5,
            mortgage_years=inputs.mortgage_years,
            bank_loan_years=inputs.bank_loan_years,
        )
        disposable_income_after_housing_dkk = (
            inputs.net_monthly_income_dkk
            - inputs.monthly_debt_payments_dkk
            - inputs.monthly_childcare_cost_dkk
            - housing_cost_monthly_dkk
        )

        loan_to_value_pct = round(
            ((mortgage_principal_dkk + bank_loan_principal_dkk) / inputs.asking_price_dkk) * 100,
            1,
        )
        required_buffer_dkk = self.policy.required_monthly_buffer(
            adults=inputs.adults,
            children=inputs.children,
        )

        maximum_purchase_price_dkk = self._calculate_maximum_purchase_price(
            inputs=inputs,
            monthly_buffer_dkk=required_buffer_dkk,
            annual_rate_pct=inputs.nominal_interest_rate_pct,
        )
        maximum_safe_purchase_price_dkk = self._calculate_maximum_purchase_price(
            inputs=inputs,
            monthly_buffer_dkk=required_buffer_dkk,
            annual_rate_pct=inputs.stress_interest_rate_pct,
        )

        approval_likelihood = self._approval_likelihood(
            savings_dkk=inputs.savings_dkk,
            minimum_required_down_payment_dkk=down_payment_dkk,
            debt_factor=debt_factor,
            stress_disposable_income_dkk=(
                inputs.net_monthly_income_dkk
                - inputs.monthly_debt_payments_dkk
                - inputs.monthly_childcare_cost_dkk
                - stress_housing_cost_monthly_dkk
            ),
            required_buffer_dkk=required_buffer_dkk,
        )

        return FinanceResult(
            debt_factor=round(debt_factor, 2),
            disposable_income_after_housing_dkk=int(disposable_income_after_housing_dkk),
            housing_cost_monthly_dkk=int(housing_cost_monthly_dkk),
            loan_to_value_pct=loan_to_value_pct,
            mortgage_principal_dkk=mortgage_principal_dkk,
            bank_loan_principal_dkk=bank_loan_principal_dkk,
            down_payment_dkk=down_payment_dkk,
            stress_test_housing_cost_monthly_dkk=int(stress_housing_cost_monthly_dkk),
            maximum_purchase_price_dkk=int(maximum_purchase_price_dkk),
            maximum_safe_purchase_price_dkk=int(maximum_safe_purchase_price_dkk),
            approval_likelihood=approval_likelihood,
            policy_notes=[
                "Calculations are deterministic and independent of LLM output.",
                "The current policy uses conservative placeholder affordability thresholds.",
            ],
        )

    def _calculate_debt_factor(
        self,
        mortgage_principal_dkk: int,
        bank_loan_principal_dkk: int,
        existing_debt_dkk: int,
        gross_annual_income_dkk: int,
    ) -> float:
        total_debt = mortgage_principal_dkk + bank_loan_principal_dkk + existing_debt_dkk
        return total_debt / gross_annual_income_dkk

    def _calculate_monthly_housing_cost(
        self,
        mortgage_principal_dkk: int,
        bank_loan_principal_dkk: int,
        owner_cost_monthly_dkk: int,
        mortgage_rate_pct: float,
        bank_rate_pct: float,
        mortgage_years: int,
        bank_loan_years: int,
    ) -> float:
        mortgage_payment = self._annuity_payment(
            principal=mortgage_principal_dkk,
            annual_rate_pct=mortgage_rate_pct,
            years=mortgage_years,
        )
        bank_payment = self._annuity_payment(
            principal=bank_loan_principal_dkk,
            annual_rate_pct=bank_rate_pct,
            years=bank_loan_years,
        )
        return mortgage_payment + bank_payment + owner_cost_monthly_dkk

    def _annuity_payment(self, principal: int, annual_rate_pct: float, years: int) -> float:
        monthly_rate = annual_rate_pct / 100 / 12
        periods = years * 12
        if principal <= 0:
            return 0.0
        if monthly_rate == 0:
            return principal / periods
        factor = monthly_rate * pow(1 + monthly_rate, periods)
        denominator = pow(1 + monthly_rate, periods) - 1
        return principal * factor / denominator

    def _calculate_maximum_purchase_price(
        self,
        inputs: FinanceInputs,
        monthly_buffer_dkk: int,
        annual_rate_pct: float,
    ) -> int:
        available_for_housing = (
            inputs.net_monthly_income_dkk
            - inputs.monthly_debt_payments_dkk
            - inputs.monthly_childcare_cost_dkk
            - monthly_buffer_dkk
        )
        if available_for_housing <= inputs.owner_cost_monthly_dkk:
            return 0

        loan_capacity_monthly = available_for_housing - inputs.owner_cost_monthly_dkk
        monthly_rate = annual_rate_pct / 100 / 12
        periods = inputs.mortgage_years * 12
        if monthly_rate == 0:
            annuity_factor = periods
        else:
            annuity_factor = ((1 + monthly_rate) ** periods - 1) / (
                monthly_rate * (1 + monthly_rate) ** periods
            )
        mortgage_capacity = loan_capacity_monthly * annuity_factor
        total_purchase_capacity = mortgage_capacity / max(inputs.mortgage_share, 0.01)

        if inputs.savings_dkk < int(total_purchase_capacity * self.policy.minimum_down_payment_ratio):
            total_purchase_capacity = inputs.savings_dkk / self.policy.minimum_down_payment_ratio

        if (
            total_purchase_capacity * (inputs.mortgage_share + inputs.bank_share)
            + inputs.existing_debt_dkk
        ) / inputs.gross_annual_income_dkk > self.policy.maximum_debt_factor:
            total_purchase_capacity = (
                inputs.gross_annual_income_dkk * self.policy.maximum_debt_factor
                - inputs.existing_debt_dkk
            ) / max(inputs.mortgage_share + inputs.bank_share, 0.01)

        return max(int(total_purchase_capacity), 0)

    def _approval_likelihood(
        self,
        savings_dkk: int,
        minimum_required_down_payment_dkk: int,
        debt_factor: float,
        stress_disposable_income_dkk: int,
        required_buffer_dkk: int,
    ) -> str:
        if savings_dkk < minimum_required_down_payment_dkk:
            return "low"
        if debt_factor > self.policy.maximum_debt_factor:
            return "low"
        if stress_disposable_income_dkk < required_buffer_dkk:
            return "medium"
        return "high"
