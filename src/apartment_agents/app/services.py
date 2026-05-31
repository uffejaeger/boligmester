from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
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
from apartment_agents.models import (
    Address,
    ApartmentComparison,
    ApartmentComparisonItem,
    AnalysisReport,
    BuyerProfile,
    Listing,
    ListingSearchCriteria,
    ListingSearchResult,
    ListingSearchRun,
    SavedApartment,
    WatchlistChange,
    WatchlistRun,
    WatchlistSnapshot,
)
from apartment_agents.reports.comparison import (
    comparison_file_path,
    render_comparison_markdown,
)
from apartment_agents.storage.fixtures import FixtureStore
from apartment_agents.storage.workspace import LocalWorkspaceStore
from apartment_agents.tools.listings import ListingIngestionService
from apartment_agents.tools.search import ListingSearchService

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


@dataclass(slots=True)
class SearchApartmentsRequest:
    city: str
    source: str = "boligsiden"
    property_type: str = "ejerlejlighed"
    query: str | None = None
    min_price_dkk: int | None = None
    max_price_dkk: int | None = None
    min_area_sqm: float | None = None
    max_area_sqm: float | None = None
    min_rooms: float | None = None
    max_results: int = 20
    search_url: str | None = None


@dataclass(slots=True)
class SearchApartmentsResult:
    search_run: ListingSearchRun
    workspace_path: Path


@dataclass(slots=True)
class SaveApartmentRequest:
    listing_id: str
    source: str
    url: str
    title: str
    address: Address
    asking_price_dkk: int | None = None
    area_sqm: float | None = None
    rooms: float | None = None
    owner_cost_monthly_dkk: int | None = None
    notes: str | None = None
    tags: list[str] | None = None
    raw_payload: dict[str, object] | None = None


@dataclass(slots=True)
class SaveApartmentResult:
    saved_apartment: SavedApartment
    workspace_path: Path


@dataclass(slots=True)
class CompareApartmentsRequest:
    buyer_profile_id: str
    saved_apartment_ids: list[str] | None = None


@dataclass(slots=True)
class CompareApartmentsResult:
    comparison: ApartmentComparison
    comparison_markdown: str
    comparison_path: Path
    workspace_path: Path


@dataclass(slots=True)
class RefreshWatchlistRequest:
    saved_apartment_ids: list[str] | None = None


@dataclass(slots=True)
class RefreshWatchlistResult:
    run: WatchlistRun
    workspace_path: Path


class AnalyzeApartmentService:
    def __init__(
        self,
        config: AppConfig,
        fixture_store: FixtureStore | None = None,
        listing_ingestion: ListingIngestionService | None = None,
        listing_search: ListingSearchService | None = None,
        finance_boundary: FinanceBoundary | None = None,
        adk_runner: AdkAnalysisRunner | None = None,
        workspace_store: LocalWorkspaceStore | None = None,
    ) -> None:
        self.config = config
        assert config.workspace_dir is not None
        self.workspace_store = workspace_store or LocalWorkspaceStore(config.workspace_dir)
        self.fixture_store = fixture_store or FixtureStore()
        self.fixture_store.prepend_buyer_profile_root(self.workspace_store.buyer_profiles_dir)
        self.listing_ingestion = listing_ingestion or ListingIngestionService(
            self.fixture_store,
            config=config,
        )
        self.listing_search = listing_search or ListingSearchService(
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
        self.workspace_store.save_analysis_run(graph_result.report, graph_result.report_path)
        log_kv(
            logger,
            20,
            "analysis_run_persisted",
            report_id=graph_result.report.report_id,
            workspace_dir=str(self.workspace_store.root),
        )
        return AnalyzeApartmentResult(
            report=graph_result.report,
            finance_result=graph_result.finance_result,
            report_markdown=graph_result.report_markdown,
            report_path=graph_result.report_path,
        )

    def available_buyer_profiles(self) -> list[BuyerProfile]:
        return self.fixture_store.list_buyer_profiles()

    def search_apartments(self, request: SearchApartmentsRequest) -> SearchApartmentsResult:
        log_kv(
            logger,
            20,
            "apartment_search_started",
            city=request.city,
            source=request.source,
            property_type=request.property_type,
        )
        search_run = self.listing_search.search(
            ListingSearchCriteria(
                city=request.city,
                source=request.source,
                property_type=request.property_type,
                query=request.query,
                min_price_dkk=request.min_price_dkk,
                max_price_dkk=request.max_price_dkk,
                min_area_sqm=request.min_area_sqm,
                max_area_sqm=request.max_area_sqm,
                min_rooms=request.min_rooms,
                max_results=request.max_results,
                search_url=request.search_url,
            )
        )
        path = self.workspace_store.save_listing_search(search_run)
        log_kv(
            logger,
            20,
            "apartment_search_persisted",
            city=search_run.criteria.city,
            result_count=len(search_run.results),
            search_id=search_run.search_id,
            path=str(path),
        )
        return SearchApartmentsResult(search_run=search_run, workspace_path=path)

    def available_listing_searches(self) -> list[ListingSearchRun]:
        return self.workspace_store.list_listing_searches()

    def save_apartment(self, request: SaveApartmentRequest) -> SaveApartmentResult:
        apartment = SavedApartment(
            saved_id=_saved_apartment_id(request.source, request.listing_id),
            listing_id=request.listing_id,
            source=request.source,
            url=request.url,
            title=request.title,
            address=request.address,
            asking_price_dkk=request.asking_price_dkk,
            area_sqm=request.area_sqm,
            rooms=request.rooms,
            owner_cost_monthly_dkk=request.owner_cost_monthly_dkk,
            notes=request.notes,
            tags=request.tags or [],
            raw_payload=request.raw_payload or {},
        )
        path = self.workspace_store.save_saved_apartment(apartment)
        log_kv(
            logger,
            20,
            "apartment_saved",
            saved_id=apartment.saved_id,
            listing_url=apartment.url,
            path=str(path),
        )
        return SaveApartmentResult(saved_apartment=apartment, workspace_path=path)

    def save_search_result_apartment(
        self, result: ListingSearchResult, notes: str | None = None
    ) -> SaveApartmentResult:
        return self.save_apartment(
            SaveApartmentRequest(
                listing_id=result.listing_id,
                source=result.source,
                url=result.url,
                title=result.title,
                address=result.address,
                asking_price_dkk=result.asking_price_dkk,
                area_sqm=result.area_sqm,
                rooms=result.rooms,
                owner_cost_monthly_dkk=result.owner_cost_monthly_dkk,
                notes=notes,
                tags=["search"],
                raw_payload=result.raw_payload,
            )
        )

    def available_saved_apartments(self) -> list[SavedApartment]:
        return self.workspace_store.list_saved_apartments()

    def compare_apartments(self, request: CompareApartmentsRequest) -> CompareApartmentsResult:
        buyer_profile_id = request.buyer_profile_id.strip()
        if not buyer_profile_id:
            raise ValueError("buyer profile id is required")
        buyer_profile = self.fixture_store.load_buyer_profile(buyer_profile_id)
        apartments = self._comparison_apartments(request.saved_apartment_ids)
        if len(apartments) < 2:
            raise ValueError("at least two saved apartments are required for comparison")

        log_kv(
            logger,
            20,
            "apartment_comparison_started",
            buyer_profile_id=buyer_profile.buyer_id,
            apartment_count=len(apartments),
        )
        items = [
            self._comparison_item_for_apartment(apartment, buyer_profile)
            for apartment in apartments
        ]
        _apply_comparison_tradeoffs(items)
        recommended = _recommended_comparison_item(items)
        generated_at = datetime.now(timezone.utc)
        comparison = ApartmentComparison(
            comparison_id=_comparison_id(buyer_profile.buyer_id, apartments, generated_at),
            buyer_profile_id=buyer_profile.buyer_id,
            items=items,
            summary=_comparison_summary(items, recommended, buyer_profile),
            recommended_saved_id=recommended.saved_id if recommended is not None else None,
            generated_at=generated_at,
        )
        comparison_markdown = render_comparison_markdown(comparison)
        comparison_path = comparison_file_path(self.config.output_dir, comparison.comparison_id)
        comparison_path.write_text(comparison_markdown, encoding="utf-8")
        workspace_path = self.workspace_store.save_apartment_comparison(comparison)
        log_kv(
            logger,
            20,
            "apartment_comparison_completed",
            buyer_profile_id=buyer_profile.buyer_id,
            comparison_id=comparison.comparison_id,
            recommended_saved_id=comparison.recommended_saved_id or "",
            path=str(comparison_path),
        )
        return CompareApartmentsResult(
            comparison=comparison,
            comparison_markdown=comparison_markdown,
            comparison_path=comparison_path,
            workspace_path=workspace_path,
        )

    def available_apartment_comparisons(self) -> list[ApartmentComparison]:
        return self.workspace_store.list_apartment_comparisons()

    def refresh_watchlist(self, request: RefreshWatchlistRequest) -> RefreshWatchlistResult:
        apartments = self._watchlist_apartments(request.saved_apartment_ids)
        if not apartments:
            raise ValueError("at least one saved apartment is required for watchlist tracking")

        observed_at = datetime.now(timezone.utc)
        previous_snapshots = {
            snapshot.saved_id: snapshot
            for snapshot in self.workspace_store.list_watchlist_snapshots()
        }
        snapshots = [
            _watchlist_snapshot_from_saved_apartment(apartment, observed_at)
            for apartment in apartments
        ]
        changes: list[WatchlistChange] = []
        for snapshot in snapshots:
            previous = previous_snapshots.get(snapshot.saved_id)
            if previous is not None:
                changes.extend(_watchlist_changes(previous, snapshot, observed_at))
            self.workspace_store.save_watchlist_snapshot(snapshot)

        run = WatchlistRun(
            run_id=_watchlist_run_id(snapshots, observed_at),
            snapshots=snapshots,
            changes=changes,
            generated_at=observed_at,
        )
        workspace_path = self.workspace_store.save_watchlist_run(run)
        log_kv(
            logger,
            20,
            "watchlist_refreshed",
            run_id=run.run_id,
            snapshot_count=len(run.snapshots),
            change_count=len(run.changes),
            path=str(workspace_path),
        )
        return RefreshWatchlistResult(run=run, workspace_path=workspace_path)

    def available_watchlist_runs(self) -> list[WatchlistRun]:
        return self.workspace_store.list_watchlist_runs()

    def available_watchlist_snapshots(self) -> list[WatchlistSnapshot]:
        return self.workspace_store.list_watchlist_snapshots()

    def save_buyer_profile(self, profile: BuyerProfile) -> Path:
        path = self.workspace_store.save_buyer_profile(profile)
        log_kv(
            logger,
            20,
            "buyer_profile_persisted",
            buyer_profile_id=profile.buyer_id,
            path=str(path),
        )
        return path

    def _validate_startup(self) -> None:
        self.fixture_store.validate_startup()
        validate_runner_startup(self.config)
        log_kv(logger, 20, "service_startup_validated")

    def _comparison_apartments(self, saved_ids: list[str] | None) -> list[SavedApartment]:
        if saved_ids is None:
            return self.available_saved_apartments()
        apartments = []
        seen_ids = set()
        for saved_id in saved_ids:
            if saved_id in seen_ids:
                continue
            apartments.append(self.workspace_store.load_saved_apartment(saved_id))
            seen_ids.add(saved_id)
        return apartments

    def _comparison_item_for_apartment(
        self, apartment: SavedApartment, buyer_profile: BuyerProfile
    ) -> ApartmentComparisonItem:
        missing_evidence = _missing_evidence_for_apartment(apartment)
        finance_result = None
        if apartment.asking_price_dkk is None or apartment.asking_price_dkk <= 0:
            missing_evidence.append("asking_price_dkk is required for finance screening")
        else:
            listing = _listing_from_saved_apartment(apartment)
            finance_result = self.finance_boundary.evaluate_listing_for_buyer(
                listing=listing,
                buyer=buyer_profile,
            )

        return ApartmentComparisonItem(
            saved_id=apartment.saved_id,
            listing_id=apartment.listing_id,
            title=apartment.title,
            address=apartment.address,
            url=apartment.url,
            asking_price_dkk=apartment.asking_price_dkk,
            area_sqm=apartment.area_sqm,
            rooms=apartment.rooms,
            owner_cost_monthly_dkk=apartment.owner_cost_monthly_dkk,
            price_per_sqm_dkk=apartment.price_per_sqm_dkk,
            approval_likelihood=(
                finance_result.approval_likelihood if finance_result is not None else None
            ),
            debt_factor=finance_result.debt_factor if finance_result is not None else None,
            monthly_housing_cost_dkk=(
                finance_result.housing_cost_monthly_dkk if finance_result is not None else None
            ),
            safe_purchase_price_gap_dkk=(
                finance_result.maximum_safe_purchase_price_dkk - apartment.asking_price_dkk
                if finance_result is not None and apartment.asking_price_dkk is not None
                else None
            ),
            missing_evidence=missing_evidence,
        )

    def _watchlist_apartments(self, saved_ids: list[str] | None) -> list[SavedApartment]:
        if saved_ids is None:
            return self.available_saved_apartments()
        apartments = []
        seen_ids = set()
        for saved_id in saved_ids:
            if saved_id in seen_ids:
                continue
            apartments.append(self.workspace_store.load_saved_apartment(saved_id))
            seen_ids.add(saved_id)
        return apartments


def _saved_apartment_id(source: str, listing_id: str) -> str:
    value = f"{source}-{listing_id}"
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")


def _comparison_id(
    buyer_profile_id: str, apartments: list[SavedApartment], generated_at: datetime
) -> str:
    timestamp = generated_at.strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha1(
        "|".join(
            [
                buyer_profile_id,
                generated_at.isoformat(),
                *[item.saved_id for item in apartments],
            ]
        ).encode("utf-8")
    ).hexdigest()[:8]
    return f"comparison-{timestamp}-{digest}"


def _listing_from_saved_apartment(apartment: SavedApartment) -> Listing:
    return Listing(
        listing_id=apartment.listing_id,
        source=apartment.source,
        url=apartment.url,
        address=apartment.address,
        asking_price_dkk=apartment.asking_price_dkk or 0,
        area_sqm=apartment.area_sqm or 0,
        rooms=apartment.rooms,
        owner_cost_monthly_dkk=apartment.owner_cost_monthly_dkk,
        raw_payload=apartment.raw_payload,
    )


def _missing_evidence_for_apartment(apartment: SavedApartment) -> list[str]:
    missing = []
    if apartment.asking_price_dkk is None:
        missing.append("asking_price_dkk is missing")
    if apartment.area_sqm is None:
        missing.append("area_sqm is missing")
    if apartment.rooms is None:
        missing.append("rooms is missing")
    if apartment.owner_cost_monthly_dkk is None:
        missing.append("owner_cost_monthly_dkk is missing")
    return missing


def _apply_comparison_tradeoffs(items: list[ApartmentComparisonItem]) -> None:
    prices = [item.asking_price_dkk for item in items if item.asking_price_dkk is not None]
    areas = [item.area_sqm for item in items if item.area_sqm is not None]
    price_per_sqm = [item.price_per_sqm_dkk for item in items if item.price_per_sqm_dkk is not None]
    owner_costs = [
        item.owner_cost_monthly_dkk for item in items if item.owner_cost_monthly_dkk is not None
    ]

    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None
    max_area = max(areas) if areas else None
    min_price_per_sqm = min(price_per_sqm) if price_per_sqm else None
    min_owner_cost = min(owner_costs) if owner_costs else None

    for item in items:
        tradeoffs = []
        if item.asking_price_dkk is not None and item.asking_price_dkk == min_price:
            tradeoffs.append("Lowest asking price among compared apartments.")
        if item.asking_price_dkk is not None and item.asking_price_dkk == max_price:
            tradeoffs.append("Highest asking price among compared apartments.")
        if item.area_sqm is not None and item.area_sqm == max_area:
            tradeoffs.append("Largest area among compared apartments.")
        if item.price_per_sqm_dkk is not None and item.price_per_sqm_dkk == min_price_per_sqm:
            tradeoffs.append("Lowest price per m2 among compared apartments.")
        if (
            item.owner_cost_monthly_dkk is not None
            and item.owner_cost_monthly_dkk == min_owner_cost
        ):
            tradeoffs.append("Lowest owner cost among compared apartments.")
        if item.approval_likelihood is not None:
            tradeoffs.append(
                f"Deterministic finance screening gives {item.approval_likelihood} approval likelihood."
            )
        if item.safe_purchase_price_gap_dkk is not None:
            if item.safe_purchase_price_gap_dkk >= 0:
                tradeoffs.append("Asking price is within deterministic safe purchase price.")
            else:
                tradeoffs.append("Asking price is above deterministic safe purchase price.")
        if item.missing_evidence:
            tradeoffs.append("Requires follow-up on missing structured evidence.")
        item.tradeoffs = tradeoffs


def _recommended_comparison_item(
    items: list[ApartmentComparisonItem],
) -> ApartmentComparisonItem | None:
    if not items:
        return None
    return max(items, key=_comparison_rank)


def _comparison_rank(item: ApartmentComparisonItem) -> tuple[int, int, int, int, int]:
    approval_rank = {"high": 3, "medium": 2, "low": 1}.get(item.approval_likelihood or "", 0)
    safe_gap = item.safe_purchase_price_gap_dkk
    price_per_sqm = item.price_per_sqm_dkk
    return (
        approval_rank,
        safe_gap if safe_gap is not None else -(10**12),
        -(price_per_sqm if price_per_sqm is not None else 10**12),
        int(item.area_sqm or 0),
        -len(item.missing_evidence),
    )


def _comparison_summary(
    items: list[ApartmentComparisonItem],
    recommended: ApartmentComparisonItem | None,
    buyer_profile: BuyerProfile,
) -> str:
    if recommended is None:
        return f"Compared 0 saved apartments for {buyer_profile.buyer_id}."
    return (
        f"Compared {len(items)} saved apartments for {buyer_profile.buyer_id}. "
        f"{recommended.title} currently ranks strongest from available structured fields "
        "because the comparison favors finance approval, safe purchase price gap, "
        "lower price per m2, usable area, and fewer missing evidence fields."
    )


def _watchlist_run_id(snapshots: list[WatchlistSnapshot], generated_at: datetime) -> str:
    timestamp = generated_at.strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha1(
        "|".join([generated_at.isoformat(), *[snapshot.saved_id for snapshot in snapshots]]).encode(
            "utf-8"
        )
    ).hexdigest()[:8]
    return f"watchlist-{timestamp}-{digest}"


def _watchlist_snapshot_from_saved_apartment(
    apartment: SavedApartment, observed_at: datetime
) -> WatchlistSnapshot:
    return WatchlistSnapshot(
        saved_id=apartment.saved_id,
        listing_id=apartment.listing_id,
        source=apartment.source,
        title=apartment.title,
        address=apartment.address,
        url=apartment.url,
        asking_price_dkk=apartment.asking_price_dkk,
        area_sqm=apartment.area_sqm,
        rooms=apartment.rooms,
        owner_cost_monthly_dkk=apartment.owner_cost_monthly_dkk,
        price_per_sqm_dkk=apartment.price_per_sqm_dkk,
        observed_at=observed_at,
    )


def _watchlist_changes(
    previous: WatchlistSnapshot,
    current: WatchlistSnapshot,
    detected_at: datetime,
) -> list[WatchlistChange]:
    tracked_fields = [
        "title",
        "url",
        "asking_price_dkk",
        "area_sqm",
        "rooms",
        "owner_cost_monthly_dkk",
        "price_per_sqm_dkk",
    ]
    changes = []
    for field in tracked_fields:
        old_value = getattr(previous, field)
        new_value = getattr(current, field)
        if old_value != new_value:
            changes.append(
                WatchlistChange(
                    change_id=_watchlist_change_id(current.saved_id, field, detected_at),
                    saved_id=current.saved_id,
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                    detected_at=detected_at,
                )
            )
    return changes


def _watchlist_change_id(saved_id: str, field: str, detected_at: datetime) -> str:
    digest = hashlib.sha1(
        "|".join([saved_id, field, detected_at.isoformat()]).encode("utf-8")
    ).hexdigest()[:8]
    return f"change-{digest}"
