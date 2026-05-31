import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apartment_agents.adk.runner import GoogleAdkAnalysisRunner, MockAdkAnalysisRunner, build_runner
from apartment_agents.config import AppConfig


class RunnerFactoryTest(unittest.TestCase):
    def test_build_runner_returns_mock_runner_for_mock_backend(self) -> None:
        with TemporaryDirectory() as tmpdir:
            runner = build_runner(AppConfig(output_dir=Path(tmpdir), adk_backend="mock"))
            self.assertIsInstance(runner, MockAdkAnalysisRunner)

    def test_build_runner_returns_google_adk_runner_for_google_backend(self) -> None:
        with TemporaryDirectory() as tmpdir:
            runner = build_runner(
                AppConfig(
                    output_dir=Path(tmpdir),
                    adk_backend="google_adk",
                    google_api_key="test-key",
                )
            )
            self.assertIsInstance(runner, GoogleAdkAnalysisRunner)

    def test_google_adk_runner_parses_structured_json_response(self) -> None:
        with TemporaryDirectory() as tmpdir:
            runner = GoogleAdkAnalysisRunner(
                AppConfig(
                    output_dir=Path(tmpdir),
                    adk_backend="google_adk",
                    google_api_key="test-key",
                )
            )
            responses = runner._parse_structured_response(
                """
                {
                  "committee_summary": "Affordability is acceptable but pricing is slightly warm.",
                  "recommendation": "MAYBE",
                  "agents": [
                    {
                      "agent_name": "listing_agent",
                      "status": "success",
                      "summary": "Listing facts were extracted.",
                      "confidence": 0.8,
                      "score": 0.7,
                      "details": {"area_sqm": 82},
                      "warnings": []
                    },
                    {
                      "agent_name": "market_comps_agent",
                      "status": "success",
                      "summary": "Price per square meter is a bit above the fixture market average.",
                      "confidence": 0.7,
                      "score": 0.6,
                      "details": {"fair_value_delta_per_sqm_dkk": 1932},
                      "warnings": []
                    },
                    {
                      "agent_name": "danish_credit_agent",
                      "status": "success",
                      "summary": "Safe price ceiling is above asking.",
                      "confidence": 0.9,
                      "score": 0.8,
                      "details": {"maximum_safe_purchase_price_dkk": 4015789},
                      "warnings": []
                    },
                    {
                      "agent_name": "negotiation_agent",
                      "status": "success",
                      "summary": "Bid below ask and keep a clear cap.",
                      "confidence": 0.6,
                      "score": 0.6,
                      "details": {"maximum_bid_dkk": 3136576},
                      "warnings": []
                    },
                    {
                      "agent_name": "red_team_agent",
                      "status": "partial",
                      "summary": "Older building stock adds some renovation risk.",
                      "confidence": 0.6,
                      "score": 0.5,
                      "details": {"risks": ["renovation exposure"]},
                      "warnings": ["Limited document coverage."]
                    }
                  ]
                }
                """
            )

            self.assertEqual(responses[0].agent_name, "buyer_committee")
            self.assertEqual(responses[0].finding.details["recommendation"], "MAYBE")
            self.assertEqual(responses[1].agent_name, "listing_agent")
            self.assertEqual(len(responses), 6)
            self.assertEqual(responses[-1].status.value, "partial")

    def test_google_adk_runner_falls_back_for_invalid_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            runner = GoogleAdkAnalysisRunner(
                AppConfig(
                    output_dir=Path(tmpdir),
                    adk_backend="google_adk",
                    google_api_key="test-key",
                )
            )
            responses = runner._parse_structured_response("not json")

            self.assertEqual(len(responses), 1)
            self.assertEqual(responses[0].status.value, "partial")
            self.assertIn("raw_response", responses[0].finding.details)
            self.assertIn("Structured ADK parsing failed.", responses[0].finding.warnings)


if __name__ == "__main__":
    unittest.main()
