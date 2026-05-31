import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apartment_agents.models import (
    Address,
    AnalysisReport,
    BuyerProfile,
    HouseholdProfile,
    Listing,
    ListingSearchCriteria,
    ListingSearchResult,
    ListingSearchRun,
    Recommendation,
)
from apartment_agents.storage.workspace import LocalWorkspaceStore


class LocalWorkspaceStoreTest(unittest.TestCase):
    def test_save_and_load_buyer_profile(self) -> None:
        with TemporaryDirectory() as tmpdir:
            store = LocalWorkspaceStore(Path(tmpdir))
            profile = BuyerProfile(
                buyer_id="first_time_buyer",
                household=HouseholdProfile(adults=2, children=1, monthly_childcare_cost_dkk=2500),
                gross_annual_income_dkk=1200000,
                net_monthly_income_dkk=62000,
                savings_dkk=700000,
                existing_debt_dkk=50000,
                monthly_debt_payments_dkk=1500,
                desired_down_payment_dkk=400000,
                employment_notes="Two permanent contracts",
                risk_tolerance="balanced",
            )

            path = store.save_buyer_profile(profile)
            loaded = store.load_buyer_profile("first_time_buyer")

            self.assertTrue(path.exists())
            self.assertEqual(loaded.buyer_id, "first_time_buyer")
            self.assertEqual(loaded.household.children, 1)
            self.assertEqual(store.list_buyer_profiles()[0].buyer_id, "first_time_buyer")

    def test_save_analysis_run_metadata(self) -> None:
        with TemporaryDirectory() as tmpdir:
            store = LocalWorkspaceStore(Path(tmpdir))
            profile = BuyerProfile(
                buyer_id="solo",
                household=HouseholdProfile(adults=1),
                gross_annual_income_dkk=900000,
                net_monthly_income_dkk=45000,
                savings_dkk=500000,
                existing_debt_dkk=0,
            )
            listing = Listing(
                listing_id="listing-1",
                source="boligsiden",
                url="https://www.boligsiden.dk/adresse/test",
                address=Address(street="Testvej 1", postal_code="8000", city="Aarhus C"),
                asking_price_dkk=3200000,
                area_sqm=80,
            )
            report = AnalysisReport(
                report_id="report-1",
                listing=listing,
                buyer_profile=profile,
                market_snapshot=None,
                findings=[],
                recommendation=Recommendation.BUY,
            )

            store.save_analysis_run(report, Path("output/report-1.md"))
            records = store.list_analysis_runs()

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].report_id, "report-1")
            self.assertEqual(records[0].buyer_profile_id, "solo")
            self.assertEqual(records[0].recommendation, "BUY")

    def test_save_listing_search_results(self) -> None:
        with TemporaryDirectory() as tmpdir:
            store = LocalWorkspaceStore(Path(tmpdir))
            search_run = ListingSearchRun(
                search_id="aarhus-c-search",
                criteria=ListingSearchCriteria(city="Aarhus C", max_price_dkk=4000000),
                results=[
                    ListingSearchResult(
                        listing_id="listing-1",
                        source="boligsiden",
                        url="https://www.boligsiden.dk/adresse/test",
                        title="Testvej 1",
                        address=Address(
                            street="Testvej 1",
                            postal_code="8000",
                            city="Aarhus C",
                        ),
                        asking_price_dkk=3500000,
                        area_sqm=70,
                        rooms=3,
                    )
                ],
            )

            path = store.save_listing_search(search_run)
            searches = store.list_listing_searches()

            self.assertTrue(path.exists())
            self.assertEqual(len(searches), 1)
            self.assertEqual(searches[0].criteria.city, "Aarhus C")
            self.assertEqual(searches[0].results[0].title, "Testvej 1")


if __name__ == "__main__":
    unittest.main()
