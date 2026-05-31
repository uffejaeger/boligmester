import unittest

from apartment_agents.finance.service import FinanceBoundary
from apartment_agents.models import Address, BuyerProfile, HouseholdProfile, Listing


class FinanceBoundaryTest(unittest.TestCase):
    def test_evaluate_listing_for_buyer_returns_finance_result(self) -> None:
        boundary = FinanceBoundary.default()
        listing = Listing(
            listing_id="listing-1",
            source="fixture",
            url="https://example.test/listing-1",
            address=Address(street="Testvej 1", postal_code="8000", city="Aarhus C"),
            asking_price_dkk=3295000,
            area_sqm=82.0,
            owner_cost_monthly_dkk=3650,
        )
        buyer = BuyerProfile(
            buyer_id="buyer-1",
            household=HouseholdProfile(adults=1),
            gross_annual_income_dkk=960000,
            net_monthly_income_dkk=47000,
            savings_dkk=550000,
            existing_debt_dkk=25000,
            monthly_debt_payments_dkk=900,
        )

        result = boundary.evaluate_listing_for_buyer(listing=listing, buyer=buyer)

        self.assertEqual(result.approval_likelihood, "high")
        self.assertGreater(result.maximum_safe_purchase_price_dkk, 3000000)

    def test_policy_notes_describe_boundary(self) -> None:
        boundary = FinanceBoundary.default()

        notes = boundary.policy_notes()

        self.assertGreaterEqual(len(notes), 2)
        self.assertIn("deterministic", notes[0].lower())


if __name__ == "__main__":
    unittest.main()
