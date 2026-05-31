from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apartment_agents.adk.runner import (
    AnalysisInputs,
    AdkAnalysisRunner,
    build_runner,
    new_run_id,
    validate_runner_startup,
)
from apartment_agents.agents.committee import (
    build_committee_finding,
    build_fallback_committee_finding,
    fallback_recommendation_from_finance,
    synthesize_committee,
)
from apartment_agents.app.errors import (
    MissingBuyerProfileIdError,
    MissingListingUrlError,
    ReportWriteError,
)
from apartment_agents.agents.contracts import AgentContext
from apartment_agents.config import AppConfig
from apartment_agents.finance.models import FinanceResult
from apartment_agents.finance.service import FinanceBoundary
from apartment_agents.logging import get_logger, log_kv
from apartment_agents.models import AnalysisReport, BuyerProfile
from apartment_agents.reports.markdown import render_report_markdown, report_file_path
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
        self._validate_startup()
        log_kv(logger, 20, "service_initialized", adk_backend=config.adk_backend)

    def analyze(self, request: AnalyzeApartmentRequest) -> AnalyzeApartmentResult:
        request = self._validated_request(request)
        log_kv(
            logger,
            20,
            "analysis_started",
            listing_url=request.listing_url,
            buyer_profile_id=request.buyer_profile_id,
        )
        listing = self.listing_ingestion.parse_listing_url(request.listing_url)
        buyer = self.fixture_store.load_buyer_profile(request.buyer_profile_id)
        market_snapshot = self._load_market_snapshot(listing.address.city)

        finance_result = self.finance_boundary.evaluate_listing_for_buyer(
            listing=listing,
            buyer=buyer,
        )

        context = AgentContext(
            run_id=new_run_id(),
            listing=listing,
            buyer_profile=buyer,
            market_snapshot=market_snapshot,
        )
        try:
            responses = self.adk_runner.analyze(
                AnalysisInputs(context=context, finance_result=finance_result)
            )
        except Exception as exc:
            log_kv(
                logger,
                40,
                "analysis_runner_failed",
                run_id=context.run_id,
                error=str(exc),
            )
            responses = []
        raw_findings = [response.finding for response in responses if response.finding is not None]
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
        findings = [committee_finding, *agent_findings]
        report = AnalysisReport(
            report_id=context.run_id,
            listing=listing,
            buyer_profile=buyer,
            market_snapshot=market_snapshot,
            findings=findings,
            recommendation=recommendation,
            assumptions=[
                *self._listing_assumptions(listing),
                "Market pricing currently uses one city-level fixture snapshot.",
                "Credit policy thresholds are conservative placeholders and must be calibrated.",
                *self.finance_boundary.policy_notes(),
            ],
            unresolved_questions=[
                *self._listing_unresolved_questions(listing),
                "Ejerforening documents are not yet analyzed.",
                "Legal and building due diligence are not yet included.",
            ],
        )
        report_markdown = render_report_markdown(report, finance_result)
        output_path = report_file_path(self.config.output_dir, report.report_id)
        try:
            output_path.write_text(report_markdown, encoding="utf-8")
        except OSError as exc:
            raise ReportWriteError(f"Could not write report to {output_path}") from exc
        log_kv(
            logger,
            20,
            "analysis_completed",
            report_id=report.report_id,
            recommendation=report.recommendation.value,
            report_path=str(output_path),
        )
        return AnalyzeApartmentResult(
            report=report,
            finance_result=finance_result,
            report_markdown=report_markdown,
            report_path=output_path,
        )

    def available_buyer_profiles(self) -> list[BuyerProfile]:
        return self.fixture_store.list_buyer_profiles()

    def _validate_startup(self) -> None:
        self.fixture_store.validate_startup()
        validate_runner_startup(self.config)
        log_kv(logger, 20, "service_startup_validated")

    def _validated_request(self, request: AnalyzeApartmentRequest) -> AnalyzeApartmentRequest:
        listing_url = request.listing_url.strip()
        buyer_profile_id = request.buyer_profile_id.strip()
        if not listing_url:
            raise MissingListingUrlError("Listing URL is required.")
        if not buyer_profile_id:
            raise MissingBuyerProfileIdError("Buyer profile id is required.")
        return AnalyzeApartmentRequest(
            listing_url=listing_url,
            buyer_profile_id=buyer_profile_id,
        )

    def _load_market_snapshot(self, city: str):
        try:
            return self.fixture_store.load_market_snapshot(city)
        except Exception:
            log_kv(logger, 30, "market_snapshot_missing", city=city)
            return None

    def _listing_assumptions(self, listing) -> list[str]:
        ingestion_source = listing.raw_payload.get("ingestion_source")
        source_document = listing.raw_payload.get("source_document")
        assumptions: list[str] = []
        if ingestion_source == "captured_listing":
            assumptions.append(
                "Listing analysis used imported captured HTML rather than a live site fetch."
            )
        if source_document == "live_html_text":
            assumptions.append(
                "Listing analysis used an HTML parsing fallback rather than a structured page payload."
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

    def _listing_unresolved_questions(self, listing) -> list[str]:
        missing_fields = listing.raw_payload.get("missing_fields", [])
        if not missing_fields:
            return []
        return [
            "Listing extraction could not confirm: "
            + ", ".join(str(item) for item in missing_fields)
            + "."
        ]
