from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from apartment_agents.adk.runner import AnalysisInputs, AdkAnalysisRunner, new_run_id
from apartment_agents.agents.committee import (
    build_committee_finding,
    build_fallback_committee_finding,
    fallback_recommendation_from_finance,
    synthesize_committee,
)
from apartment_agents.agents.contracts import AgentContext, AgentResponse
from apartment_agents.app.errors import (
    MissingBuyerProfileIdError,
    MissingListingUrlError,
    ReportWriteError,
)
from apartment_agents.config import AppConfig
from apartment_agents.finance.models import FinanceResult
from apartment_agents.finance.service import FinanceBoundary
from apartment_agents.logging import get_logger, log_kv
from apartment_agents.models import (
    AnalysisReport,
    BuyerProfile,
    Listing,
    MarketSnapshot,
)
from apartment_agents.reports.markdown import render_report_markdown, report_file_path
from apartment_agents.storage.fixtures import FixtureStore
from apartment_agents.tools.listings import ListingIngestionService


logger = get_logger("analysis_graph")
GRAPH_START = "START"


class AnalysisNodeKind(str, Enum):
    DETERMINISTIC = "deterministic"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class AnalysisGraphNode:
    name: str
    kind: AnalysisNodeKind
    description: str


@dataclass(frozen=True, slots=True)
class AnalysisGraphEdge:
    source: str
    target: str


@dataclass(frozen=True, slots=True)
class AnalysisWorkflowGraphDefinition:
    nodes: tuple[AnalysisGraphNode, ...]
    edges: tuple[AnalysisGraphEdge, ...]

    def node(self, name: str) -> AnalysisGraphNode:
        for node in self.nodes:
            if node.name == name:
                return node
        raise KeyError(name)


@dataclass(slots=True)
class AnalysisWorkflowRequest:
    listing_url: str
    buyer_profile_id: str


@dataclass(slots=True)
class AnalysisWorkflowResult:
    report: AnalysisReport
    finance_result: FinanceResult
    report_markdown: str
    report_path: Path


@dataclass(slots=True)
class AnalysisWorkflowState:
    request: AnalysisWorkflowRequest
    run_id: str = field(default_factory=new_run_id)
    listing: Listing | None = None
    buyer: BuyerProfile | None = None
    market_snapshot: MarketSnapshot | None = None
    finance_result: FinanceResult | None = None
    agent_responses: list[AgentResponse] = field(default_factory=list)
    report: AnalysisReport | None = None
    report_markdown: str | None = None
    report_path: Path | None = None


def build_analysis_workflow_graph_definition() -> AnalysisWorkflowGraphDefinition:
    nodes = (
        AnalysisGraphNode(
            name="validate_request",
            kind=AnalysisNodeKind.DETERMINISTIC,
            description="Normalize and validate the requested listing URL and buyer profile id.",
        ),
        AnalysisGraphNode(
            name="ingest_listing",
            kind=AnalysisNodeKind.DETERMINISTIC,
            description="Load or fetch the listing and parse it into a structured Listing.",
        ),
        AnalysisGraphNode(
            name="load_buyer_profile",
            kind=AnalysisNodeKind.DETERMINISTIC,
            description="Load the configured buyer profile fixture.",
        ),
        AnalysisGraphNode(
            name="load_market_snapshot",
            kind=AnalysisNodeKind.DETERMINISTIC,
            description="Load city-level market context when a fixture is available.",
        ),
        AnalysisGraphNode(
            name="evaluate_finance",
            kind=AnalysisNodeKind.DETERMINISTIC,
            description="Run deterministic affordability calculations outside agent reasoning.",
        ),
        AnalysisGraphNode(
            name="run_adk_agents",
            kind=AnalysisNodeKind.AGENT,
            description="Invoke the configured ADK analysis runner with structured inputs.",
        ),
        AnalysisGraphNode(
            name="assemble_report",
            kind=AnalysisNodeKind.DETERMINISTIC,
            description=(
                "Synthesize findings, assumptions, unresolved questions, and recommendation."
            ),
        ),
        AnalysisGraphNode(
            name="write_report",
            kind=AnalysisNodeKind.DETERMINISTIC,
            description="Render and persist the Markdown report.",
        ),
    )
    return AnalysisWorkflowGraphDefinition(
        nodes=nodes,
        edges=(
            AnalysisGraphEdge(source=GRAPH_START, target=nodes[0].name),
            *(
                AnalysisGraphEdge(source=nodes[index].name, target=nodes[index + 1].name)
                for index in range(len(nodes) - 1)
            ),
        ),
    )


class ApartmentAnalysisWorkflowGraph:
    def __init__(
        self,
        config: AppConfig,
        fixture_store: FixtureStore,
        listing_ingestion: ListingIngestionService,
        finance_boundary: FinanceBoundary,
        adk_runner: AdkAnalysisRunner,
        definition: AnalysisWorkflowGraphDefinition | None = None,
    ) -> None:
        self.config = config
        self.fixture_store = fixture_store
        self.listing_ingestion = listing_ingestion
        self.finance_boundary = finance_boundary
        self.adk_runner = adk_runner
        self.definition = definition or build_analysis_workflow_graph_definition()
        self._node_handlers: dict[str, Callable[[AnalysisWorkflowState], None]] = {
            "validate_request": self._validate_request,
            "ingest_listing": self._ingest_listing,
            "load_buyer_profile": self._load_buyer_profile,
            "load_market_snapshot": self._load_market_snapshot,
            "evaluate_finance": self._evaluate_finance,
            "run_adk_agents": self._run_adk_agents,
            "assemble_report": self._assemble_report,
            "write_report": self._write_report,
        }

    def run(self, request: AnalysisWorkflowRequest) -> AnalysisWorkflowResult:
        state = AnalysisWorkflowState(request=request)
        for node in self.definition.nodes:
            self._run_node(node, state)

        if state.report is None or state.finance_result is None:
            raise RuntimeError("Analysis graph completed without report and finance result.")
        if state.report_markdown is None or state.report_path is None:
            raise RuntimeError("Analysis graph completed without persisted report output.")

        return AnalysisWorkflowResult(
            report=state.report,
            finance_result=state.finance_result,
            report_markdown=state.report_markdown,
            report_path=state.report_path,
        )

    def _run_node(self, node: AnalysisGraphNode, state: AnalysisWorkflowState) -> None:
        log_kv(
            logger,
            20,
            "analysis_graph_node_started",
            node=node.name,
            kind=node.kind.value,
            run_id=state.run_id,
        )
        try:
            self._node_handlers[node.name](state)
        except Exception as exc:
            log_kv(
                logger,
                40,
                "analysis_graph_node_failed",
                node=node.name,
                kind=node.kind.value,
                run_id=state.run_id,
                error=str(exc),
            )
            raise
        log_kv(
            logger,
            20,
            "analysis_graph_node_completed",
            node=node.name,
            kind=node.kind.value,
            run_id=state.run_id,
        )

    def _validate_request(self, state: AnalysisWorkflowState) -> None:
        listing_url = state.request.listing_url.strip()
        buyer_profile_id = state.request.buyer_profile_id.strip()
        if not listing_url:
            raise MissingListingUrlError("Listing URL is required.")
        if not buyer_profile_id:
            raise MissingBuyerProfileIdError("Buyer profile id is required.")
        state.request = AnalysisWorkflowRequest(
            listing_url=listing_url,
            buyer_profile_id=buyer_profile_id,
        )

    def _ingest_listing(self, state: AnalysisWorkflowState) -> None:
        state.listing = self.listing_ingestion.parse_listing_url(state.request.listing_url)

    def _load_buyer_profile(self, state: AnalysisWorkflowState) -> None:
        state.buyer = self.fixture_store.load_buyer_profile(state.request.buyer_profile_id)

    def _load_market_snapshot(self, state: AnalysisWorkflowState) -> None:
        listing = self._require_listing(state)
        try:
            state.market_snapshot = self.fixture_store.load_market_snapshot(listing.address.city)
        except Exception:
            log_kv(logger, 30, "market_snapshot_missing", city=listing.address.city)
            state.market_snapshot = None

    def _evaluate_finance(self, state: AnalysisWorkflowState) -> None:
        state.finance_result = self.finance_boundary.evaluate_listing_for_buyer(
            listing=self._require_listing(state),
            buyer=self._require_buyer(state),
        )

    def _run_adk_agents(self, state: AnalysisWorkflowState) -> None:
        context = AgentContext(
            run_id=state.run_id,
            listing=self._require_listing(state),
            buyer_profile=self._require_buyer(state),
            market_snapshot=state.market_snapshot,
        )
        try:
            state.agent_responses = self.adk_runner.analyze(
                AnalysisInputs(
                    context=context,
                    finance_result=self._require_finance_result(state),
                )
            )
        except Exception as exc:
            log_kv(
                logger,
                40,
                "analysis_runner_failed",
                run_id=state.run_id,
                error=str(exc),
            )
            state.agent_responses = []

    def _assemble_report(self, state: AnalysisWorkflowState) -> None:
        listing = self._require_listing(state)
        buyer = self._require_buyer(state)
        finance_result = self._require_finance_result(state)
        raw_findings = [
            response.finding for response in state.agent_responses if response.finding is not None
        ]
        committee_seed = next(
            (finding for finding in raw_findings if finding.agent_name == "buyer_committee"),
            None,
        )
        agent_findings = [
            finding for finding in raw_findings if finding.agent_name != "buyer_committee"
        ]

        if agent_findings:
            synthesis = synthesize_committee(
                findings=agent_findings,
                finance_result=finance_result,
                listing_price_dkk=listing.asking_price_dkk,
            )
            committee_finding = build_committee_finding(
                synthesis=synthesis,
                existing_summary=committee_seed.summary if committee_seed else None,
            )
            recommendation = synthesis.recommendation
        else:
            fallback_reason = (
                committee_seed.summary
                if committee_seed is not None
                else "Agent execution did not produce usable specialist findings."
            )
            committee_finding = build_fallback_committee_finding(
                finance_result=finance_result,
                listing_price_dkk=listing.asking_price_dkk,
                reason=fallback_reason,
            )
            recommendation = fallback_recommendation_from_finance(
                finance_result=finance_result,
                listing_price_dkk=listing.asking_price_dkk,
            )

        state.report = AnalysisReport(
            report_id=state.run_id,
            listing=listing,
            buyer_profile=buyer,
            market_snapshot=state.market_snapshot,
            findings=[committee_finding, *agent_findings],
            recommendation=recommendation,
            assumptions=[
                *self._listing_assumptions(listing),
                "Market pricing currently uses one city-level fixture snapshot.",
                "Credit policy is a deterministic Danish screening heuristic, not a lender decision.",
                *self.finance_boundary.policy_notes(),
            ],
            unresolved_questions=[
                *self._listing_unresolved_questions(listing),
                "Ejerforening documents are not yet analyzed.",
                "Legal and building due diligence are not yet included.",
            ],
        )

    def _write_report(self, state: AnalysisWorkflowState) -> None:
        report = self._require_report(state)
        state.report_markdown = render_report_markdown(
            report,
            self._require_finance_result(state),
        )
        state.report_path = report_file_path(self.config.output_dir, report.report_id)
        try:
            state.report_path.write_text(state.report_markdown, encoding="utf-8")
        except OSError as exc:
            raise ReportWriteError(f"Could not write report to {state.report_path}") from exc

    def _listing_assumptions(self, listing: Listing) -> list[str]:
        ingestion_source = listing.raw_payload.get("ingestion_source")
        source_document = listing.raw_payload.get("source_document")
        assumptions: list[str] = []
        if ingestion_source == "captured_listing":
            assumptions.append(
                "Listing analysis used imported captured HTML rather than a live site fetch."
            )
        if source_document == "live_html_text":
            assumptions.append(
                "Listing analysis used an HTML parsing fallback rather than a structured page "
                "payload."
            )
            coverage = listing.raw_payload.get("field_coverage_ratio")
            if coverage is not None:
                assumptions.append(f"Listing extraction field coverage was {coverage}.")
            assumptions.extend(str(item) for item in listing.raw_payload.get("warnings", []))
            return assumptions
        if assumptions:
            return assumptions
        return [
            "Listing analysis currently uses fixture-backed ingestion rather than live scraping."
        ]

    def _listing_unresolved_questions(self, listing: Listing) -> list[str]:
        missing_fields = listing.raw_payload.get("missing_fields", [])
        if not missing_fields:
            return []
        return [
            "Listing extraction could not confirm: "
            + ", ".join(str(item) for item in missing_fields)
            + "."
        ]

    def _require_listing(self, state: AnalysisWorkflowState) -> Listing:
        if state.listing is None:
            raise RuntimeError("Analysis graph requires listing before this node.")
        return state.listing

    def _require_buyer(self, state: AnalysisWorkflowState) -> BuyerProfile:
        if state.buyer is None:
            raise RuntimeError("Analysis graph requires buyer profile before this node.")
        return state.buyer

    def _require_finance_result(self, state: AnalysisWorkflowState) -> FinanceResult:
        if state.finance_result is None:
            raise RuntimeError("Analysis graph requires finance result before this node.")
        return state.finance_result

    def _require_report(self, state: AnalysisWorkflowState) -> AnalysisReport:
        if state.report is None:
            raise RuntimeError("Analysis graph requires assembled report before this node.")
        return state.report
