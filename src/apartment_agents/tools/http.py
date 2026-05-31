from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apartment_agents.app.errors import ListingFetchBlockedError, ListingFetchError


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def detect_blocked_listing_html(document: str) -> str | None:
    lowered = document.lower()
    if "just a moment" in lowered and "cloudflare" in lowered:
        return "Listing fetch was blocked by Cloudflare challenge handling."
    if "enable javascript and cookies to continue" in lowered:
        return "Listing fetch requires JavaScript and cookies to continue."
    return None


@dataclass(slots=True)
class HttpPageFetcher:
    timeout_seconds: int = 20
    user_agent: str = DEFAULT_USER_AGENT

    def fetch_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                document = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise ListingFetchError(
                f"HTTP fetch failed with status {exc.code} for URL: {url}"
            ) from exc
        except URLError as exc:
            raise ListingFetchError(f"Could not fetch listing URL: {url}") from exc

        blocked_message = detect_blocked_listing_html(document)
        if blocked_message is not None:
            raise ListingFetchBlockedError(blocked_message)
        return document


@dataclass(slots=True)
class BlockedPageFallbackFetcher:
    primary: object
    blocked_fallback: object | None = None

    def fetch_text(self, url: str) -> str:
        try:
            return self.primary.fetch_text(url)
        except ListingFetchBlockedError:
            if self.blocked_fallback is None:
                raise
            return self.blocked_fallback.fetch_text(url)
