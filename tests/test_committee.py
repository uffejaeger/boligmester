import unittest

from apartment_agents.agents.committee import build_committee_finding, synthesize_committee
from apartment_agents.finance.models import FinanceResult
from apartment_agents.models import AgentFinding, ConfidenceScore


class CommitteeSynthesisTest(unittest.TestCase):
    def test_synthesis_returns_buy_for_strong_affordability_and_scores(self) -> None:
        finance = FinanceResult(
            debt_factor=3.1,
            disposable_income_after_housing_dkk=24000,
            housing_cost_monthly_dkk=21000,
            loan_to_value_pct=95.0,
            mortgage_principal_dkk=2600000,
            bank_loan_principal_dkk=480000,
            down_payment_dkk=215000,
            stress_test_housing_cost_monthly_dkk=23000,
            maximum_purchase_price_dkk=4100000,
            maximum_safe_purchase_price_dkk=4000000,
            approval_likelihood="high",
        )
        findings = [
            AgentFinding("listing_agent", "ok", ConfidenceScore(0.8), score=0.75),
            AgentFinding("market_comps_agent", "ok", ConfidenceScore(0.7), score=0.65),
            AgentFinding("danish_credit_agent", "ok", ConfidenceScore(0.9), score=0.8),
            AgentFinding("negotiation_agent", "ok", ConfidenceScore(0.6), score=0.6),
            AgentFinding("red_team_agent", "ok", ConfidenceScore(0.4), score=0.35),
        ]

        synthesis = synthesize_committee(findings, finance, listing_price_dkk=3295000)

        self.assertEqual(synthesis.recommendation.value, "BUY")
        self.assertGreaterEqual(synthesis.aggregate_score, 0.68)

    def test_synthesis_returns_maybe_when_red_team_and_market_disagree(self) -> None:
        finance = FinanceResult(
            debt_factor=3.0,
            disposable_income_after_housing_dkk=22000,
            housing_cost_monthly_dkk=21000,
            loan_to_value_pct=95.0,
            mortgage_principal_dkk=2600000,
            bank_loan_principal_dkk=480000,
            down_payment_dkk=215000,
            stress_test_housing_cost_monthly_dkk=23000,
            maximum_purchase_price_dkk=4100000,
            maximum_safe_purchase_price_dkk=3800000,
            approval_likelihood="high",
        )
        findings = [
            AgentFinding("listing_agent", "ok", ConfidenceScore(0.8), score=0.75),
            AgentFinding("market_comps_agent", "weak pricing", ConfidenceScore(0.4), score=0.4),
            AgentFinding("danish_credit_agent", "ok", ConfidenceScore(0.9), score=0.8),
            AgentFinding("negotiation_agent", "ok", ConfidenceScore(0.6), score=0.55),
            AgentFinding("red_team_agent", "risk", ConfidenceScore(0.8), score=0.8),
        ]

        synthesis = synthesize_committee(findings, finance, listing_price_dkk=3295000)
        committee_finding = build_committee_finding(synthesis)

        self.assertEqual(synthesis.recommendation.value, "MAYBE")
        self.assertTrue(synthesis.disagreements)
        self.assertIn("normalized_scores", committee_finding.details)


if __name__ == "__main__":
    unittest.main()
