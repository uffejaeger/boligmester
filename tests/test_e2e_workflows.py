import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apartment_agents.app.services import (
    AnalyzeApartmentService,
    SaveApartmentRequest,
    SearchApartmentsRequest,
)
from apartment_agents.config import AppConfig

try:
    from apartment_agents.tui.textual_ui import BoligmesterApp, SAMPLE_LISTING_URL
    from textual.widgets import DataTable, Input, Static
except ImportError:  # pragma: no cover - Textual is an optional extra
    BoligmesterApp = None
    DataTable = None
    Input = None
    Static = None
    SAMPLE_LISTING_URL = "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c"


class EndToEndCase:
    def __init__(self, test: unittest.TestCase, root: Path) -> None:
        self.test = test
        self.output_dir = root / "output"
        self.workspace_dir = root / "workspace"
        self.service = self.new_service()
        self.saved_apartment_ids: list[str] = []
        self.last_analysis_report_id: str | None = None
        self.last_comparison_id: str | None = None
        self.last_watchlist_change_fields: set[str] = set()

    def new_service(self) -> AnalyzeApartmentService:
        return AnalyzeApartmentService(
            config=AppConfig(
                output_dir=self.output_dir,
                workspace_dir=self.workspace_dir,
                adk_backend="mock",
            )
        )

    def restart(self) -> AnalyzeApartmentService:
        self.service = self.new_service()
        return self.service

    def steps(self) -> tuple["Given", "When", "Then"]:
        return Given(self), When(self), Then(self)


class Given:
    def __init__(self, case: EndToEndCase) -> None:
        self.case = case

    def a_clean_local_workspace(self) -> "Given":
        self.case.test.assertEqual(self.case.service.workspace_store.list_analysis_runs(), [])
        self.case.test.assertEqual(self.case.service.available_saved_apartments(), [])
        self.case.test.assertEqual(self.case.service.available_apartment_comparisons(), [])
        self.case.test.assertEqual(self.case.service.available_watchlist_runs(), [])
        return self

    def aarhus_c_apartments_are_saved(self, count: int = 2) -> "Given":
        search = self.case.service.search_apartments(SearchApartmentsRequest(city="Aarhus C"))
        self.case.saved_apartment_ids = [
            self.case.service.save_search_result_apartment(result).saved_apartment.saved_id
            for result in search.search_run.results[:count]
        ]
        self.case.test.assertEqual(len(self.case.saved_apartment_ids), count)
        return self


class When:
    def __init__(self, case: EndToEndCase) -> None:
        self.case = case

    async def the_user_opens_the_tui_and_saves_a_profile(
        self,
        profile_id: str = "e2e_family",
    ) -> "When":
        assert BoligmesterApp is not None
        assert Input is not None
        assert Static is not None

        app = BoligmesterApp(self.case.service)
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.1)
            await pilot.press("p")
            await pilot.pause(0.1)

            fields = {
                "profile-id": profile_id,
                "profile-adults": "2",
                "profile-children": "1",
                "profile-childcare": "3500",
                "profile-vehicles": "1",
                "profile-net-income": "65000",
                "profile-gross-income": "1320000",
                "profile-savings": "850000",
                "profile-existing-debt": "125000",
                "profile-monthly-debt": "2500",
                "profile-down-payment": "500000",
                "profile-risk": "balanced",
                "profile-notes": "Two permanent contracts",
            }
            for field_id, value in fields.items():
                app.screen.query_one(f"#{field_id}", Input).value = value

            await app.screen.action_save_profile()
            status = app.screen.query_one("#profile-status", Static)

        self.case.test.assertEqual(str(status.content), f"saved profile {profile_id}")
        return self

    async def the_user_analyzes_a_listing_url(
        self,
        listing_url: str = SAMPLE_LISTING_URL,
    ) -> "When":
        assert BoligmesterApp is not None
        assert Input is not None
        assert Static is not None

        app = BoligmesterApp(self.case.service)
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.1)
            await pilot.press("1")
            await pilot.pause(0.1)

            app.screen.query_one("#listing-url", Input).value = listing_url
            await app.screen.action_run_analysis()

            status = app.screen.query_one("#analysis-status", Static)
            recommendation = app.screen.query_one("#recommendation-tile", Static)
            evidence = app.screen.query_one("#evidence-tile", Static)

        self.case.test.assertEqual(str(status.content), "analysis complete")
        self.case.test.assertEqual(str(recommendation.content), "[b]BUY[/b]\nRECOMMENDATION")
        self.case.test.assertIn("findings", str(evidence.content))
        self.case.last_analysis_report_id = self.case.service.workspace_store.list_analysis_runs()[
            0
        ].report_id
        return self

    async def the_user_searches_saves_and_analyzes_an_aarhus_c_property(self) -> "When":
        assert BoligmesterApp is not None
        assert DataTable is not None
        assert Input is not None
        assert Static is not None

        app = BoligmesterApp(self.case.service)
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.1)
            await pilot.press("2")
            await pilot.pause(0.1)

            app.screen.query_one("#search-city", Input).value = "Aarhus C"
            app.screen.query_one("#search-max-price", Input).value = "3700000"
            app.screen.query_one("#search-min-area", Input).value = "50"
            app.screen.query_one("#search-max-results", Input).value = "10"

            await app.screen.action_run_search()
            search_status = app.screen.query_one("#search-status", Static)
            search_results = app.screen.query_one("#search-results", DataTable)

            self.case.test.assertEqual(
                str(search_status.content), "search complete: 2 results saved"
            )
            self.case.test.assertEqual(search_results.row_count, 2)

            app.screen.action_save_selected_apartment()
            app.screen.action_analyze_selected()
            await pilot.pause(0.1)

            await app.screen.action_run_analysis()
            analysis_status = app.screen.query_one("#analysis-status", Static)
            recommendation = app.screen.query_one("#recommendation-tile", Static)

        self.case.test.assertEqual(str(analysis_status.content), "analysis complete")
        self.case.test.assertEqual(str(recommendation.content), "[b]BUY[/b]\nRECOMMENDATION")
        self.case.saved_apartment_ids = [
            apartment.saved_id for apartment in self.case.service.available_saved_apartments()
        ]
        self.case.last_analysis_report_id = self.case.service.workspace_store.list_analysis_runs()[
            0
        ].report_id
        return self

    async def the_user_compares_saved_apartments(self) -> "When":
        assert BoligmesterApp is not None
        assert DataTable is not None
        assert Static is not None

        app = BoligmesterApp(self.case.service)
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.1)
            await pilot.press("5")
            await pilot.pause(0.1)

            candidates = app.screen.query_one("#comparison-candidates", DataTable)
            self.case.test.assertEqual(candidates.row_count, 2)

            await app.screen.action_run_comparison()
            status = app.screen.query_one("#comparison-status", Static)

        self.case.test.assertIn("comparison complete:", str(status.content))
        self.case.last_comparison_id = self.case.service.available_apartment_comparisons()[
            0
        ].comparison_id
        return self

    async def the_user_refreshes_the_watchlist(self) -> "When":
        assert BoligmesterApp is not None
        assert Static is not None

        app = BoligmesterApp(self.case.service)
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.1)
            await pilot.press("6")
            await pilot.pause(0.1)

            await app.screen.action_refresh_watchlist()
            status = app.screen.query_one("#watchlist-status", Static)

        latest_run = self.case.service.available_watchlist_runs()[0]
        self.case.last_watchlist_change_fields = {change.field for change in latest_run.changes}
        self.case.test.assertEqual(
            str(status.content),
            f"watchlist refresh: {len(latest_run.changes)} changes",
        )
        return self

    def new_source_data_lowers_the_first_saved_apartment_price(self) -> "When":
        apartment = self.case.service.available_saved_apartments()[0]
        self.case.service.save_apartment(
            SaveApartmentRequest(
                listing_id=apartment.listing_id,
                source=apartment.source,
                url=apartment.url,
                title=apartment.title,
                address=apartment.address,
                asking_price_dkk=(apartment.asking_price_dkk or 0) - 100000,
                area_sqm=apartment.area_sqm,
                rooms=apartment.rooms,
                owner_cost_monthly_dkk=apartment.owner_cost_monthly_dkk,
                notes=apartment.notes,
                tags=apartment.tags,
                raw_payload=apartment.raw_payload,
            )
        )
        return self


class Then:
    def __init__(self, case: EndToEndCase) -> None:
        self.case = case

    def the_profile_is_available_after_restart(self, profile_id: str = "e2e_family") -> "Then":
        service = self.case.restart()
        profiles = {profile.buyer_id: profile for profile in service.available_buyer_profiles()}

        self.case.test.assertIn(profile_id, profiles)
        self.case.test.assertEqual(profiles[profile_id].household.children, 1)
        self.case.test.assertEqual(profiles[profile_id].household.monthly_childcare_cost_dkk, 3500)
        self.case.test.assertEqual(profiles[profile_id].savings_dkk, 850000)
        return self

    def the_analysis_run_is_available_after_restart(self) -> "Then":
        service = self.case.restart()
        runs = service.workspace_store.list_analysis_runs()

        self.case.test.assertEqual(len(runs), 1)
        self.case.test.assertEqual(runs[0].report_id, self.case.last_analysis_report_id)
        self.case.test.assertTrue(Path(runs[0].report_path).exists())
        return self

    def the_search_saved_apartment_and_analysis_are_available_after_restart(self) -> "Then":
        service = self.case.restart()
        searches = service.available_listing_searches()
        apartments = service.available_saved_apartments()
        runs = service.workspace_store.list_analysis_runs()

        self.case.test.assertEqual(len(searches), 1)
        self.case.test.assertEqual(searches[0].criteria.city, "Aarhus C")
        self.case.test.assertEqual(len(searches[0].results), 2)
        self.case.test.assertEqual(len(apartments), 1)
        self.case.test.assertEqual(apartments[0].saved_id, self.case.saved_apartment_ids[0])
        self.case.test.assertEqual(len(runs), 1)
        self.case.test.assertEqual(runs[0].report_id, self.case.last_analysis_report_id)
        return self

    def the_comparison_is_available_after_restart(self) -> "Then":
        service = self.case.restart()
        comparisons = service.available_apartment_comparisons()

        self.case.test.assertEqual(len(comparisons), 1)
        self.case.test.assertEqual(comparisons[0].comparison_id, self.case.last_comparison_id)
        self.case.test.assertEqual(len(comparisons[0].items), 2)
        self.case.test.assertIsNotNone(comparisons[0].recommended_saved_id)
        return self

    def the_watchlist_change_is_available_after_restart(self) -> "Then":
        service = self.case.restart()
        runs = service.available_watchlist_runs()

        self.case.test.assertEqual(len(runs), 2)
        self.case.test.assertEqual(
            {"asking_price_dkk", "price_per_sqm_dkk"},
            {change.field for change in runs[0].changes},
        )
        self.case.test.assertEqual(
            {"asking_price_dkk", "price_per_sqm_dkk"},
            self.case.last_watchlist_change_fields,
        )
        return self


@unittest.skipUnless(BoligmesterApp is not None, "Textual is required for TUI E2E tests")
class TuiEndToEndWorkflowTest(unittest.TestCase):
    def test_profile_creation_survives_tui_restart(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                case = EndToEndCase(self, Path(tmpdir))
                given, when, then = case.steps()

                given.a_clean_local_workspace()
                await when.the_user_opens_the_tui_and_saves_a_profile()
                then.the_profile_is_available_after_restart()

        asyncio.run(scenario())

    def test_url_analysis_survives_tui_restart(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                case = EndToEndCase(self, Path(tmpdir))
                given, when, then = case.steps()

                given.a_clean_local_workspace()
                await when.the_user_analyzes_a_listing_url()
                then.the_analysis_run_is_available_after_restart()

        asyncio.run(scenario())

    def test_search_save_and_analyze_flow_survives_tui_restart(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                case = EndToEndCase(self, Path(tmpdir))
                given, when, then = case.steps()

                given.a_clean_local_workspace()
                await when.the_user_searches_saves_and_analyzes_an_aarhus_c_property()
                then.the_search_saved_apartment_and_analysis_are_available_after_restart()

        asyncio.run(scenario())

    def test_comparison_and_watchlist_flows_survive_tui_restart(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                case = EndToEndCase(self, Path(tmpdir))
                given, when, then = case.steps()

                given.a_clean_local_workspace().aarhus_c_apartments_are_saved()
                await when.the_user_compares_saved_apartments()
                then.the_comparison_is_available_after_restart()
                await when.the_user_refreshes_the_watchlist()
                when.new_source_data_lowers_the_first_saved_apartment_price()
                await when.the_user_refreshes_the_watchlist()
                then.the_watchlist_change_is_available_after_restart()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
