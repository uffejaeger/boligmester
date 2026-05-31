from __future__ import annotations

from dataclasses import dataclass

from apartment_agents.finance.models import FinanceResult
from apartment_agents.models import AgentFinding, ConfidenceScore, Recommendation


AGENT_WEIGHTS = {
    "listing_agent": 0.15,
    "market_comps_agent": 0.25,
    "danish_credit_agent": 0.35,
    "negotiation_agent": 0.10,
    "red_team_agent": 0.15,
}


@dataclass(slots=True)
class CommitteeSynthesis:
    recommendation: Recommendation
    aggregate_score: float
    normalized_scores: dict[str, float]
    disagreements: list[str]
    warnings: list[str]
    summary: str


def synthesize_committee(
    findings: list[AgentFinding],
    finance_result: FinanceResult,
    listing_price_dkk: int,
) -> CommitteeSynthesis:
    normalized_scores = {
        finding.agent_name: _normalize_finding_score(finding)
        for finding in findings
        if finding.agent_name in AGENT_WEIGHTS
    }

    aggregate_score = 0.0
    total_weight = 0.0
    for agent_name, weight in AGENT_WEIGHTS.items():
        if agent_name not in normalized_scores:
            continue
        value = normalized_scores[agent_name]
        effective_value = 1.0 - value if agent_name == "red_team_agent" else value
        aggregate_score += effective_value * weight
        total_weight += weight
    aggregate_score = aggregate_score / total_weight if total_weight else 0.0

    disagreements = _find_disagreements(normalized_scores, finance_result, listing_price_dkk)
    recommendation = _recommendation_from_scores(
        aggregate_score=aggregate_score,
        normalized_scores=normalized_scores,
        disagreements=disagreements,
        finance_result=finance_result,
        listing_price_dkk=listing_price_dkk,
    )
    warnings = list(disagreements)
    if "red_team_agent" not in normalized_scores:
        warnings.append("Red-team risk input is missing from the committee score.")
    if "market_comps_agent" not in normalized_scores:
        warnings.append("Market comps input is missing from the committee score.")

    summary = (
        f"Committee aggregate score is {aggregate_score:.2f}. "
        f"Finance approval is {finance_result.approval_likelihood}; "
        f"safe ceiling is {finance_result.maximum_safe_purchase_price_dkk:,} DKK."
    )
    return CommitteeSynthesis(
        recommendation=recommendation,
        aggregate_score=round(aggregate_score, 2),
        normalized_scores={k: round(v, 2) for k, v in normalized_scores.items()},
        disagreements=disagreements,
        warnings=warnings,
        summary=summary,
    )


def build_committee_finding(
    synthesis: CommitteeSynthesis,
    existing_summary: str | None = None,
) -> AgentFinding:
    return AgentFinding(
        agent_name="buyer_committee",
        summary=existing_summary or synthesis.summary,
        confidence=ConfidenceScore(
            score=max(0.2, min(0.95, synthesis.aggregate_score)),
            rationale="Weighted normalization across the MVP agent set.",
        ),
        score=synthesis.aggregate_score,
        details={
            "recommendation": synthesis.recommendation.value,
            "normalized_scores": synthesis.normalized_scores,
            "disagreements": synthesis.disagreements,
        },
        warnings=synthesis.warnings,
    )


def build_fallback_committee_finding(
    finance_result: FinanceResult,
    listing_price_dkk: int,
    reason: str,
) -> AgentFinding:
    recommendation = fallback_recommendation_from_finance(
        finance_result=finance_result,
        listing_price_dkk=listing_price_dkk,
    )
    return AgentFinding(
        agent_name="buyer_committee",
        summary=reason,
        confidence=ConfidenceScore(
            score=0.25,
            rationale="Fallback committee path due to missing or failed agent execution.",
        ),
        score=0.25,
        details={
            "recommendation": recommendation.value,
            "fallback": True,
        },
        warnings=[
            "Agent execution did not complete normally.",
            "Recommendation is based on finance-led fallback logic with limited diligence coverage.",
        ],
    )


def _normalize_finding_score(finding: AgentFinding) -> float:
    base_score = finding.score if finding.score is not None else finding.confidence.score
    penalty = min(0.25, len(finding.warnings) * 0.05)
    return max(0.0, min(1.0, base_score - penalty))


def _find_disagreements(
    normalized_scores: dict[str, float],
    finance_result: FinanceResult,
    listing_price_dkk: int,
) -> list[str]:
    disagreements: list[str] = []
    if (
        finance_result.approval_likelihood == "high"
        and normalized_scores.get("market_comps_agent", 0.5) < 0.45
    ):
        disagreements.append(
            "Credit looks acceptable, but market pricing still appears weak."
        )
    if (
        finance_result.maximum_safe_purchase_price_dkk >= listing_price_dkk
        and normalized_scores.get("red_team_agent", 0.0) > 0.7
    ):
        disagreements.append(
            "Affordability clears the bar, but downside risk remains elevated."
        )
    if (
        normalized_scores.get("negotiation_agent", 0.5) < 0.45
        and normalized_scores.get("market_comps_agent", 0.5) > 0.65
    ):
        disagreements.append(
            "Valuation looks acceptable, but negotiating leverage appears limited."
        )
    return disagreements


def _recommendation_from_scores(
    aggregate_score: float,
    normalized_scores: dict[str, float],
    disagreements: list[str],
    finance_result: FinanceResult,
    listing_price_dkk: int,
) -> Recommendation:
    if finance_result.approval_likelihood == "low":
        return Recommendation.AVOID
    if finance_result.maximum_safe_purchase_price_dkk < listing_price_dkk * 0.9:
        return Recommendation.AVOID
    if finance_result.maximum_safe_purchase_price_dkk < listing_price_dkk:
        return Recommendation.MAYBE
    if normalized_scores.get("red_team_agent", 0.0) > 0.8:
        return Recommendation.MAYBE
    if disagreements and aggregate_score < 0.65:
        return Recommendation.MAYBE
    if aggregate_score >= 0.68:
        return Recommendation.BUY
    if aggregate_score >= 0.45:
        return Recommendation.MAYBE
    return Recommendation.AVOID


def fallback_recommendation_from_finance(
    finance_result: FinanceResult,
    listing_price_dkk: int,
) -> Recommendation:
    if finance_result.approval_likelihood == "low":
        return Recommendation.AVOID
    if finance_result.maximum_safe_purchase_price_dkk < listing_price_dkk:
        return Recommendation.MAYBE
    return Recommendation.MAYBE
