from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from uuid import uuid4

from apartment_agents.app.errors import AdkRuntimeUnavailableError
from apartment_agents.adk.root_agent import build_google_adk_root_agent
from apartment_agents.agents.contracts import AgentContext, AgentResponse, AgentStatus
from apartment_agents.config import AppConfig
from apartment_agents.finance.models import FinanceResult
from apartment_agents.logging import get_logger, log_kv
from apartment_agents.models import AgentFinding, AnalysisReport, ConfidenceScore, Recommendation

logger = get_logger("adk")

try:
    from google.adk.runners import InMemorySessionService, Runner
except ImportError:  # pragma: no cover
    InMemorySessionService = None
    Runner = None

try:
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover
    genai_types = None


@dataclass(slots=True)
class AnalysisInputs:
    context: AgentContext
    finance_result: FinanceResult


class AdkAnalysisRunner:
    def analyze(self, inputs: AnalysisInputs) -> list[AgentResponse]:
        raise NotImplementedError


class GoogleAdkAnalysisRunner(AdkAnalysisRunner):
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def analyze(self, inputs: AnalysisInputs) -> list[AgentResponse]:
        if InMemorySessionService is None or Runner is None or genai_types is None:
            raise AdkRuntimeUnavailableError(
                "google-adk is not installed. Install 'google-adk' to use ADK_BACKEND=google_adk."
            )

        os.environ.setdefault("GOOGLE_API_KEY", self.config.google_api_key or "")
        prompt = self._prompt(inputs)
        root_agent = build_google_adk_root_agent(self.config.adk_model)
        log_kv(
            logger,
            20,
            "adk_analysis_started",
            backend=self.config.adk_backend,
            model=self.config.adk_model,
            run_id=inputs.context.run_id,
        )
        session_service = InMemorySessionService()

        async def _run() -> str:
            user_id = "local-user"
            session_id = inputs.context.run_id
            if hasattr(session_service, "create_session"):
                await session_service.create_session(
                    app_name="apartment-buying-agents-dk",
                    user_id=user_id,
                    session_id=session_id,
                )
            runner = Runner(
                agent=root_agent,
                app_name="apartment-buying-agents-dk",
                session_service=session_service,
            )
            content = genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])
            response_text = ""
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
            ):
                if hasattr(event, "is_final_response") and event.is_final_response():
                    response_text = event.content.parts[0].text
            return response_text

        try:
            response_text = asyncio.run(
                asyncio.wait_for(_run(), timeout=self.config.adk_timeout_seconds)
            )
        except TimeoutError:
            log_kv(
                logger,
                30,
                "adk_analysis_timeout",
                backend=self.config.adk_backend,
                run_id=inputs.context.run_id,
                timeout_seconds=self.config.adk_timeout_seconds,
            )
            return [
                self._fallback_response(
                    f"ADK analysis timed out after {self.config.adk_timeout_seconds} seconds."
                )
            ]
        except Exception as exc:
            log_kv(
                logger,
                40,
                "adk_analysis_failed",
                backend=self.config.adk_backend,
                run_id=inputs.context.run_id,
                error=str(exc),
            )
            return [
                self._fallback_response(
                    "ADK analysis failed before producing a complete response.",
                    raw_response=str(exc),
                )
            ]
        responses = self._parse_structured_response(response_text)
        log_kv(
            logger,
            20,
            "adk_analysis_completed",
            backend=self.config.adk_backend,
            run_id=inputs.context.run_id,
            response_count=len(responses),
        )
        return responses

    def _prompt(self, inputs: AnalysisInputs) -> str:
        listing = inputs.context.listing
        buyer = inputs.context.buyer_profile
        finance = inputs.finance_result
        assert listing is not None
        assert buyer is not None
        return (
            f"Listing URL: {listing.url}\n"
            f"Address: {listing.address.street}, {listing.address.postal_code} {listing.address.city}\n"
            f"Asking price DKK: {listing.asking_price_dkk}\n"
            f"Area sqm: {listing.area_sqm}\n"
            f"Rooms: {listing.rooms}\n"
            f"Buyer net monthly income DKK: {buyer.net_monthly_income_dkk}\n"
            f"Buyer savings DKK: {buyer.savings_dkk}\n"
            f"Debt factor: {finance.debt_factor}\n"
            f"Safe maximum purchase price DKK: {finance.maximum_safe_purchase_price_dkk}\n"
            "Use your sub-agents to reason about listing facts, market pricing, affordability, "
            "negotiation stance, and red-team risk.\n"
            "Return valid JSON only with this shape:\n"
            "{\n"
            '  "committee_summary": "string",\n'
            '  "recommendation": "BUY|MAYBE|AVOID",\n'
            '  "agents": [\n'
            "    {\n"
            '      "agent_name": "listing_agent|market_comps_agent|danish_credit_agent|negotiation_agent|red_team_agent",\n'
            '      "status": "success|partial|failed",\n'
            '      "summary": "string",\n'
            '      "confidence": 0.0,\n'
            '      "score": 0.0,\n'
            '      "details": {},\n'
            '      "warnings": ["string"]\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Every agent listed above must be present exactly once. No markdown. No prose outside JSON."
        )

    def _parse_structured_response(self, response_text: str) -> list[AgentResponse]:
        if not response_text.strip():
            return [self._fallback_response("ADK returned an empty final response.")]

        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError:
            return [
                self._fallback_response(
                    "ADK did not return valid JSON. Raw response captured for review.",
                    raw_response=response_text,
                )
            ]

        committee_summary = str(payload.get("committee_summary", "ADK committee summary missing."))
        recommendation = str(payload.get("recommendation", "MAYBE"))
        responses = [
            AgentResponse(
                agent_name="buyer_committee",
                status=AgentStatus.SUCCESS,
                finding=AgentFinding(
                    agent_name="buyer_committee",
                    summary=committee_summary,
                    confidence=ConfidenceScore(
                        score=0.65,
                        rationale="Parsed from structured ADK committee response.",
                    ),
                    details={"recommendation": recommendation},
                ),
            )
        ]

        for agent_payload in payload.get("agents", []):
            agent_name = str(agent_payload.get("agent_name", "unknown_agent"))
            status = self._status_from_string(str(agent_payload.get("status", "partial")))
            score = self._float_or_default(agent_payload.get("score"), 0.5)
            confidence = self._float_or_default(agent_payload.get("confidence"), 0.5)
            summary = str(agent_payload.get("summary", "No summary provided."))
            details = agent_payload.get("details", {})
            warnings = [str(item) for item in agent_payload.get("warnings", [])]
            responses.append(
                AgentResponse(
                    agent_name=agent_name,
                    status=status,
                    finding=AgentFinding(
                        agent_name=agent_name,
                        summary=summary,
                        confidence=ConfidenceScore(
                            score=confidence,
                            rationale="Parsed from structured ADK agent response.",
                        ),
                        score=score,
                        details=details if isinstance(details, dict) else {"raw_details": details},
                        warnings=warnings,
                    ),
                )
            )
        return responses

    def _status_from_string(self, value: str) -> AgentStatus:
        normalized = value.lower()
        if normalized == "success":
            return AgentStatus.SUCCESS
        if normalized == "failed":
            return AgentStatus.FAILED
        return AgentStatus.PARTIAL

    def _float_or_default(self, value: object, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _fallback_response(self, summary: str, raw_response: str | None = None) -> AgentResponse:
        details = {"raw_response": raw_response} if raw_response else {}
        return AgentResponse(
            agent_name="buyer_committee",
            status=AgentStatus.PARTIAL,
            finding=AgentFinding(
                agent_name="buyer_committee",
                summary=summary,
                confidence=ConfidenceScore(
                    score=0.2,
                    rationale="Fallback response due to invalid or missing structured ADK output.",
                ),
                details=details,
                warnings=["Structured ADK parsing failed."],
            ),
            warnings=["Structured ADK parsing failed."],
        )


class MockAdkAnalysisRunner(AdkAnalysisRunner):
    def analyze(self, inputs: AnalysisInputs) -> list[AgentResponse]:
        log_kv(
            logger,
            20,
            "mock_adk_analysis_started",
            run_id=inputs.context.run_id,
        )
        listing = inputs.context.listing
        buyer = inputs.context.buyer_profile
        market = inputs.context.market_snapshot
        finance = inputs.finance_result
        assert listing is not None
        assert buyer is not None

        price_per_sqm = int(listing.asking_price_dkk / listing.area_sqm)
        market_ppsqm = market.average_price_per_sqm_dkk if market else None
        fair_value_delta = 0
        if market_ppsqm:
            fair_value_delta = price_per_sqm - market_ppsqm

        red_team_warnings = []
        if listing.build_year and listing.build_year < 1970:
            red_team_warnings.append("Older building stock may imply renovation exposure.")
        if listing.owner_cost_monthly_dkk and listing.owner_cost_monthly_dkk > 4500:
            red_team_warnings.append("High monthly owner costs reduce affordability buffer.")

        negotiation_cap = min(
            finance.maximum_safe_purchase_price_dkk,
            listing.asking_price_dkk - max(fair_value_delta * int(listing.area_sqm), 0),
        )

        responses = [
            AgentResponse(
                agent_name="listing_agent",
                status=AgentStatus.SUCCESS,
                finding=self._finding(
                    agent_name="listing_agent",
                    summary=(
                        f"Parsed {listing.address.street}, {listing.address.postal_code} "
                        f"{listing.address.city} at {listing.asking_price_dkk:,} DKK."
                    ),
                    score=0.75,
                    details={
                        "price_per_sqm_dkk": price_per_sqm,
                        "rooms": listing.rooms,
                        "area_sqm": listing.area_sqm,
                    },
                    citations_count=len(listing.citations),
                    warnings=[],
                    citations=listing.citations,
                ),
            ),
            AgentResponse(
                agent_name="market_comps_agent",
                status=AgentStatus.SUCCESS,
                finding=self._finding(
                    agent_name="market_comps_agent",
                    summary=(
                        f"Estimated price per sqm is {price_per_sqm:,} DKK versus local "
                        f"fixture market average {market_ppsqm:,} DKK."
                        if market_ppsqm
                        else "No market fixture available; comps estimate is incomplete."
                    ),
                    score=0.65 if market_ppsqm else 0.35,
                    details={
                        "asking_price_per_sqm_dkk": price_per_sqm,
                        "market_average_price_per_sqm_dkk": market_ppsqm,
                        "fair_value_delta_per_sqm_dkk": fair_value_delta,
                    },
                    citations_count=len(market.citations) if market else 0,
                    warnings=[] if market_ppsqm else ["Market pricing is based on incomplete inputs."],
                    citations=market.citations if market else [],
                ),
            ),
            AgentResponse(
                agent_name="danish_credit_agent",
                status=AgentStatus.SUCCESS,
                finding=self._finding(
                    agent_name="danish_credit_agent",
                    summary=(
                        f"Approval likelihood is {finance.approval_likelihood}. "
                        f"Safe purchase ceiling is {finance.maximum_safe_purchase_price_dkk:,} DKK."
                    ),
                    score=0.8,
                    details={
                        "debt_factor": finance.debt_factor,
                        "monthly_housing_cost_dkk": finance.housing_cost_monthly_dkk,
                        "monthly_buffer_after_housing_dkk": finance.disposable_income_after_housing_dkk,
                        "maximum_purchase_price_dkk": finance.maximum_purchase_price_dkk,
                        "maximum_safe_purchase_price_dkk": finance.maximum_safe_purchase_price_dkk,
                    },
                    citations_count=0,
                    warnings=[] if finance.approval_likelihood != "low" else ["Affordability is weak."],
                    citations=[],
                ),
            ),
            AgentResponse(
                agent_name="negotiation_agent",
                status=AgentStatus.SUCCESS,
                finding=self._finding(
                    agent_name="negotiation_agent",
                    summary=(
                        f"Suggested opening bid is {int(negotiation_cap * 0.96):,} DKK "
                        f"with a walk-away cap near {negotiation_cap:,} DKK."
                    ),
                    score=0.6,
                    details={
                        "opening_bid_dkk": int(negotiation_cap * 0.96),
                        "maximum_bid_dkk": int(negotiation_cap),
                    },
                    citations_count=0,
                    warnings=["Negotiation logic is fixture-backed and should be replaced with live comps."],
                    citations=[],
                ),
            ),
            AgentResponse(
                agent_name="red_team_agent",
                status=AgentStatus.SUCCESS,
                finding=self._finding(
                    agent_name="red_team_agent",
                    summary="Key downside risks have been enumerated for review.",
                    score=0.55,
                    details={"risks": red_team_warnings or ["No obvious fixture-derived red flags found."]},
                    citations_count=0,
                    warnings=red_team_warnings,
                    citations=[],
                ),
            ),
        ]
        log_kv(
            logger,
            20,
            "mock_adk_analysis_completed",
            run_id=inputs.context.run_id,
            response_count=len(responses),
        )
        return responses

    def synthesize_recommendation(self, report: AnalysisReport, finance_result: FinanceResult) -> Recommendation:
        if finance_result.approval_likelihood == "low":
            return Recommendation.AVOID
        if finance_result.maximum_safe_purchase_price_dkk < report.listing.asking_price_dkk:
            return Recommendation.MAYBE
        return Recommendation.BUY

    def _finding(
        self,
        agent_name: str,
        summary: str,
        score: float,
        details: dict[str, object],
        citations_count: int,
        warnings: list[str],
        citations: list[object],
    ) -> AgentFinding:
        return AgentFinding(
            agent_name=agent_name,
            summary=summary,
            confidence=ConfidenceScore(
                score=score,
                rationale=f"Mocked ADK path with {citations_count} direct citations.",
            ),
            score=score,
            details=details,
            warnings=warnings,
            citations=citations,
        )


def new_run_id() -> str:
    return str(uuid4())


def validate_runner_startup(config: AppConfig) -> None:
    if config.adk_backend == "google_adk":
        if InMemorySessionService is None or Runner is None or genai_types is None:
            raise AdkRuntimeUnavailableError(
                "google-adk is not installed. Install 'google-adk' to use ADK_BACKEND=google_adk."
            )
        build_google_adk_root_agent(config.adk_model)
    log_kv(logger, 20, "runner_startup_validated", adk_backend=config.adk_backend)


def build_runner(config: AppConfig) -> AdkAnalysisRunner:
    if config.adk_backend == "google_adk":
        log_kv(logger, 20, "runner_selected", adk_backend=config.adk_backend)
        return GoogleAdkAnalysisRunner(config)
    log_kv(logger, 20, "runner_selected", adk_backend="mock")
    return MockAdkAnalysisRunner()
