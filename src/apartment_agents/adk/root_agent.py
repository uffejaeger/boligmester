from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apartment_agents.app.errors import AdkRuntimeUnavailableError

try:
    from google.adk.agents import Agent as GoogleAdkAgent
except ImportError:  # pragma: no cover
    GoogleAdkAgent = None


@dataclass(slots=True)
class AgentNode:
    name: str
    description: str
    instruction: str
    children: list["AgentNode"] = field(default_factory=list)


def build_root_agent_definition() -> AgentNode:
    listing_agent = AgentNode(
        name="listing_agent",
        description="Extracts and normalizes listing facts.",
        instruction=(
            "You analyze Danish apartment listing facts. "
            "Return concise structured findings about address, asking price, area, rooms, "
            "owner costs, age, and notable listing attributes."
        ),
    )
    market_comps_agent = AgentNode(
        name="market_comps_agent",
        description="Assesses pricing against market context.",
        instruction=(
            "You assess whether the apartment looks expensive, fair, or attractive relative to "
            "the local market context provided. Highlight pricing pressure and valuation uncertainty."
        ),
    )
    credit_agent = AgentNode(
        name="danish_credit_agent",
        description="Assesses affordability and credit fit.",
        instruction=(
            "You assess Danish-style affordability using the deterministic finance outputs provided. "
            "Do not invent numbers. Interpret the debt factor, buffer, and safe purchase ceiling."
        ),
    )
    negotiation_agent = AgentNode(
        name="negotiation_agent",
        description="Suggests bidding strategy.",
        instruction=(
            "You propose a negotiation stance using listing and pricing context. "
            "Summarize opening bid posture, walk-away discipline, and bargaining leverage."
        ),
    )
    red_team_agent = AgentNode(
        name="red_team_agent",
        description="Challenges the buy case and identifies risk.",
        instruction=(
            "You argue against the purchase. Surface downside risk, uncertainty, missing diligence, "
            "and reasons the buyer may regret the transaction."
        ),
    )
    return AgentNode(
        name="buyer_committee",
        description="Coordinates the apartment analysis and synthesizes a final recommendation.",
        instruction=(
            "You are the buyer committee. Delegate work to the relevant sub-agents, synthesize their "
            "findings, and return a final structured recommendation."
        ),
        children=[
            listing_agent,
            market_comps_agent,
            credit_agent,
            negotiation_agent,
            red_team_agent,
        ],
    )


def build_google_adk_root_agent(model: str):
    if GoogleAdkAgent is None:
        raise AdkRuntimeUnavailableError(
            "google-adk is not installed, so a live ADK root agent cannot be built."
        )

    tree = build_root_agent_definition()
    sub_agents = [_build_google_adk_agent(model, child) for child in tree.children]
    return GoogleAdkAgent(
        model=model,
        name=tree.name,
        description=tree.description,
        instruction=tree.instruction,
        sub_agents=sub_agents,
    )


def serialize_agent_tree(node: AgentNode) -> dict[str, Any]:
    return {
        "name": node.name,
        "description": node.description,
        "instruction": node.instruction,
        "children": [serialize_agent_tree(child) for child in node.children],
    }


def _build_google_adk_agent(model: str, node: AgentNode):
    if GoogleAdkAgent is None:
        raise AdkRuntimeUnavailableError(
            "google-adk is not installed, so a live ADK agent cannot be built."
        )
    return GoogleAdkAgent(
        model=model,
        name=node.name,
        description=node.description,
        instruction=node.instruction,
        sub_agents=[_build_google_adk_agent(model, child) for child in node.children],
    )
