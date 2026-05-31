import json
import unittest
from pathlib import Path

from apartment_agents.finance.engine import DanishCreditEngine
from apartment_agents.finance.models import FinanceInputs


FINANCE_SCENARIOS_PATH = Path("examples/finance/scenarios.json")


class DanishCreditEngineTest(unittest.TestCase):
    def _base_inputs(self, **overrides: int | float | None) -> FinanceInputs:
        defaults: dict[str, int | float | None] = {
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
        self.assertEqual(result.required_monthly_buffer_dkk, 7900)
        self.assertEqual(result.debt_factor_status, "standard")
        self.assertIn("not a lender credit decision", " ".join(result.policy_notes))

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
        self.assertEqual(result.required_monthly_buffer_dkk, 17370)

    def test_evaluate_returns_medium_for_resilient_elevated_debt_factor(self) -> None:
        engine = DanishCreditEngine()

        result = engine.evaluate(
            self._base_inputs(
                asking_price_dkk=4300000,
                savings_dkk=1000000,
                existing_debt_dkk=0,
                monthly_debt_payments_dkk=0,
            )
        )

        self.assertEqual(result.approval_likelihood, "medium")
        self.assertEqual(result.debt_factor_status, "elevated")
        self.assertGreater(result.stressed_net_wealth_dkk or 0, 0)

    def test_evaluate_returns_low_when_elevated_debt_factor_lacks_resilience(self) -> None:
        engine = DanishCreditEngine()

        result = engine.evaluate(
            self._base_inputs(
                asking_price_dkk=4300000,
                savings_dkk=250000,
                existing_debt_dkk=0,
                monthly_debt_payments_dkk=0,
            )
        )

        self.assertEqual(result.approval_likelihood, "low")
        self.assertEqual(result.debt_factor_status, "elevated")
        self.assertLess(result.stressed_net_wealth_dkk or 0, 0)

    def test_evaluate_runs_documented_scenario_fixtures(self) -> None:
        engine = DanishCreditEngine()
        payload = json.loads(FINANCE_SCENARIOS_PATH.read_text())

        for scenario in payload["scenarios"]:
            with self.subTest(scenario=scenario["name"]):
                result = engine.evaluate(FinanceInputs(**scenario["inputs"]))
                expected = scenario["expected"]

                self.assertEqual(result.approval_likelihood, expected["approval_likelihood"])
                self.assertEqual(
                    result.required_monthly_buffer_dkk,
                    expected["required_monthly_buffer_dkk"],
                )
                self.assertEqual(result.debt_factor_status, expected["debt_factor_status"])

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
        self.assertGreaterEqual(result.stress_test_housing_cost_monthly_dkk, 0)

    def test_evaluate_does_not_allow_explicit_stress_rate_below_policy_floor(self) -> None:
        engine = DanishCreditEngine()

        floored = engine.evaluate(
            self._base_inputs(
                nominal_interest_rate_pct=4.0,
                stress_interest_rate_pct=2.0,
            )
        )
        defaulted = engine.evaluate(
            self._base_inputs(
                nominal_interest_rate_pct=4.0,
                stress_interest_rate_pct=None,
            )
        )

        self.assertEqual(
            floored.stress_test_housing_cost_monthly_dkk,
            defaulted.stress_test_housing_cost_monthly_dkk,
        )

    def test_evaluate_rejects_impossible_income_inputs(self) -> None:
        engine = DanishCreditEngine()

        with self.assertRaisesRegex(ValueError, "gross_annual_income_dkk must be positive"):
            engine.evaluate(self._base_inputs(gross_annual_income_dkk=0))

        with self.assertRaisesRegex(ValueError, "net_monthly_income_dkk must be positive"):
            engine.evaluate(self._base_inputs(net_monthly_income_dkk=-1))

        with self.assertRaisesRegex(ValueError, "cannot annualize above"):
            engine.evaluate(
                self._base_inputs(
                    gross_annual_income_dkk=300000,
                    net_monthly_income_dkk=40000,
                )
            )

    def test_evaluate_rejects_impossible_property_and_household_inputs(self) -> None:
        engine = DanishCreditEngine()

        invalid_inputs = [
            ("asking_price_dkk", {"asking_price_dkk": 0}),
            ("owner_cost_monthly_dkk", {"owner_cost_monthly_dkk": -1}),
            ("adults", {"adults": 0}),
            ("children", {"children": -1}),
        ]

        for field_name, overrides in invalid_inputs:
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, field_name):
                    engine.evaluate(self._base_inputs(**overrides))

    def test_evaluate_rejects_impossible_financing_inputs(self) -> None:
        engine = DanishCreditEngine()

        with self.assertRaisesRegex(ValueError, "mortgage_share cannot exceed"):
            engine.evaluate(self._base_inputs(mortgage_share=0.81, bank_share=0.14))

        with self.assertRaisesRegex(ValueError, "cannot finance more than 95%"):
            engine.evaluate(self._base_inputs(mortgage_share=0.8, bank_share=0.16))


if __name__ == "__main__":
    unittest.main()
