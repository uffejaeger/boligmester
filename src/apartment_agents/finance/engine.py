from __future__ import annotations

from dataclasses import dataclass
from math import pow

from apartment_agents.finance.models import FinanceInputs, FinanceResult


@dataclass(slots=True)
class AffordabilityPolicy:
    minimum_down_payment_ratio: float = 0.05
    maximum_mortgage_share: float = 0.8
    maximum_debt_factor: float = 4.0
    extended_debt_factor: float = 5.0
    debt_factor_warning_price_shock_pct: float = 0.10
    debt_factor_high_price_shock_pct: float = 0.25
    minimum_monthly_buffer_dkk_first_adult: int = 7900
    minimum_monthly_buffer_dkk_additional_adult: int = 5500
    minimum_monthly_buffer_per_child_dkk: int = 3970
    stress_rate_markup_pct: float = 1.0
    minimum_stress_interest_rate_pct: float = 4.0

    def required_monthly_buffer(self, adults: int, children: int) -> int:
        additional_adults = max(adults - 1, 0)
        return (
            self.minimum_monthly_buffer_dkk_first_adult
            + additional_adults * self.minimum_monthly_buffer_dkk_additional_adult
            + children * self.minimum_monthly_buffer_per_child_dkk
        )


class DanishCreditEngine:
    """Deterministic credit calculations only. No LLM-generated numbers."""

    def __init__(self, policy: AffordabilityPolicy | None = None) -> None:
        self.policy = policy or AffordabilityPolicy()

    def evaluate(self, inputs: FinanceInputs) -> FinanceResult:
        self._validate_inputs(inputs)

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
        stress_interest_rate_pct = self._effective_stress_interest_rate_pct(inputs)
        stress_housing_cost_monthly_dkk = self._calculate_monthly_housing_cost(
            mortgage_principal_dkk=mortgage_principal_dkk,
            bank_loan_principal_dkk=bank_loan_principal_dkk,
            owner_cost_monthly_dkk=inputs.owner_cost_monthly_dkk,
            mortgage_rate_pct=stress_interest_rate_pct,
            bank_rate_pct=stress_interest_rate_pct + 1.5,
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
            annual_rate_pct=stress_interest_rate_pct,
        )
        stress_disposable_income_after_housing_dkk = (
            inputs.net_monthly_income_dkk
            - inputs.monthly_debt_payments_dkk
            - inputs.monthly_childcare_cost_dkk
            - stress_housing_cost_monthly_dkk
        )
        post_purchase_liquid_assets_dkk = inputs.savings_dkk - down_payment_dkk
        debt_factor_status = self._debt_factor_status(debt_factor)
        stressed_net_wealth_dkk = self._calculate_stressed_net_wealth(
            asking_price_dkk=inputs.asking_price_dkk,
            mortgage_principal_dkk=mortgage_principal_dkk,
            bank_loan_principal_dkk=bank_loan_principal_dkk,
            existing_debt_dkk=inputs.existing_debt_dkk,
            post_purchase_liquid_assets_dkk=post_purchase_liquid_assets_dkk,
            debt_factor=debt_factor,
        )

        approval_likelihood = self._approval_likelihood(
            savings_dkk=inputs.savings_dkk,
            minimum_required_down_payment_dkk=down_payment_dkk,
            debt_factor=debt_factor,
            stress_disposable_income_dkk=stress_disposable_income_after_housing_dkk,
            required_buffer_dkk=required_buffer_dkk,
            stressed_net_wealth_dkk=stressed_net_wealth_dkk,
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
            required_monthly_buffer_dkk=required_buffer_dkk,
            stress_disposable_income_after_housing_dkk=int(
                stress_disposable_income_after_housing_dkk
            ),
            post_purchase_liquid_assets_dkk=post_purchase_liquid_assets_dkk,
            stressed_net_wealth_dkk=stressed_net_wealth_dkk,
            debt_factor_status=debt_factor_status,
            policy_notes=[
                "Calculations are deterministic and independent of LLM output.",
                "Financing assumes a standard owner-occupied split: 80% mortgage, "
                "15% bank loan, and at least 5% buyer down payment before costs.",
                "Monthly buffer floor uses 2026 debt-restructuring allowance rates: "
                "7,900 DKK for the first adult, 5,500 DKK per additional adult, "
                "and 3,970 DKK per child because child age is not modelled.",
                f"Stress calculations use at least {self.policy.minimum_stress_interest_rate_pct:.1f}% "
                f"or nominal rate plus {self.policy.stress_rate_markup_pct:.1f} percentage point.",
                "Debt factors above 4 are treated as elevated risk and require positive "
                "net wealth after the relevant price-fall shock.",
                "This is a screening heuristic, not a lender credit decision.",
            ],
        )

    def _validate_inputs(self, inputs: FinanceInputs) -> None:
        positive_fields = {
            "gross_annual_income_dkk": inputs.gross_annual_income_dkk,
            "net_monthly_income_dkk": inputs.net_monthly_income_dkk,
            "asking_price_dkk": inputs.asking_price_dkk,
            "adults": inputs.adults,
            "mortgage_years": inputs.mortgage_years,
            "bank_loan_years": inputs.bank_loan_years,
        }
        for field_name, value in positive_fields.items():
            if value <= 0:
                raise ValueError(f"{field_name} must be positive.")

        non_negative_fields = {
            "savings_dkk": inputs.savings_dkk,
            "existing_debt_dkk": inputs.existing_debt_dkk,
            "monthly_debt_payments_dkk": inputs.monthly_debt_payments_dkk,
            "owner_cost_monthly_dkk": inputs.owner_cost_monthly_dkk,
            "children": inputs.children,
            "monthly_childcare_cost_dkk": inputs.monthly_childcare_cost_dkk,
            "nominal_interest_rate_pct": inputs.nominal_interest_rate_pct,
            "mortgage_share": inputs.mortgage_share,
            "bank_share": inputs.bank_share,
        }
        for field_name, value in non_negative_fields.items():
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative.")

        if inputs.stress_interest_rate_pct is not None and inputs.stress_interest_rate_pct < 0:
            raise ValueError("stress_interest_rate_pct must be non-negative.")

        if inputs.net_monthly_income_dkk * 12 > inputs.gross_annual_income_dkk:
            raise ValueError(
                "net_monthly_income_dkk cannot annualize above gross_annual_income_dkk."
            )

        if inputs.mortgage_share > self.policy.maximum_mortgage_share:
            raise ValueError("mortgage_share cannot exceed the owner-occupied 80% cap.")

        maximum_financed_share = 1 - self.policy.minimum_down_payment_ratio
        if inputs.mortgage_share + inputs.bank_share > maximum_financed_share + 1e-9:
            raise ValueError("mortgage_share and bank_share cannot finance more than 95%.")

    def _effective_stress_interest_rate_pct(self, inputs: FinanceInputs) -> float:
        policy_stress_rate = max(
            inputs.nominal_interest_rate_pct + self.policy.stress_rate_markup_pct,
            self.policy.minimum_stress_interest_rate_pct,
        )
        if inputs.stress_interest_rate_pct is None:
            return policy_stress_rate
        return max(inputs.stress_interest_rate_pct, policy_stress_rate)

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

        if inputs.savings_dkk < int(
            total_purchase_capacity * self.policy.minimum_down_payment_ratio
        ):
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

    def _debt_factor_status(self, debt_factor: float) -> str:
        if debt_factor <= self.policy.maximum_debt_factor:
            return "standard"
        if debt_factor <= self.policy.extended_debt_factor:
            return "elevated"
        return "high"

    def _calculate_stressed_net_wealth(
        self,
        asking_price_dkk: int,
        mortgage_principal_dkk: int,
        bank_loan_principal_dkk: int,
        existing_debt_dkk: int,
        post_purchase_liquid_assets_dkk: int,
        debt_factor: float,
    ) -> int | None:
        price_shock_pct = self._debt_factor_price_shock_pct(debt_factor)
        if price_shock_pct is None:
            return None

        shocked_home_value_dkk = int(asking_price_dkk * (1 - price_shock_pct))
        home_debt_dkk = mortgage_principal_dkk + bank_loan_principal_dkk
        return (
            post_purchase_liquid_assets_dkk
            + shocked_home_value_dkk
            - home_debt_dkk
            - existing_debt_dkk
        )

    def _debt_factor_price_shock_pct(self, debt_factor: float) -> float | None:
        if debt_factor > self.policy.extended_debt_factor:
            return self.policy.debt_factor_high_price_shock_pct
        if debt_factor > self.policy.maximum_debt_factor:
            return self.policy.debt_factor_warning_price_shock_pct
        return None

    def _approval_likelihood(
        self,
        savings_dkk: int,
        minimum_required_down_payment_dkk: int,
        debt_factor: float,
        stress_disposable_income_dkk: int,
        required_buffer_dkk: int,
        stressed_net_wealth_dkk: int | None,
    ) -> str:
        if savings_dkk < minimum_required_down_payment_dkk:
            return "low"
        if stressed_net_wealth_dkk is not None and stressed_net_wealth_dkk < 0:
            return "low"
        if stress_disposable_income_dkk < 0:
            return "low"
        if stress_disposable_income_dkk < required_buffer_dkk:
            return "medium"
        if debt_factor > self.policy.maximum_debt_factor:
            return "medium"
        return "high"
