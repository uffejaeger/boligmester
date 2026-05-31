import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

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

    def test_google_adk_runner_records_delegation_evidence_from_events(self) -> None:
        with TemporaryDirectory() as tmpdir:
            runner = GoogleAdkAnalysisRunner(
                AppConfig(
                    output_dir=Path(tmpdir),
                    adk_backend="google_adk",
                    google_api_key="test-key",
                )
            )
            runner.last_event_trace = [
                runner._trace_event(
                    _FakeEvent(
                        author="buyer_committee",
                        final_response=False,
                        transfer_to_agent="listing_agent",
                    )
                ),
                runner._trace_event(
                    _FakeEvent(
                        author="danish_credit_agent",
                        final_response=True,
                        text="Credit response",
                    )
                ),
            ]

            evidence = runner.delegation_evidence()

            self.assertEqual(
                evidence["delegated_agents"],
                ["listing_agent", "danish_credit_agent"],
            )
            self.assertIn("market_comps_agent", evidence["missing_agents"])
            self.assertEqual(evidence["event_count"], 2)
            self.assertEqual(evidence["events"][0]["transfer_to_agent"], "listing_agent")

    def test_google_adk_runner_handles_final_event_without_text(self) -> None:
        with TemporaryDirectory() as tmpdir:
            runner = GoogleAdkAnalysisRunner(
                AppConfig(
                    output_dir=Path(tmpdir),
                    adk_backend="google_adk",
                    google_api_key="test-key",
                )
            )

            trace = runner._trace_event(_FakeEvent(author="buyer_committee", final_response=True))

            self.assertTrue(trace.final_response)
            self.assertIsNone(trace.text)


class _FakeEvent:
    def __init__(
        self,
        author: str,
        final_response: bool,
        text: str | None = None,
        transfer_to_agent: str | None = None,
    ) -> None:
        self.id = "event-1"
        self.author = author
        self.branch = "branch-1"
        self.node_info = SimpleNamespace(path=f"/{author}")
        self.content = (
            SimpleNamespace(parts=[SimpleNamespace(text=text)]) if text is not None else None
        )
        self.actions = SimpleNamespace(transfer_to_agent=transfer_to_agent)
        self.error_code = None
        self.error_message = None
        self._final_response = final_response

    def is_final_response(self) -> bool:
        return self._final_response


if __name__ == "__main__":
    unittest.main()
