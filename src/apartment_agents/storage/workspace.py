from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from apartment_agents.app.errors import WorkspacePersistenceError
from apartment_agents.models import AnalysisReport, BuyerProfile, HouseholdProfile


PROFILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


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
        self.ensure_directories()

    def ensure_directories(self) -> None:
        self.buyer_profiles_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_runs_dir.mkdir(parents=True, exist_ok=True)

    def save_buyer_profile(self, profile: BuyerProfile) -> Path:
        self._validate_profile_id(profile.buyer_id)
        path = self.buyer_profiles_dir / f"{profile.buyer_id}.json"
        self._write_json(path, self._buyer_profile_to_payload(profile))
        return path

    def load_buyer_profile(self, profile_id: str) -> BuyerProfile:
        self._validate_profile_id(profile_id)
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

    def _validate_profile_id(self, profile_id: str) -> None:
        if not PROFILE_ID_PATTERN.fullmatch(profile_id):
            raise WorkspacePersistenceError(
                "Buyer profile id may only contain letters, numbers, underscores, and dashes."
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
