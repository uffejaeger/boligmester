from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from apartment_agents.models import (
    AgentFinding,
    BuyerProfile,
    DocumentBundle,
    Listing,
    MarketSnapshot,
)


class AgentStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(slots=True)
class AgentContext:
    run_id: str
    listing: Listing | None = None
    buyer_profile: BuyerProfile | None = None
    document_bundle: DocumentBundle | None = None
    market_snapshot: MarketSnapshot | None = None
    shared_state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentRequest:
    agent_name: str
    context: AgentContext
    objectives: list[str] = field(default_factory=list)
    required_outputs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentResponse:
    agent_name: str
    status: AgentStatus
    finding: AgentFinding | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentAggregationPolicy:
    minimum_successful_agents: int = 1
    allow_partial_results: bool = True
    recommendation_priority: list[str] = field(default_factory=lambda: ["AVOID", "MAYBE", "BUY"])
    require_citations: bool = True


class Agent(Protocol):
    name: str

    def analyze(self, request: AgentRequest) -> AgentResponse: ...


class DataTool(Protocol):
    name: str

    def fetch(self, query: dict[str, Any]) -> dict[str, Any]: ...
