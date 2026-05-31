from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from apartment_agents.app.errors import WorkspacePersistenceError
from apartment_agents.models import (
    Address,
    ApartmentComparison,
    ApartmentComparisonItem,
    AnalysisReport,
    BuyerProfile,
    HouseholdProfile,
    ListingSearchCriteria,
    ListingSearchResult,
    ListingSearchRun,
    SavedApartment,
    WatchlistChange,
    WatchlistRun,
    WatchlistSnapshot,
)


SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class AnalysisRunRecord:
    report_id: str
    listing_url: str
    listing_address: str
    buyer_profile_id: str
    recommendation: str
    report_path: str
    generated_at: str


class LocalWorkspaceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.buyer_profiles_dir = self.root / "buyer_profiles"
        self.analysis_runs_dir = self.root / "analysis_runs"
        self.search_runs_dir = self.root / "search_runs"
        self.saved_apartments_dir = self.root / "saved_apartments"
        self.comparisons_dir = self.root / "comparisons"
        self.watchlist_dir = self.root / "watchlist"
        self.watchlist_snapshots_dir = self.watchlist_dir / "snapshots"
        self.watchlist_runs_dir = self.watchlist_dir / "runs"
        self.ensure_directories()

    def ensure_directories(self) -> None:
        self.buyer_profiles_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_runs_dir.mkdir(parents=True, exist_ok=True)
        self.search_runs_dir.mkdir(parents=True, exist_ok=True)
        self.saved_apartments_dir.mkdir(parents=True, exist_ok=True)
        self.comparisons_dir.mkdir(parents=True, exist_ok=True)
        self.watchlist_snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.watchlist_runs_dir.mkdir(parents=True, exist_ok=True)

    def save_buyer_profile(self, profile: BuyerProfile) -> Path:
        self._validate_safe_id(profile.buyer_id, "Buyer profile id")
        path = self.buyer_profiles_dir / f"{profile.buyer_id}.json"
        self._write_json(path, self._buyer_profile_to_payload(profile))
        return path

    def load_buyer_profile(self, profile_id: str) -> BuyerProfile:
        self._validate_safe_id(profile_id, "Buyer profile id")
        path = self.buyer_profiles_dir / f"{profile_id}.json"
        try:
            payload = self._read_json(path)
        except FileNotFoundError as exc:
            raise WorkspacePersistenceError(
                f"Workspace buyer profile does not exist: {profile_id}"
            ) from exc
        return self._buyer_profile_from_payload(payload)

    def list_buyer_profiles(self) -> list[BuyerProfile]:
        profiles = []
        for path in sorted(self.buyer_profiles_dir.glob("*.json")):
            profiles.append(self._buyer_profile_from_payload(self._read_json(path)))
        return profiles

    def save_analysis_run(self, report: AnalysisReport, report_path: Path) -> Path:
        listing = report.listing
        record = AnalysisRunRecord(
            report_id=report.report_id,
            listing_url=listing.url,
            listing_address=(
                f"{listing.address.street}, {listing.address.postal_code} {listing.address.city}"
            ),
            buyer_profile_id=report.buyer_profile.buyer_id,
            recommendation=report.recommendation.value,
            report_path=str(report_path),
            generated_at=report.generated_at.isoformat(),
        )
        path = self.analysis_runs_dir / f"{report.report_id}.json"
        self._write_json(path, asdict(record))
        return path

    def list_analysis_runs(self) -> list[AnalysisRunRecord]:
        records = []
        for path in sorted(self.analysis_runs_dir.glob("*.json")):
            payload = self._read_json(path)
            records.append(AnalysisRunRecord(**payload))
        return records

    def save_listing_search(self, search_run: ListingSearchRun) -> Path:
        self._validate_safe_id(search_run.search_id, "Search id")
        path = self.search_runs_dir / f"{search_run.search_id}.json"
        self._write_json(path, self._listing_search_to_payload(search_run))
        return path

    def list_listing_searches(self) -> list[ListingSearchRun]:
        searches = []
        for path in sorted(self.search_runs_dir.glob("*.json")):
            searches.append(self._listing_search_from_payload(self._read_json(path)))
        return searches

    def save_saved_apartment(self, apartment: SavedApartment) -> Path:
        self._validate_safe_id(apartment.saved_id, "Saved apartment id")
        path = self.saved_apartments_dir / f"{apartment.saved_id}.json"
        self._write_json(path, self._saved_apartment_to_payload(apartment))
        return path

    def load_saved_apartment(self, saved_id: str) -> SavedApartment:
        self._validate_safe_id(saved_id, "Saved apartment id")
        path = self.saved_apartments_dir / f"{saved_id}.json"
        try:
            payload = self._read_json(path)
        except FileNotFoundError as exc:
            raise WorkspacePersistenceError(
                f"Workspace saved apartment does not exist: {saved_id}"
            ) from exc
        return self._saved_apartment_from_payload(payload)

    def list_saved_apartments(self) -> list[SavedApartment]:
        apartments = []
        for path in sorted(self.saved_apartments_dir.glob("*.json")):
            apartments.append(self._saved_apartment_from_payload(self._read_json(path)))
        return sorted(apartments, key=lambda apartment: apartment.saved_at, reverse=True)

    def save_apartment_comparison(self, comparison: ApartmentComparison) -> Path:
        self._validate_safe_id(comparison.comparison_id, "Comparison id")
        path = self.comparisons_dir / f"{comparison.comparison_id}.json"
        self._write_json(path, self._apartment_comparison_to_payload(comparison))
        return path

    def load_apartment_comparison(self, comparison_id: str) -> ApartmentComparison:
        self._validate_safe_id(comparison_id, "Comparison id")
        path = self.comparisons_dir / f"{comparison_id}.json"
        try:
            payload = self._read_json(path)
        except FileNotFoundError as exc:
            raise WorkspacePersistenceError(
                f"Workspace apartment comparison does not exist: {comparison_id}"
            ) from exc
        return self._apartment_comparison_from_payload(payload)

    def list_apartment_comparisons(self) -> list[ApartmentComparison]:
        comparisons = []
        for path in sorted(self.comparisons_dir.glob("*.json")):
            comparisons.append(self._apartment_comparison_from_payload(self._read_json(path)))
        return sorted(comparisons, key=lambda comparison: comparison.generated_at, reverse=True)

    def save_watchlist_snapshot(self, snapshot: WatchlistSnapshot) -> Path:
        self._validate_safe_id(snapshot.saved_id, "Watchlist saved apartment id")
        path = self.watchlist_snapshots_dir / f"{snapshot.saved_id}.json"
        self._write_json(path, self._watchlist_snapshot_to_payload(snapshot))
        return path

    def list_watchlist_snapshots(self) -> list[WatchlistSnapshot]:
        snapshots = []
        for path in sorted(self.watchlist_snapshots_dir.glob("*.json")):
            snapshots.append(self._watchlist_snapshot_from_payload(self._read_json(path)))
        return sorted(snapshots, key=lambda snapshot: snapshot.observed_at, reverse=True)

    def save_watchlist_run(self, run: WatchlistRun) -> Path:
        self._validate_safe_id(run.run_id, "Watchlist run id")
        path = self.watchlist_runs_dir / f"{run.run_id}.json"
        self._write_json(path, self._watchlist_run_to_payload(run))
        return path

    def list_watchlist_runs(self) -> list[WatchlistRun]:
        runs = []
        for path in sorted(self.watchlist_runs_dir.glob("*.json")):
            runs.append(self._watchlist_run_from_payload(self._read_json(path)))
        return sorted(runs, key=lambda run: run.generated_at, reverse=True)

    def _validate_safe_id(self, value: str, label: str) -> None:
        if not SAFE_ID_PATTERN.fullmatch(value):
            raise WorkspacePersistenceError(
                f"{label} may only contain letters, numbers, underscores, and dashes."
            )

    def _read_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        try:
            temp_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temp_path.replace(path)
        except OSError as exc:
            raise WorkspacePersistenceError(f"Could not write workspace file: {path}") from exc

    def _buyer_profile_to_payload(self, profile: BuyerProfile) -> dict[str, Any]:
        return {
            "buyer_id": profile.buyer_id,
            "household": {
                "adults": profile.household.adults,
                "children": profile.household.children,
                "monthly_childcare_cost_dkk": profile.household.monthly_childcare_cost_dkk,
                "vehicles": profile.household.vehicles,
            },
            "gross_annual_income_dkk": profile.gross_annual_income_dkk,
            "net_monthly_income_dkk": profile.net_monthly_income_dkk,
            "savings_dkk": profile.savings_dkk,
            "existing_debt_dkk": profile.existing_debt_dkk,
            "monthly_debt_payments_dkk": profile.monthly_debt_payments_dkk,
            "desired_down_payment_dkk": profile.desired_down_payment_dkk,
            "employment_notes": profile.employment_notes,
            "risk_tolerance": profile.risk_tolerance,
        }

    def _buyer_profile_from_payload(self, payload: dict[str, Any]) -> BuyerProfile:
        return BuyerProfile(
            buyer_id=payload["buyer_id"],
            household=HouseholdProfile(**payload["household"]),
            gross_annual_income_dkk=payload["gross_annual_income_dkk"],
            net_monthly_income_dkk=payload["net_monthly_income_dkk"],
            savings_dkk=payload["savings_dkk"],
            existing_debt_dkk=payload["existing_debt_dkk"],
            monthly_debt_payments_dkk=payload.get("monthly_debt_payments_dkk", 0),
            desired_down_payment_dkk=payload.get("desired_down_payment_dkk"),
            employment_notes=payload.get("employment_notes"),
            risk_tolerance=payload.get("risk_tolerance", "balanced"),
        )

    def _listing_search_to_payload(self, search_run: ListingSearchRun) -> dict[str, Any]:
        criteria = search_run.criteria
        return {
            "search_id": search_run.search_id,
            "generated_at": search_run.generated_at.isoformat(),
            "criteria": {
                "city": criteria.city,
                "source": criteria.source,
                "property_type": criteria.property_type,
                "query": criteria.query,
                "min_price_dkk": criteria.min_price_dkk,
                "max_price_dkk": criteria.max_price_dkk,
                "min_area_sqm": criteria.min_area_sqm,
                "max_area_sqm": criteria.max_area_sqm,
                "min_rooms": criteria.min_rooms,
                "max_results": criteria.max_results,
                "search_url": criteria.search_url,
            },
            "results": [
                self._listing_search_result_to_payload(result) for result in search_run.results
            ],
        }

    def _listing_search_result_to_payload(self, result: ListingSearchResult) -> dict[str, Any]:
        return {
            "listing_id": result.listing_id,
            "source": result.source,
            "url": result.url,
            "title": result.title,
            "address": {
                "street": result.address.street,
                "postal_code": result.address.postal_code,
                "city": result.address.city,
                "municipality": result.address.municipality,
                "country_code": result.address.country_code,
            },
            "asking_price_dkk": result.asking_price_dkk,
            "area_sqm": result.area_sqm,
            "rooms": result.rooms,
            "owner_cost_monthly_dkk": result.owner_cost_monthly_dkk,
            "raw_payload": result.raw_payload,
        }

    def _listing_search_from_payload(self, payload: dict[str, Any]) -> ListingSearchRun:
        criteria = ListingSearchCriteria(**payload["criteria"])
        return ListingSearchRun(
            search_id=payload["search_id"],
            criteria=criteria,
            results=[
                self._listing_search_result_from_payload(result)
                for result in payload.get("results", [])
            ],
            generated_at=_datetime_from_iso(payload["generated_at"]),
        )

    def _listing_search_result_from_payload(self, payload: dict[str, Any]) -> ListingSearchResult:
        return ListingSearchResult(
            listing_id=payload["listing_id"],
            source=payload["source"],
            url=payload["url"],
            title=payload["title"],
            address=Address(**payload["address"]),
            asking_price_dkk=payload.get("asking_price_dkk"),
            area_sqm=payload.get("area_sqm"),
            rooms=payload.get("rooms"),
            owner_cost_monthly_dkk=payload.get("owner_cost_monthly_dkk"),
            raw_payload=payload.get("raw_payload", {}),
        )

    def _saved_apartment_to_payload(self, apartment: SavedApartment) -> dict[str, Any]:
        return {
            "saved_id": apartment.saved_id,
            "listing_id": apartment.listing_id,
            "source": apartment.source,
            "url": apartment.url,
            "title": apartment.title,
            "address": {
                "street": apartment.address.street,
                "postal_code": apartment.address.postal_code,
                "city": apartment.address.city,
                "municipality": apartment.address.municipality,
                "country_code": apartment.address.country_code,
            },
            "asking_price_dkk": apartment.asking_price_dkk,
            "area_sqm": apartment.area_sqm,
            "rooms": apartment.rooms,
            "owner_cost_monthly_dkk": apartment.owner_cost_monthly_dkk,
            "notes": apartment.notes,
            "tags": apartment.tags,
            "saved_at": apartment.saved_at.isoformat(),
            "raw_payload": apartment.raw_payload,
        }

    def _saved_apartment_from_payload(self, payload: dict[str, Any]) -> SavedApartment:
        return SavedApartment(
            saved_id=payload["saved_id"],
            listing_id=payload["listing_id"],
            source=payload["source"],
            url=payload["url"],
            title=payload["title"],
            address=Address(**payload["address"]),
            asking_price_dkk=payload.get("asking_price_dkk"),
            area_sqm=payload.get("area_sqm"),
            rooms=payload.get("rooms"),
            owner_cost_monthly_dkk=payload.get("owner_cost_monthly_dkk"),
            notes=payload.get("notes"),
            tags=payload.get("tags", []),
            saved_at=_datetime_from_iso(payload["saved_at"]),
            raw_payload=payload.get("raw_payload", {}),
        )

    def _apartment_comparison_to_payload(self, comparison: ApartmentComparison) -> dict[str, Any]:
        return {
            "comparison_id": comparison.comparison_id,
            "buyer_profile_id": comparison.buyer_profile_id,
            "summary": comparison.summary,
            "recommended_saved_id": comparison.recommended_saved_id,
            "generated_at": comparison.generated_at.isoformat(),
            "items": [self._comparison_item_to_payload(item) for item in comparison.items],
        }

    def _comparison_item_to_payload(self, item: ApartmentComparisonItem) -> dict[str, Any]:
        return {
            "saved_id": item.saved_id,
            "listing_id": item.listing_id,
            "title": item.title,
            "address": {
                "street": item.address.street,
                "postal_code": item.address.postal_code,
                "city": item.address.city,
                "municipality": item.address.municipality,
                "country_code": item.address.country_code,
            },
            "url": item.url,
            "asking_price_dkk": item.asking_price_dkk,
            "area_sqm": item.area_sqm,
            "rooms": item.rooms,
            "owner_cost_monthly_dkk": item.owner_cost_monthly_dkk,
            "price_per_sqm_dkk": item.price_per_sqm_dkk,
            "approval_likelihood": item.approval_likelihood,
            "debt_factor": item.debt_factor,
            "monthly_housing_cost_dkk": item.monthly_housing_cost_dkk,
            "safe_purchase_price_gap_dkk": item.safe_purchase_price_gap_dkk,
            "tradeoffs": item.tradeoffs,
            "missing_evidence": item.missing_evidence,
        }

    def _apartment_comparison_from_payload(self, payload: dict[str, Any]) -> ApartmentComparison:
        return ApartmentComparison(
            comparison_id=payload["comparison_id"],
            buyer_profile_id=payload["buyer_profile_id"],
            items=[self._comparison_item_from_payload(item) for item in payload.get("items", [])],
            summary=payload["summary"],
            recommended_saved_id=payload.get("recommended_saved_id"),
            generated_at=_datetime_from_iso(payload["generated_at"]),
        )

    def _comparison_item_from_payload(self, payload: dict[str, Any]) -> ApartmentComparisonItem:
        return ApartmentComparisonItem(
            saved_id=payload["saved_id"],
            listing_id=payload["listing_id"],
            title=payload["title"],
            address=Address(**payload["address"]),
            url=payload["url"],
            asking_price_dkk=payload.get("asking_price_dkk"),
            area_sqm=payload.get("area_sqm"),
            rooms=payload.get("rooms"),
            owner_cost_monthly_dkk=payload.get("owner_cost_monthly_dkk"),
            price_per_sqm_dkk=payload.get("price_per_sqm_dkk"),
            approval_likelihood=payload.get("approval_likelihood"),
            debt_factor=payload.get("debt_factor"),
            monthly_housing_cost_dkk=payload.get("monthly_housing_cost_dkk"),
            safe_purchase_price_gap_dkk=payload.get("safe_purchase_price_gap_dkk"),
            tradeoffs=payload.get("tradeoffs", []),
            missing_evidence=payload.get("missing_evidence", []),
        )

    def _watchlist_snapshot_to_payload(self, snapshot: WatchlistSnapshot) -> dict[str, Any]:
        return {
            "saved_id": snapshot.saved_id,
            "listing_id": snapshot.listing_id,
            "source": snapshot.source,
            "title": snapshot.title,
            "address": {
                "street": snapshot.address.street,
                "postal_code": snapshot.address.postal_code,
                "city": snapshot.address.city,
                "municipality": snapshot.address.municipality,
                "country_code": snapshot.address.country_code,
            },
            "url": snapshot.url,
            "asking_price_dkk": snapshot.asking_price_dkk,
            "area_sqm": snapshot.area_sqm,
            "rooms": snapshot.rooms,
            "owner_cost_monthly_dkk": snapshot.owner_cost_monthly_dkk,
            "price_per_sqm_dkk": snapshot.price_per_sqm_dkk,
            "observed_at": snapshot.observed_at.isoformat(),
        }

    def _watchlist_snapshot_from_payload(self, payload: dict[str, Any]) -> WatchlistSnapshot:
        return WatchlistSnapshot(
            saved_id=payload["saved_id"],
            listing_id=payload["listing_id"],
            source=payload["source"],
            title=payload["title"],
            address=Address(**payload["address"]),
            url=payload["url"],
            asking_price_dkk=payload.get("asking_price_dkk"),
            area_sqm=payload.get("area_sqm"),
            rooms=payload.get("rooms"),
            owner_cost_monthly_dkk=payload.get("owner_cost_monthly_dkk"),
            price_per_sqm_dkk=payload.get("price_per_sqm_dkk"),
            observed_at=_datetime_from_iso(payload["observed_at"]),
        )

    def _watchlist_run_to_payload(self, run: WatchlistRun) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "generated_at": run.generated_at.isoformat(),
            "snapshots": [
                self._watchlist_snapshot_to_payload(snapshot) for snapshot in run.snapshots
            ],
            "changes": [self._watchlist_change_to_payload(change) for change in run.changes],
        }

    def _watchlist_run_from_payload(self, payload: dict[str, Any]) -> WatchlistRun:
        return WatchlistRun(
            run_id=payload["run_id"],
            snapshots=[
                self._watchlist_snapshot_from_payload(snapshot)
                for snapshot in payload.get("snapshots", [])
            ],
            changes=[
                self._watchlist_change_from_payload(change) for change in payload.get("changes", [])
            ],
            generated_at=_datetime_from_iso(payload["generated_at"]),
        )

    def _watchlist_change_to_payload(self, change: WatchlistChange) -> dict[str, Any]:
        return {
            "change_id": change.change_id,
            "saved_id": change.saved_id,
            "field": change.field,
            "old_value": change.old_value,
            "new_value": change.new_value,
            "detected_at": change.detected_at.isoformat(),
        }

    def _watchlist_change_from_payload(self, payload: dict[str, Any]) -> WatchlistChange:
        return WatchlistChange(
            change_id=payload["change_id"],
            saved_id=payload["saved_id"],
            field=payload["field"],
            old_value=payload.get("old_value"),
            new_value=payload.get("new_value"),
            detected_at=_datetime_from_iso(payload["detected_at"]),
        )


def _datetime_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)
