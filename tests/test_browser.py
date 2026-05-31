import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apartment_agents.app.errors import (
    ConfigValidationError,
    ListingFetchBlockedError,
    ListingFetchError,
)
from apartment_agents.tools.browser import BrowserCommandPageFetcher
from apartment_agents.tools.http import BlockedPageFallbackFetcher


class BrowserCommandPageFetcherTest(unittest.TestCase):
    def test_rejects_missing_url_placeholder(self) -> None:
        with self.assertRaises(ConfigValidationError):
            BrowserCommandPageFetcher(command_template="python3 script.py")

    def test_returns_stdout_when_command_succeeds(self) -> None:
        class Result:
            returncode = 0
            stdout = "<html><body>Apartment</body></html>"
            stderr = ""

        with patch("shutil.which", return_value="/usr/bin/python3"):
            fetcher = BrowserCommandPageFetcher(
                command_template="python3 script.py {url}",
                timeout_seconds=5,
            )
        with patch("subprocess.run", return_value=Result()):
            result = fetcher.fetch_text("https://www.boligsiden.dk/adresse/test")

        self.assertIn("Apartment", result)

    def test_raises_when_browser_command_returns_blocked_page(self) -> None:
        class Result:
            returncode = 0
            stdout = "<html><title>Just a moment...</title><body>Cloudflare</body></html>"
            stderr = ""

        with patch("shutil.which", return_value="/usr/bin/python3"):
            fetcher = BrowserCommandPageFetcher(
                command_template="python3 script.py {url}",
                timeout_seconds=5,
            )
        with patch("subprocess.run", return_value=Result()):
            with self.assertRaises(ListingFetchError):
                fetcher.fetch_text("https://www.boligsiden.dk/adresse/test")

    def test_forwards_storage_state_path_in_env_and_placeholder(self) -> None:
        class Result:
            returncode = 0
            stdout = "<html><body>Apartment</body></html>"
            stderr = ""

        with TemporaryDirectory() as tmpdir:
            storage_state = Path(tmpdir) / "state.json"
            storage_state.write_text("{}", encoding="utf-8")
            with patch("shutil.which", return_value="/usr/bin/python3"):
                fetcher = BrowserCommandPageFetcher(
                    command_template=(
                        "python3 script.py {url} --storage-state {storage_state_path}"
                    ),
                    timeout_seconds=5,
                    storage_state_path=storage_state,
                )
            with patch("subprocess.run", return_value=Result()) as run_mock:
                fetcher.fetch_text("https://www.boligsiden.dk/adresse/test")

        self.assertIn(str(storage_state), run_mock.call_args.kwargs["env"]["BROWSER_STORAGE_STATE_PATH"])
        self.assertIn(str(storage_state), run_mock.call_args.args[0])


class BlockedPageFallbackFetcherTest(unittest.TestCase):
    def test_uses_browser_fallback_when_http_fetch_is_blocked(self) -> None:
        class BlockedFetcher:
            def fetch_text(self, url: str) -> str:
                raise ListingFetchBlockedError("blocked")

        class BrowserFetcher:
            def fetch_text(self, url: str) -> str:
                return "<html><body>Rendered</body></html>"

        fetcher = BlockedPageFallbackFetcher(
            primary=BlockedFetcher(),
            blocked_fallback=BrowserFetcher(),
        )

        result = fetcher.fetch_text("https://www.boligsiden.dk/adresse/test")

        self.assertIn("Rendered", result)

    def test_does_not_use_browser_fallback_for_non_blocked_errors(self) -> None:
        class BrokenFetcher:
            def fetch_text(self, url: str) -> str:
                raise ListingFetchError("network failed")

        class BrowserFetcher:
            def fetch_text(self, url: str) -> str:
                return "<html><body>Rendered</body></html>"

        fetcher = BlockedPageFallbackFetcher(
            primary=BrokenFetcher(),
            blocked_fallback=BrowserFetcher(),
        )

        with self.assertRaises(ListingFetchError):
            fetcher.fetch_text("https://www.boligsiden.dk/adresse/test")


if __name__ == "__main__":
    unittest.main()
