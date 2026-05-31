from __future__ import annotations

from dataclasses import dataclass

from apartment_agents.finance.engine import AffordabilityPolicy, DanishCreditEngine
from apartment_agents.finance.models import FinanceInputs, FinanceResult
from apartment_agents.logging import get_logger, log_kv
from apartment_agents.models import BuyerProfile, Listing


logger = get_logger("finance")


@dataclass(slots=True)
class FinanceBoundary:
    """Service-facing finance boundary.

    The rest of the application should interact with finance through this boundary
    instead of reaching into calculation internals directly.
    """

    engine: DanishCreditEngine

    @classmethod
    def default(cls) -> "FinanceBoundary":
        return cls(engine=DanishCreditEngine(policy=AffordabilityPolicy()))

    def evaluate_listing_for_buyer(
        self,
        listing: Listing,
        buyer: BuyerProfile,
    ) -> FinanceResult:
        inputs = FinanceInputs(
                gross_annual_income_dkk=buyer.gross_annual_income_dkk,
                net_monthly_income_dkk=buyer.net_monthly_income_dkk,
                savings_dkk=buyer.savings_dkk,
                existing_debt_dkk=buyer.existing_debt_dkk,
                monthly_debt_payments_dkk=buyer.monthly_debt_payments_dkk,
                asking_price_dkk=listing.asking_price_dkk,
                owner_cost_monthly_dkk=listing.owner_cost_monthly_dkk or 0,
                adults=buyer.household.adults,
                children=buyer.household.children,
                monthly_childcare_cost_dkk=buyer.household.monthly_childcare_cost_dkk,
        )
        log_kv(
            logger,
            20,
            "finance_evaluation_started",
            listing_id=listing.listing_id,
            buyer_id=buyer.buyer_id,
            asking_price_dkk=listing.asking_price_dkk,
        )
        result = self.engine.evaluate(inputs)
        log_kv(
            logger,
            20,
            "finance_evaluation_completed",
            listing_id=listing.listing_id,
            buyer_id=buyer.buyer_id,
            approval_likelihood=result.approval_likelihood,
            maximum_safe_purchase_price_dkk=result.maximum_safe_purchase_price_dkk,
        )
        return result

    def policy_notes(self) -> list[str]:
        return [
            "Finance boundary is deterministic and isolated from agent reasoning.",
            "Only structured inputs and outputs cross the finance package boundary.",
        ]
