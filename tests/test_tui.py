import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apartment_agents.app.services import AnalyzeApartmentService, SearchApartmentsRequest
from apartment_agents.config import AppConfig
from apartment_agents.tui.app import render_main_menu, render_placeholder_screen, run

try:
    from apartment_agents.tui.textual_ui import BoligmesterApp
    from textual.widgets import DataTable, Input, Static
except ImportError:  # pragma: no cover - Textual is an optional extra
    BoligmesterApp = None
    DataTable = None
    Input = None
    Static = None


class TuiTest(unittest.TestCase):
    def test_render_main_menu_contains_primary_flow(self) -> None:
        menu = render_main_menu()

        self.assertIn("Boligmester", menu)
        self.assertIn("1 Analyze Apartment URL", menu)
        self.assertIn("9 Buyer Profiles", menu)

    def test_render_placeholder_screen_for_search(self) -> None:
        screen = render_placeholder_screen("2")

        self.assertIn("Search Apartments", screen)
        self.assertIn("Status: Available", screen)

    def test_render_placeholder_screen_for_profiles(self) -> None:
        screen = render_placeholder_screen("9")

        self.assertIn("Buyer Profiles", screen)
        self.assertIn("Status: Available", screen)

    def test_render_placeholder_screen_for_saved_apartments(self) -> None:
        screen = render_placeholder_screen("6")

        self.assertIn("Saved Apartments", screen)
        self.assertIn("Status: Available", screen)

    def test_render_placeholder_screen_for_compare(self) -> None:
        screen = render_placeholder_screen("5")

        self.assertIn("Compare Apartments", screen)
        self.assertIn("Status: Available", screen)

    def test_render_placeholder_screen_for_unknown_option(self) -> None:
        screen = render_placeholder_screen("99")

        self.assertIn("Unknown menu selection", screen)

    def test_run_delegates_to_textual_launcher(self) -> None:
        launched = {}

        def fake_launcher(service: AnalyzeApartmentService) -> None:
            launched["service"] = service

        with TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
            )
            with patch(
                "apartment_agents.tui.app._load_textual_launcher", return_value=fake_launcher
            ):
                run(service=service)

        self.assertIs(launched["service"], service)

    def test_run_initializes_service_when_none_is_provided(self) -> None:
        launched = {}

        def fake_launcher(service: AnalyzeApartmentService) -> None:
            launched["service"] = service

        with patch("apartment_agents.tui.app._load_textual_launcher", return_value=fake_launcher):
            run()

        self.assertIsInstance(launched["service"], AnalyzeApartmentService)

    @unittest.skipUnless(BoligmesterApp is not None, "Textual is an optional TUI extra")
    def test_textual_analyzer_runs_mock_analysis(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                service = AnalyzeApartmentService(
                    config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
                )
                app = BoligmesterApp(service)

                async with app.run_test(size=(80, 24)) as pilot:
                    await pilot.pause(0.1)
                    await pilot.press("enter")
                    await pilot.pause(0.1)
                    await pilot.press("enter")
                    await pilot.pause(1.0)

                    recommendation = app.screen.query_one("#recommendation-tile", Static)
                    status = app.screen.query_one("#analysis-status", Static)

                self.assertEqual(recommendation.content, "[b]BUY[/b]\nRECOMMENDATION")
                self.assertEqual(str(status.content), "analysis complete")

        asyncio.run(scenario())

    @unittest.skipUnless(BoligmesterApp is not None, "Textual is an optional TUI extra")
    def test_textual_arrow_keys_move_focus(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                service = AnalyzeApartmentService(
                    config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
                )
                app = BoligmesterApp(service)

                async with app.run_test(size=(80, 24)) as pilot:
                    await pilot.pause(0.1)

                    table = app.screen.query_one("#resource-table", DataTable)
                    self.assertEqual(app.focused.id, "resource-table")
                    self.assertEqual(table.cursor_row, 0)

                    await pilot.press("down")
                    await pilot.pause(0.1)
                    self.assertEqual(table.cursor_row, 1)

                    await pilot.press("up")
                    await pilot.pause(0.1)
                    self.assertEqual(table.cursor_row, 0)

                    await pilot.press("enter")
                    await pilot.pause(0.1)
                    command_table = app.screen.query_one("#command-table", DataTable)
                    self.assertEqual(app.focused.id, "command-table")
                    self.assertEqual(command_table.cursor_row, 0)

                    await pilot.press("down")
                    await pilot.pause(0.1)
                    self.assertEqual(command_table.cursor_row, 1)

        asyncio.run(scenario())

    @unittest.skipUnless(BoligmesterApp is not None, "Textual is an optional TUI extra")
    def test_textual_profile_screen_saves_profile(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                service = AnalyzeApartmentService(
                    config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
                )
                app = BoligmesterApp(service)

                async with app.run_test(size=(100, 34)) as pilot:
                    await pilot.pause(0.1)
                    await pilot.press("p")
                    await pilot.pause(0.1)

                    app.screen.query_one("#profile-id", Input).value = "tui_profile"
                    app.screen.query_one("#profile-adults", Input).value = "2"
                    app.screen.query_one("#profile-children", Input).value = "1"
                    app.screen.query_one("#profile-childcare", Input).value = "2500"
                    app.screen.query_one("#profile-vehicles", Input).value = "1"
                    app.screen.query_one("#profile-net-income", Input).value = "62000"
                    app.screen.query_one("#profile-gross-income", Input).value = "1200000"
                    app.screen.query_one("#profile-savings", Input).value = "700000"
                    app.screen.query_one("#profile-existing-debt", Input).value = "50000"
                    app.screen.query_one("#profile-monthly-debt", Input).value = "1500"
                    app.screen.query_one("#profile-down-payment", Input).value = "400000"
                    app.screen.query_one("#profile-risk", Input).value = "balanced"
                    app.screen.query_one("#profile-notes", Input).value = "Two permanent contracts"

                    await app.screen.action_save_profile()
                    await pilot.pause(0.1)

                    status = app.screen.query_one("#profile-status", Static)

                self.assertEqual(str(status.content), "saved profile tui_profile")
                self.assertIn(
                    "tui_profile",
                    [profile.buyer_id for profile in service.available_buyer_profiles()],
                )
                profile = service.fixture_store.load_buyer_profile("tui_profile")
                self.assertEqual(profile.household.monthly_childcare_cost_dkk, 2500)
                self.assertEqual(profile.household.vehicles, 1)

        asyncio.run(scenario())

    @unittest.skipUnless(BoligmesterApp is not None, "Textual is an optional TUI extra")
    def test_textual_search_screen_searches_and_opens_analyzer(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                service = AnalyzeApartmentService(
                    config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
                )
                app = BoligmesterApp(service)

                async with app.run_test(size=(110, 34)) as pilot:
                    await pilot.pause(0.1)
                    await pilot.press("2")
                    await pilot.pause(0.1)

                    app.screen.query_one("#search-max-price", Input).value = "3700000"
                    app.screen.query_one("#search-min-area", Input).value = "50"
                    await app.screen.action_run_search()
                    await pilot.pause(0.1)

                    status = app.screen.query_one("#search-status", Static)
                    results = app.screen.query_one("#search-results", DataTable)
                    self.assertEqual(str(status.content), "search complete: 2 results saved")
                    self.assertEqual(results.row_count, 2)

                    app.screen.action_save_selected_apartment()
                    await pilot.pause(0.1)
                    self.assertEqual(
                        len(service.available_saved_apartments()),
                        1,
                    )

                    app.screen.action_analyze_selected()
                    await pilot.pause(0.1)

                    listing_url = app.screen.query_one("#listing-url", Input).value

                self.assertEqual(
                    listing_url,
                    "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c",
                )
                self.assertEqual(len(service.available_listing_searches()), 1)

        asyncio.run(scenario())

    @unittest.skipUnless(BoligmesterApp is not None, "Textual is an optional TUI extra")
    def test_textual_saved_apartments_screen_opens_analyzer(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                service = AnalyzeApartmentService(
                    config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
                )
                search = service.search_apartments(SearchApartmentsRequest(city="Aarhus C"))
                service.save_search_result_apartment(search.search_run.results[0])
                app = BoligmesterApp(service)

                async with app.run_test(size=(110, 34)) as pilot:
                    await pilot.pause(0.1)
                    await pilot.press("6")
                    await pilot.pause(0.1)

                    table = app.screen.query_one("#saved-apartments", DataTable)
                    self.assertEqual(table.row_count, 1)

                    app.screen.action_analyze_selected()
                    await pilot.pause(0.1)

                    listing_url = app.screen.query_one("#listing-url", Input).value

                self.assertEqual(
                    listing_url,
                    "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c",
                )

        asyncio.run(scenario())

    @unittest.skipUnless(BoligmesterApp is not None, "Textual is an optional TUI extra")
    def test_textual_comparison_screen_compares_saved_apartments(self) -> None:
        async def scenario() -> None:
            with TemporaryDirectory() as tmpdir:
                service = AnalyzeApartmentService(
                    config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
                )
                search = service.search_apartments(SearchApartmentsRequest(city="Aarhus C"))
                for result in search.search_run.results[:2]:
                    service.save_search_result_apartment(result)
                app = BoligmesterApp(service)

                async with app.run_test(size=(120, 36)) as pilot:
                    await pilot.pause(0.1)
                    await pilot.press("5")
                    await pilot.pause(0.1)

                    table = app.screen.query_one("#comparison-candidates", DataTable)
                    self.assertEqual(table.row_count, 2)

                    await app.screen.action_run_comparison()
                    await pilot.pause(0.1)

                    status = app.screen.query_one("#comparison-status", Static)

                self.assertIn("comparison complete:", str(status.content))
                self.assertEqual(len(service.available_apartment_comparisons()), 1)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
