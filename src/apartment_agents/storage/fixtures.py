from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apartment_agents.app.errors import (
    BuyerProfileNotFoundError,
    FixtureNotFoundError,
    MarketSnapshotNotFoundError,
    StartupValidationError,
)
from apartment_agents.models import (
    BuyerProfile,
    DocumentBundle,
    DocumentReference,
    HouseholdProfile,
    MarketSnapshot,
    SourceCitation,
)


class FixtureStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("examples")
        self._listing_index_cache: dict[str, dict[str, str]] | None = None
        self._captured_listing_index_cache: dict[str, dict[str, str]] | None = None

    def load_listing_document(self, url: str) -> str:
        index = self._listing_index()
        if url not in index:
            raise FixtureNotFoundError(f"No listing fixture found for URL: {url}")
        path = self.root / "listings" / index[url]["document"]
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise FixtureNotFoundError(f"Listing document fixture missing: {path}") from exc

    def load_captured_listing_document(self, url: str) -> tuple[str, str]:
        index = self._captured_listing_index()
        if url not in index:
            raise FixtureNotFoundError(f"No captured listing found for URL: {url}")
        document_name = index[url]["document"]
        path = self.root / "captured_listings" / document_name
        try:
            return document_name, path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise FixtureNotFoundError(f"Captured listing document missing: {path}") from exc

    def load_buyer_profile(self, profile_id: str) -> BuyerProfile:
        path = self.root / "buyers" / f"{profile_id}.json"
        try:
            payload = self._read_json(path)
        except FileNotFoundError as exc:
            raise BuyerProfileNotFoundError(f"Buyer profile fixture missing: {profile_id}") from exc
        return self._to_buyer_profile(payload)

    def load_market_snapshot(self, city: str) -> MarketSnapshot:
        slug = city.lower().replace(" ", "_")
        path = self.root / "market" / f"{slug}.json"
        try:
            payload = self._read_json(path)
        except FileNotFoundError as exc:
            raise MarketSnapshotNotFoundError(
                f"Market snapshot fixture missing for city: {city}"
            ) from exc
        return self._to_market_snapshot(payload)

    def load_document_bundle(self, bundle_id: str) -> DocumentBundle:
        path = self.root / "documents" / f"{bundle_id}.json"
        payload = self._read_json(path)
        documents = [
            DocumentReference(
                document_id=item["document_id"],
                kind=item["kind"],
                title=item["title"],
                path=item.get("path"),
                source_url=item.get("source_url"),
            )
            for item in payload.get("documents", [])
        ]
        return DocumentBundle(
            bundle_id=payload["bundle_id"],
            listing_id=payload.get("listing_id"),
            documents=documents,
        )

    def list_buyer_profiles(self) -> list[BuyerProfile]:
        profiles = []
        for path in sorted((self.root / "buyers").glob("*.json")):
            profiles.append(self._to_buyer_profile(self._read_json(path)))
        return profiles

    def validate_startup(self) -> None:
        if not self.root.exists():
            raise StartupValidationError(f"Fixture root does not exist: {self.root}")

        listing_index_path = self.root / "listings" / "index.json"
        if not listing_index_path.exists():
            raise StartupValidationError(
                f"Required listing fixture index is missing: {listing_index_path}"
            )

        try:
            listing_index = self._listing_index()
        except FileNotFoundError as exc:
            raise StartupValidationError(
                f"Required listing fixture index is missing: {listing_index_path}"
            ) from exc
        except (KeyError, json.JSONDecodeError) as exc:
            raise StartupValidationError(
                f"Listing fixture index is invalid: {listing_index_path}"
            ) from exc

        if not listing_index:
            raise StartupValidationError("Listing fixture index is empty.")

        for item in listing_index.values():
            document_path = self.root / "listings" / item["document"]
            if not document_path.exists():
                raise StartupValidationError(
                    f"Listing fixture document is missing: {document_path}"
                )

        try:
            buyer_profiles = self.list_buyer_profiles()
        except FileNotFoundError as exc:
            raise StartupValidationError("Buyer profile fixtures are missing.") from exc
        if not buyer_profiles:
            raise StartupValidationError("At least one buyer profile fixture is required.")

    def _listing_index(self) -> dict[str, dict[str, str]]:
        if self._listing_index_cache is None:
            path = self.root / "listings" / "index.json"
            raw_index = self._read_json(path)
            self._listing_index_cache = {item["url"]: item for item in raw_index["items"]}
        return self._listing_index_cache

    def _captured_listing_index(self) -> dict[str, dict[str, str]]:
        if self._captured_listing_index_cache is None:
            path = self.root / "captured_listings" / "index.json"
            try:
                raw_index = self._read_json(path)
            except FileNotFoundError:
                self._captured_listing_index_cache = {}
            else:
                self._captured_listing_index_cache = {
                    item["url"]: item for item in raw_index.get("items", [])
                }
        return self._captured_listing_index_cache

    def _read_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _to_buyer_profile(self, payload: dict[str, Any]) -> BuyerProfile:
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

    def _to_market_snapshot(self, payload: dict[str, Any]) -> MarketSnapshot:
        citations = [
            SourceCitation(
                source_id=citation["source_id"],
                label=citation["label"],
                locator=citation["locator"],
                snippet=citation.get("snippet"),
            )
            for citation in payload.get("citations", [])
        ]
        return MarketSnapshot(
            snapshot_id=payload["snapshot_id"],
            city=payload["city"],
            neighborhood=payload.get("neighborhood"),
            average_price_per_sqm_dkk=payload.get("average_price_per_sqm_dkk"),
            median_days_on_market=payload.get("median_days_on_market"),
            inventory_level=payload.get("inventory_level"),
            interest_rate_pct=payload.get("interest_rate_pct"),
            citations=citations,
        )
