import unittest
from unittest.mock import patch

from apartment_agents.app.errors import ListingFetchBlockedError
from apartment_agents.tools.http import HttpPageFetcher


class _FakeResponse:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload.encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class HttpPageFetcherTest(unittest.TestCase):
    def test_fetch_text_raises_for_cloudflare_challenge_page(self) -> None:
        fetcher = HttpPageFetcher()
        page = "<html><title>Just a moment...</title><body>Cloudflare</body></html>"

        with patch("apartment_agents.tools.http.urlopen", return_value=_FakeResponse(page)):
            with self.assertRaises(ListingFetchBlockedError):
                fetcher.fetch_text("https://www.boligsiden.dk/adresse/test")

    def test_fetch_text_returns_html_for_normal_page(self) -> None:
        fetcher = HttpPageFetcher()
        page = "<html><body><h1>Apartment</h1></body></html>"

        with patch("apartment_agents.tools.http.urlopen", return_value=_FakeResponse(page)):
            result = fetcher.fetch_text("https://www.boligsiden.dk/adresse/test")

        self.assertIn("Apartment", result)


if __name__ == "__main__":
    unittest.main()
