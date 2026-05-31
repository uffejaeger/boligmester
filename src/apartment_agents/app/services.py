from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apartment_agents.adk.analysis_graph import (
    AnalysisWorkflowRequest,
    ApartmentAnalysisWorkflowGraph,
)
from apartment_agents.adk.runner import (
    AdkAnalysisRunner,
    build_runner,
    validate_runner_startup,
)
from apartment_agents.config import AppConfig
from apartment_agents.finance.models import FinanceResult
from apartment_agents.finance.service import FinanceBoundary
from apartment_agents.logging import get_logger, log_kv
from apartment_agents.models import AnalysisReport, BuyerProfile
from apartment_agents.storage.fixtures import FixtureStore
from apartment_agents.tools.listings import ListingIngestionService

logger = get_logger("services")


@dataclass(slots=True)
class AnalyzeApartmentRequest:
    listing_url: str
    buyer_profile_id: str


@dataclass(slots=True)
class AnalyzeApartmentResult:
    report: AnalysisReport
    finance_result: FinanceResult
    report_markdown: str
    report_path: Path


class AnalyzeApartmentService:
    def __init__(
        self,
        config: AppConfig,
        fixture_store: FixtureStore | None = None,
        listing_ingestion: ListingIngestionService | None = None,
        finance_boundary: FinanceBoundary | None = None,
        adk_runner: AdkAnalysisRunner | None = None,
    ) -> None:
        self.config = config
        self.fixture_store = fixture_store or FixtureStore()
        self.listing_ingestion = listing_ingestion or ListingIngestionService(
            self.fixture_store,
            config=config,
        )
        self.finance_boundary = finance_boundary or FinanceBoundary.default()
        self.adk_runner = adk_runner or build_runner(config)
        self.analysis_graph = ApartmentAnalysisWorkflowGraph(
            config=config,
            fixture_store=self.fixture_store,
            listing_ingestion=self.listing_ingestion,
            finance_boundary=self.finance_boundary,
            adk_runner=self.adk_runner,
        )
        self._validate_startup()
        log_kv(logger, 20, "service_initialized", adk_backend=config.adk_backend)

    def analyze(self, request: AnalyzeApartmentRequest) -> AnalyzeApartmentResult:
        log_kv(
            logger,
            20,
            "analysis_started",
            listing_url=request.listing_url,
            buyer_profile_id=request.buyer_profile_id,
        )
        graph_result = self.analysis_graph.run(
            AnalysisWorkflowRequest(
                listing_url=request.listing_url,
                buyer_profile_id=request.buyer_profile_id,
            )
        )
        log_kv(
            logger,
            20,
            "analysis_completed",
            report_id=graph_result.report.report_id,
            recommendation=graph_result.report.recommendation.value,
            report_path=str(graph_result.report_path),
        )
        return AnalyzeApartmentResult(
            report=graph_result.report,
            finance_result=graph_result.finance_result,
            report_markdown=graph_result.report_markdown,
            report_path=graph_result.report_path,
        )

    def available_buyer_profiles(self) -> list[BuyerProfile]:
        return self.fixture_store.list_buyer_profiles()

    def _validate_startup(self) -> None:
        self.fixture_store.validate_startup()
        validate_runner_startup(self.config)
        log_kv(logger, 20, "service_startup_validated")
