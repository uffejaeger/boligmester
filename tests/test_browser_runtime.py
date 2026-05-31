import unittest
from io import StringIO
from pathlib import Path
from types import ModuleType
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apartment_agents.app.errors import ListingFetchError
from apartment_agents.tools.browser_runtime import (
    fetch_rendered_html,
    main,
    parse_args,
    validate_url,
)


class BrowserRuntimeTest(unittest.TestCase):
    def test_parse_args_accepts_url(self) -> None:
        args = parse_args(["https://www.boligsiden.dk/adresse/test"])

        self.assertEqual(args.url, "https://www.boligsiden.dk/adresse/test")
        self.assertEqual(args.timeout_ms, 45000)

    def test_parse_args_accepts_storage_state(self) -> None:
        args = parse_args(
            [
                "https://www.boligsiden.dk/adresse/test",
                "--storage-state",
                "/tmp/storage-state.json",
            ]
        )

        self.assertEqual(args.storage_state, "/tmp/storage-state.json")

    def test_validate_url_rejects_relative_url(self) -> None:
        with self.assertRaises(ListingFetchError):
            validate_url("/adresse/test")

    def test_fetch_rendered_html_raises_when_playwright_missing(self) -> None:
        with patch("builtins.__import__", side_effect=ImportError("missing")):
            with self.assertRaises(ListingFetchError):
                fetch_rendered_html("https://www.boligsiden.dk/adresse/test")

    def test_main_prints_rendered_html(self) -> None:
        with (
            patch(
                "apartment_agents.tools.browser_runtime.fetch_rendered_html",
                return_value="<html><body>Rendered</body></html>",
            ),
            patch("sys.stdout", new_callable=StringIO) as stdout,
        ):
            self.assertEqual(main(["https://www.boligsiden.dk/adresse/test"]), 0)

        self.assertIn("Rendered", stdout.getvalue())

    def test_main_returns_nonzero_for_runtime_error(self) -> None:
        with (
            patch(
                "apartment_agents.tools.browser_runtime.fetch_rendered_html",
                side_effect=ListingFetchError("failed"),
            ),
            patch("sys.stderr", new_callable=StringIO) as stderr,
        ):
            self.assertEqual(main(["https://www.boligsiden.dk/adresse/test"]), 1)

        self.assertIn("failed", stderr.getvalue())

    def test_fetch_rendered_html_rejects_missing_storage_state_file(self) -> None:
        with self.assertRaises(ListingFetchError):
            fetch_rendered_html(
                "https://www.boligsiden.dk/adresse/test",
                storage_state_path="/tmp/does-not-exist.json",
            )

    def test_fetch_rendered_html_uses_env_storage_state_path(self) -> None:
        class FakePage:
            def goto(self, url: str, wait_until: str, timeout: int) -> None:
                return None

            def content(self) -> str:
                return "<html><body>Rendered</body></html>"

        class FakeContext:
            def new_page(self) -> FakePage:
                return FakePage()

            def close(self) -> None:
                return None

        class FakeBrowser:
            def __init__(self) -> None:
                self.context_kwargs = None

            def new_context(self, **kwargs):
                self.context_kwargs = kwargs
                return FakeContext()

            def close(self) -> None:
                return None

        class FakeChromium:
            def __init__(self, browser: FakeBrowser) -> None:
                self.browser = browser

            def launch(self, headless: bool = True) -> FakeBrowser:
                return self.browser

        class FakePlaywright:
            def __init__(self, browser: FakeBrowser) -> None:
                self.chromium = FakeChromium(browser)

        class FakePlaywrightManager:
            def __init__(self, browser: FakeBrowser) -> None:
                self.browser = browser

            def __enter__(self) -> FakePlaywright:
                return FakePlaywright(self.browser)

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        browser = FakeBrowser()

        with TemporaryDirectory() as tmpdir:
            storage_state = Path(tmpdir) / "state.json"
            storage_state.write_text("{}", encoding="utf-8")
            playwright_module = ModuleType("playwright")
            sync_api_module = ModuleType("playwright.sync_api")
            sync_api_module.Error = RuntimeError
            sync_api_module.sync_playwright = lambda: FakePlaywrightManager(browser)
            with (
                patch.dict("os.environ", {"BROWSER_STORAGE_STATE_PATH": str(storage_state)}),
                patch.dict(
                    "sys.modules",
                    {
                        "playwright": playwright_module,
                        "playwright.sync_api": sync_api_module,
                    },
                ),
            ):
                html = fetch_rendered_html("https://www.boligsiden.dk/adresse/test")

        self.assertIn("Rendered", html)
        self.assertEqual(browser.context_kwargs, {"storage_state": str(storage_state)})


if __name__ == "__main__":
    unittest.main()
