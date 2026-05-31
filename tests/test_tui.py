import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apartment_agents.config import AppConfig
from apartment_agents.app.services import AnalyzeApartmentService
from apartment_agents.tui.app import render_main_menu, render_placeholder_screen


class TuiTest(unittest.TestCase):
    def test_render_main_menu_contains_primary_flow(self) -> None:
        menu = render_main_menu()

        self.assertIn("ApartmentBuyingAgents DK", menu)
        self.assertIn("1 Analyze Apartment URL", menu)

    def test_render_placeholder_screen_for_search(self) -> None:
        screen = render_placeholder_screen("2")

        self.assertIn("Search Apartments", screen)
        self.assertIn("Status: Planned", screen)

    def test_render_placeholder_screen_for_unknown_option(self) -> None:
        screen = render_placeholder_screen("99")

        self.assertIn("Unknown menu selection", screen)

    def test_run_analyze_flow_prints_recommendation(self) -> None:
        prompts = iter(
            [
                "1",
                "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c",
                "solo_engineer",
            ]
        )
        outputs: list[str] = []

        def fake_input(_: str) -> str:
            return next(prompts)

        def fake_output(message: str) -> None:
            outputs.append(message)

        with TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
            )
            from apartment_agents.tui import app

            app.run(input_func=fake_input, output_func=fake_output, service=service)

        joined = "\n".join(outputs)
        self.assertIn("Recommendation: BUY", joined)

    def test_run_placeholder_flow_prints_planned_screen(self) -> None:
        prompts = iter(["7"])
        outputs: list[str] = []

        def fake_input(_: str) -> str:
            return next(prompts)

        def fake_output(message: str) -> None:
            outputs.append(message)

        with TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
            )
            from apartment_agents.tui import app

            app.run(input_func=fake_input, output_func=fake_output, service=service)

        joined = "\n".join(outputs)
        self.assertIn("Reports", joined)
        self.assertIn("Status: Planned", joined)

    def test_run_analyze_flow_rejects_missing_buyer_profile_id(self) -> None:
        prompts = iter(
            [
                "1",
                "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c",
                "",
            ]
        )
        outputs: list[str] = []

        def fake_input(_: str) -> str:
            return next(prompts)

        def fake_output(message: str) -> None:
            outputs.append(message)

        with TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock")
            )
            from apartment_agents.tui import app

            app.run(input_func=fake_input, output_func=fake_output, service=service)

        joined = "\n".join(outputs)
        self.assertIn("Analysis error: Buyer profile id is required.", joined)


if __name__ == "__main__":
    unittest.main()
