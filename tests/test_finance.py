import unittest

from apartment_agents.finance.engine import DanishCreditEngine
from apartment_agents.finance.models import FinanceInputs


class DanishCreditEngineTest(unittest.TestCase):
    def _base_inputs(self, **overrides: int | float) -> FinanceInputs:
        defaults: dict[str, int | float] = {
            "gross_annual_income_dkk": 960000,
            "net_monthly_income_dkk": 47000,
            "savings_dkk": 550000,
            "existing_debt_dkk": 25000,
            "monthly_debt_payments_dkk": 900,
            "asking_price_dkk": 3295000,
            "owner_cost_monthly_dkk": 3650,
            "adults": 1,
            "children": 0,
            "monthly_childcare_cost_dkk": 0,
            "nominal_interest_rate_pct": 4.0,
            "stress_interest_rate_pct": 6.0,
        }
        defaults.update(overrides)
        return FinanceInputs(**defaults)

    def test_evaluate_returns_deterministic_metrics(self) -> None:
        engine = DanishCreditEngine()

        result = engine.evaluate(self._base_inputs())

        self.assertEqual(result.approval_likelihood, "high")
        self.assertGreater(result.maximum_safe_purchase_price_dkk, 3000000)
        self.assertAlmostEqual(result.loan_to_value_pct, 95.0)

    def test_evaluate_returns_low_when_savings_do_not_cover_down_payment(self) -> None:
        engine = DanishCreditEngine()

        result = engine.evaluate(self._base_inputs(savings_dkk=50000))

        self.assertEqual(result.approval_likelihood, "low")
        self.assertEqual(result.down_payment_dkk, 164750)

    def test_evaluate_returns_low_when_debt_factor_exceeds_policy(self) -> None:
        engine = DanishCreditEngine()

        result = engine.evaluate(self._base_inputs(existing_debt_dkk=1500000))

        self.assertEqual(result.approval_likelihood, "low")
        self.assertGreater(result.debt_factor, 4.0)

    def test_evaluate_returns_medium_when_stress_buffer_is_tight(self) -> None:
        engine = DanishCreditEngine()

        result = engine.evaluate(
            self._base_inputs(
                net_monthly_income_dkk=34000,
                monthly_childcare_cost_dkk=3500,
                adults=2,
                children=1,
            )
        )

        self.assertEqual(result.approval_likelihood, "medium")
        self.assertLess(result.disposable_income_after_housing_dkk, 19000)

    def test_evaluate_handles_zero_interest_rates(self) -> None:
        engine = DanishCreditEngine()

        result = engine.evaluate(
            self._base_inputs(
                nominal_interest_rate_pct=0.0,
                stress_interest_rate_pct=0.0,
            )
        )

        self.assertGreater(result.maximum_purchase_price_dkk, 0)
        self.assertGreater(result.maximum_safe_purchase_price_dkk, 0)


if __name__ == "__main__":
    unittest.main()
