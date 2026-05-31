from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Recommendation(str, Enum):
    BUY = "BUY"
    MAYBE = "MAYBE"
    AVOID = "AVOID"


@dataclass(slots=True)
class SourceCitation:
    source_id: str
    label: str
    locator: str
    snippet: str | None = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class ConfidenceScore:
    score: float
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")


@dataclass(slots=True)
class Address:
    street: str
    postal_code: str
    city: str
    municipality: str | None = None
    country_code: str = "DK"


@dataclass(slots=True)
class Listing:
    listing_id: str
    source: str
    url: str
    address: Address
    asking_price_dkk: int
    area_sqm: float
    rooms: float | None = None
    owner_cost_monthly_dkk: int | None = None
    build_year: int | None = None
    floor_label: str | None = None
    balcony: bool | None = None
    elevator: bool | None = None
    energy_label: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    citations: list[SourceCitation] = field(default_factory=list)


@dataclass(slots=True)
class HouseholdProfile:
    adults: int
    children: int = 0
    monthly_childcare_cost_dkk: int = 0
    vehicles: int = 0


@dataclass(slots=True)
class BuyerProfile:
    buyer_id: str
    household: HouseholdProfile
    gross_annual_income_dkk: int
    net_monthly_income_dkk: int
    savings_dkk: int
    existing_debt_dkk: int
    monthly_debt_payments_dkk: int = 0
    desired_down_payment_dkk: int | None = None
    employment_notes: str | None = None
    risk_tolerance: str = "balanced"


@dataclass(slots=True)
class DocumentReference:
    document_id: str
    kind: str
    title: str
    path: str | None = None
    source_url: str | None = None


@dataclass(slots=True)
class DocumentBundle:
    bundle_id: str
    listing_id: str | None = None
    documents: list[DocumentReference] = field(default_factory=list)


@dataclass(slots=True)
class MarketSnapshot:
    snapshot_id: str
    city: str
    neighborhood: str | None = None
    average_price_per_sqm_dkk: int | None = None
    median_days_on_market: int | None = None
    inventory_level: str | None = None
    interest_rate_pct: float | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    citations: list[SourceCitation] = field(default_factory=list)


@dataclass(slots=True)
class AgentFinding:
    agent_name: str
    summary: str
    confidence: ConfidenceScore
    score: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    citations: list[SourceCitation] = field(default_factory=list)


@dataclass(slots=True)
class AnalysisReport:
    report_id: str
    listing: Listing
    buyer_profile: BuyerProfile
    market_snapshot: MarketSnapshot | None
    findings: list[AgentFinding]
    recommendation: Recommendation
    assumptions: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
