import tempfile
import unittest
from pathlib import Path

from apartment_agents.adk.runner import MockAdkAnalysisRunner
from apartment_agents.app.errors import (
    MissingBuyerProfileIdError,
    MissingListingUrlError,
    StartupValidationError,
)
from apartment_agents.app.services import (
    AnalyzeApartmentRequest,
    AnalyzeApartmentService,
    SearchApartmentsRequest,
)
from apartment_agents.adk.runner import AdkAnalysisRunner
from apartment_agents.config import AppConfig
from apartment_agents.models import BuyerProfile, HouseholdProfile
from apartment_agents.storage.fixtures import FixtureStore
from apartment_agents.tools.listings import ListingIngestionService


class AnalyzeApartmentServiceTest(unittest.TestCase):
    def test_analyze_generates_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
            )
            result = service.analyze(
                AnalyzeApartmentRequest(
                    listing_url="https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c",
                    buyer_profile_id="solo_engineer",
                )
            )

            self.assertEqual(result.report.recommendation.value, "BUY")
            self.assertTrue(result.report_path.exists())
            self.assertIn("Recommendation: **BUY**", result.report_markdown)
            self.assertEqual(result.report.findings[0].agent_name, "buyer_committee")
            self.assertIn("normalized_scores", result.report.findings[0].details)
            records = service.workspace_store.list_analysis_runs()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].report_id, result.report.report_id)

    def test_saved_workspace_profile_can_be_used_for_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
            )
            profile = BuyerProfile(
                buyer_id="saved_profile",
                household=HouseholdProfile(adults=1),
                gross_annual_income_dkk=840000,
                net_monthly_income_dkk=41000,
                savings_dkk=450000,
                existing_debt_dkk=0,
                risk_tolerance="balanced",
            )

            service.save_buyer_profile(profile)
            result = service.analyze(
                AnalyzeApartmentRequest(
                    listing_url="https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c",
                    buyer_profile_id="saved_profile",
                )
            )

            self.assertEqual(result.report.buyer_profile.buyer_id, "saved_profile")
            self.assertIn(
                "saved_profile",
                [profile.buyer_id for profile in service.available_buyer_profiles()],
            )

    def test_saved_workspace_profile_is_added_to_injected_fixture_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_store = FixtureStore()
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
                fixture_store=fixture_store,
            )
            profile = BuyerProfile(
                buyer_id="custom_store_profile",
                household=HouseholdProfile(adults=2),
                gross_annual_income_dkk=920000,
                net_monthly_income_dkk=52000,
                savings_dkk=650000,
                existing_debt_dkk=100000,
                risk_tolerance="balanced",
            )

            service.save_buyer_profile(profile)

            self.assertEqual(
                fixture_store.load_buyer_profile("custom_store_profile").buyer_id,
                "custom_store_profile",
            )

    def test_search_apartments_persists_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
            )

            result = service.search_apartments(
                SearchApartmentsRequest(
                    city="Aarhus C",
                    max_price_dkk=3700000,
                    min_area_sqm=50,
                )
            )

            self.assertTrue(result.workspace_path.exists())
            self.assertEqual(len(result.search_run.results), 2)
            self.assertEqual(
                service.available_listing_searches()[0].search_id, result.search_run.search_id
            )

    def test_search_result_can_be_saved_as_apartment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
            )
            search = service.search_apartments(SearchApartmentsRequest(city="Aarhus C"))

            saved = service.save_search_result_apartment(search.search_run.results[0])

            self.assertTrue(saved.workspace_path.exists())
            self.assertEqual(saved.saved_apartment.tags, ["search"])
            self.assertEqual(len(service.available_saved_apartments()), 1)
            self.assertEqual(
                service.available_saved_apartments()[0].url,
                search.search_run.results[0].url,
            )

    def test_analyze_reports_imported_capture_assumption(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
            )
            result = service.analyze(
                AnalyzeApartmentRequest(
                    listing_url="https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c-07510157___21___3____th",
                    buyer_profile_id="solo_engineer",
                )
            )

        self.assertIn(
            "Listing analysis used imported captured HTML rather than a live site fetch.",
            result.report.assumptions,
        )

    def test_analyze_rejects_missing_listing_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
            )

            with self.assertRaises(MissingListingUrlError):
                service.analyze(
                    AnalyzeApartmentRequest(
                        listing_url="   ",
                        buyer_profile_id="solo_engineer",
                    )
                )

    def test_analyze_rejects_missing_buyer_profile_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
            )

            with self.assertRaises(MissingBuyerProfileIdError):
                service.analyze(
                    AnalyzeApartmentRequest(
                        listing_url="https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c",
                        buyer_profile_id="",
                    )
                )

    def test_service_startup_rejects_missing_fixture_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_root = Path(tmpdir)
            (fixture_root / "buyers").mkdir(parents=True)
            (fixture_root / "buyers" / "buyer.json").write_text(
                """
                {
                  "buyer_id": "buyer-1",
                  "household": {"adults": 1, "children": 0, "monthly_childcare_cost_dkk": 0, "vehicles": 0},
                  "gross_annual_income_dkk": 800000,
                  "net_monthly_income_dkk": 40000,
                  "savings_dkk": 300000,
                  "existing_debt_dkk": 0
                }
                """,
                encoding="utf-8",
            )
            with self.assertRaises(StartupValidationError):
                AnalyzeApartmentService(
                    config=AppConfig(output_dir=fixture_root / "output", adk_backend="mock"),
                    fixture_store=FixtureStore(root=fixture_root),
                )

    def test_service_falls_back_when_runner_raises(self) -> None:
        class FailingRunner(AdkAnalysisRunner):
            def analyze(self, inputs):
                raise RuntimeError("runner blew up")

        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
                adk_runner=FailingRunner(),
            )

            result = service.analyze(
                AnalyzeApartmentRequest(
                    listing_url="https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c",
                    buyer_profile_id="solo_engineer",
                )
            )

            self.assertEqual(result.report.findings[0].agent_name, "buyer_committee")
            self.assertTrue(result.report.findings[0].details["fallback"])
            self.assertEqual(result.report.recommendation.value, "MAYBE")

    def test_service_reports_live_html_extraction_coverage(self) -> None:
        class HtmlFetcher:
            def fetch_text(self, url: str) -> str:
                return """
                <html><body>
                <h1>Odensegade 21, 3. th. 8000 Aarhus C Ejerlejlighed</h1>
                <div>Til salg: 3.698.000 kr.</div>
                <div>Boligareal: 51 m²</div>
                </body></html>
                """

        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_root = Path(tmpdir)
            (fixture_root / "listings").mkdir(parents=True)
            (fixture_root / "listings" / "index.json").write_text('{"items": []}', encoding="utf-8")
            config = AppConfig(
                output_dir=fixture_root / "output",
                adk_backend="mock",
                enable_live_listing_fetch=True,
            )
            service = AnalyzeApartmentService(
                config=config,
                listing_ingestion=ListingIngestionService(
                    FixtureStore(root=fixture_root),
                    config=config,
                    fetcher=HtmlFetcher(),  # type: ignore[arg-type]
                ),
                adk_runner=MockAdkAnalysisRunner(),
            )

            result = service.analyze(
                AnalyzeApartmentRequest(
                    listing_url="https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c",
                    buyer_profile_id="solo_engineer",
                )
            )

        self.assertIn(
            "Listing analysis used an HTML parsing fallback rather than a structured page payload.",
            result.report.assumptions,
        )
        self.assertIn(
            "Listing extraction could not confirm: rooms, owner_cost_monthly_dkk, build_year, elevator, balcony.",
            result.report.unresolved_questions,
        )
        self.assertIn("- Listing field coverage:", result.report_markdown)


if __name__ == "__main__":
    unittest.main()
