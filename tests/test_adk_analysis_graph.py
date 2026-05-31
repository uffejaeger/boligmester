import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apartment_agents.adk.analysis_graph import (
    AnalysisNodeKind,
    AnalysisWorkflowRequest,
    ApartmentAnalysisWorkflowGraph,
    build_analysis_workflow_graph_definition,
)
from apartment_agents.adk.runner import AdkAnalysisRunner, MockAdkAnalysisRunner
from apartment_agents.config import AppConfig
from apartment_agents.finance.service import FinanceBoundary
from apartment_agents.storage.fixtures import FixtureStore
from apartment_agents.tools.listings import ListingIngestionService


BOLIGSIDEN_FIXTURE_URL = "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c"


class AnalysisWorkflowGraphDefinitionTest(unittest.TestCase):
    def test_graph_contract_separates_deterministic_and_agent_nodes(self) -> None:
        definition = build_analysis_workflow_graph_definition()

        self.assertEqual(
            [node.name for node in definition.nodes],
            [
                "validate_request",
                "ingest_listing",
                "load_buyer_profile",
                "load_market_snapshot",
                "evaluate_finance",
                "run_adk_agents",
                "assemble_report",
                "write_report",
            ],
        )
        self.assertEqual(definition.node("run_adk_agents").kind, AnalysisNodeKind.AGENT)
        deterministic_nodes = [
            node.name for node in definition.nodes if node.kind == AnalysisNodeKind.DETERMINISTIC
        ]
        self.assertEqual(
            deterministic_nodes,
            [
                "validate_request",
                "ingest_listing",
                "load_buyer_profile",
                "load_market_snapshot",
                "evaluate_finance",
                "assemble_report",
                "write_report",
            ],
        )
        self.assertEqual(
            [(edge.source, edge.target) for edge in definition.edges],
            [
                ("START", "validate_request"),
                ("validate_request", "ingest_listing"),
                ("ingest_listing", "load_buyer_profile"),
                ("load_buyer_profile", "load_market_snapshot"),
                ("load_market_snapshot", "evaluate_finance"),
                ("evaluate_finance", "run_adk_agents"),
                ("run_adk_agents", "assemble_report"),
                ("assemble_report", "write_report"),
            ],
        )


class ApartmentAnalysisWorkflowGraphTest(unittest.TestCase):
    def _graph(
        self,
        tmpdir: str,
        runner: AdkAnalysisRunner | None = None,
    ) -> ApartmentAnalysisWorkflowGraph:
        config = AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
        fixture_store = FixtureStore()
        return ApartmentAnalysisWorkflowGraph(
            config=config,
            fixture_store=fixture_store,
            listing_ingestion=ListingIngestionService(fixture_store, config=config),
            finance_boundary=FinanceBoundary.default(),
            adk_runner=runner or MockAdkAnalysisRunner(),
        )

    def test_graph_runs_analysis_through_adk_runner_boundary(self) -> None:
        class RecordingRunner(AdkAnalysisRunner):
            def __init__(self) -> None:
                self.delegate = MockAdkAnalysisRunner()
                self.context_run_id: str | None = None
                self.finance_debt_factor: float | None = None

            def analyze(self, inputs):
                self.context_run_id = inputs.context.run_id
                self.finance_debt_factor = inputs.finance_result.debt_factor
                return self.delegate.analyze(inputs)

        runner = RecordingRunner()

        with TemporaryDirectory() as tmpdir:
            graph = self._graph(tmpdir, runner=runner)
            result = graph.run(
                AnalysisWorkflowRequest(
                    listing_url=BOLIGSIDEN_FIXTURE_URL,
                    buyer_profile_id="solo_engineer",
                )
            )

        self.assertEqual(result.report.report_id, runner.context_run_id)
        self.assertIsNotNone(runner.finance_debt_factor)
        self.assertEqual(result.report.findings[0].agent_name, "buyer_committee")
        self.assertIn("listing_agent", [finding.agent_name for finding in result.report.findings])

    def test_graph_falls_back_when_agent_node_raises(self) -> None:
        class FailingRunner(AdkAnalysisRunner):
            def analyze(self, inputs):
                raise RuntimeError("runner blew up")

        with TemporaryDirectory() as tmpdir:
            graph = self._graph(tmpdir, runner=FailingRunner())
            result = graph.run(
                AnalysisWorkflowRequest(
                    listing_url=BOLIGSIDEN_FIXTURE_URL,
                    buyer_profile_id="solo_engineer",
                )
            )

            self.assertTrue(result.report_path.exists())

        self.assertEqual(result.report.findings[0].agent_name, "buyer_committee")
        self.assertTrue(result.report.findings[0].details["fallback"])
        self.assertEqual(result.report.recommendation.value, "MAYBE")


if __name__ == "__main__":
    unittest.main()
