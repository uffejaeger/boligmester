import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apartment_agents.app.services import AnalyzeApartmentService
from apartment_agents.config import AppConfig
from apartment_agents.tui.app import render_main_menu, render_placeholder_screen, run

try:
    from apartment_agents.tui.textual_ui import BoligmesterApp
    from textual.widgets import DataTable, Static
except ImportError:  # pragma: no cover - Textual is an optional extra
    BoligmesterApp = None
    DataTable = None
    Static = None


class TuiTest(unittest.TestCase):
    def test_render_main_menu_contains_primary_flow(self) -> None:
        menu = render_main_menu()

        self.assertIn("Boligmester", menu)
        self.assertIn("1 Analyze Apartment URL", menu)

    def test_render_placeholder_screen_for_search(self) -> None:
        screen = render_placeholder_screen("2")

        self.assertIn("Search Apartments", screen)
        self.assertIn("Status: Planned", screen)

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


if __name__ == "__main__":
    unittest.main()
