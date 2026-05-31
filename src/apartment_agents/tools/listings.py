from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from apartment_agents.app.errors import FixtureNotFoundError, ListingIngestionError, UnsupportedListingDomainError
from apartment_agents.config import AppConfig
from apartment_agents.logging import get_logger, log_kv
from apartment_agents.models import Listing
from apartment_agents.storage.fixtures import FixtureStore
from apartment_agents.tools.browser import BrowserCommandPageFetcher
from apartment_agents.tools.http import BlockedPageFallbackFetcher, HttpPageFetcher
from apartment_agents.tools.listing_parsers import BoligsidenParser, EstateParser, ListingParser

logger = get_logger("listings")


SUPPORTED_LISTING_DOMAINS = {
    "www.boligsiden.dk": "boligsiden",
    "boligsiden.dk": "boligsiden",
    "www.estatemeglerne.dk": "estate_agent",
    "estatemeglerne.dk": "estate_agent",
}


@dataclass(slots=True)
class ListingIngestionService:
    fixture_store: FixtureStore
    config: AppConfig | None = None
    fetcher: HttpPageFetcher | None = None
    parsers: dict[str, ListingParser] = field(init=False)

    def __post_init__(self) -> None:
        self.parsers = {
            "boligsiden": BoligsidenParser(),
            "estate_agent": EstateParser(),
        }
        self.fetcher = self.fetcher or self._build_fetcher()

    def parse_listing_url(self, url: str) -> Listing:
        normalized_url, source_name = self._validate_url(url)
        try:
            document = self.fixture_store.load_listing_document(normalized_url)
            log_kv(logger, 20, "listing_fixture_loaded", url=normalized_url, source=source_name)
            ingestion_source = "fixture"
        except FixtureNotFoundError:
            try:
                capture_name, document = self.fixture_store.load_captured_listing_document(normalized_url)
                log_kv(
                    logger,
                    20,
                    "listing_capture_loaded",
                    url=normalized_url,
                    source=source_name,
                    document=capture_name,
                )
                ingestion_source = "captured_listing"
            except FixtureNotFoundError:
                if not self.config or not self.config.enable_live_listing_fetch:
                    raise ListingIngestionError(
                        "No fixture or captured listing matched the URL and live listing fetch is disabled."
                    )
                log_kv(logger, 20, "listing_live_fetch_started", url=normalized_url, source=source_name)
                document = self.fetcher.fetch_text(normalized_url)
                log_kv(logger, 20, "listing_live_fetch_completed", url=normalized_url, source=source_name)
                ingestion_source = "live_fetch"
        except Exception as exc:
            raise ListingIngestionError(f"Could not load listing document for URL: {normalized_url}") from exc

        parser = self.parsers[source_name]
        listing = parser.parse(normalized_url, document)
        listing.raw_payload["ingestion_source"] = ingestion_source
        return listing

    def _validate_url(self, url: str) -> tuple[str, str]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ListingIngestionError("Listing URL must start with http:// or https://")
        if not parsed.netloc:
            raise ListingIngestionError("Listing URL must include a domain")
        if parsed.netloc not in SUPPORTED_LISTING_DOMAINS:
            raise UnsupportedListingDomainError(
                f"Unsupported listing domain: {parsed.netloc}. "
                "Supported fixtures currently cover boligsiden.dk and estatemeglerne.dk"
            )
        return url, SUPPORTED_LISTING_DOMAINS[parsed.netloc]

    def _build_fetcher(self):
        timeout_seconds = self.config.http_timeout_seconds if self.config else 20
        primary = HttpPageFetcher(timeout_seconds=timeout_seconds)
        if self.config and self.config.enable_browser_listing_fetch:
            browser_fetcher = BrowserCommandPageFetcher(
                command_template=self.config.browser_listing_fetch_command or "",
                timeout_seconds=self.config.browser_fetch_timeout_seconds,
            )
            return BlockedPageFallbackFetcher(
                primary=primary,
                blocked_fallback=browser_fetcher,
            )
        return primary
