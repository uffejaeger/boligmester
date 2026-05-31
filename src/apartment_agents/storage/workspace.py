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
    AnalysisReport,
    BuyerProfile,
    HouseholdProfile,
    ListingSearchCriteria,
    ListingSearchResult,
    ListingSearchRun,
    SavedApartment,
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
        self.ensure_directories()

    def ensure_directories(self) -> None:
        self.buyer_profiles_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_runs_dir.mkdir(parents=True, exist_ok=True)
        self.search_runs_dir.mkdir(parents=True, exist_ok=True)
        self.saved_apartments_dir.mkdir(parents=True, exist_ok=True)

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


def _datetime_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)
