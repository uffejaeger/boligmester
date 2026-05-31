from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from html import unescape
from typing import Protocol
from urllib.parse import quote_plus, urljoin

from apartment_agents.app.errors import FixtureNotFoundError, ListingIngestionError
from apartment_agents.config import AppConfig
from apartment_agents.logging import get_logger, log_kv
from apartment_agents.models import (
    Address,
    ListingSearchCriteria,
    ListingSearchResult,
    ListingSearchRun,
    SourceCitation,
)
from apartment_agents.storage.fixtures import FixtureStore
from apartment_agents.tools.browser import BrowserCommandPageFetcher
from apartment_agents.tools.http import BlockedPageFallbackFetcher, HttpPageFetcher


logger = get_logger("search")


SUPPORTED_SEARCH_SOURCES = {"boligsiden"}


class SearchPageParser(Protocol):
    source_name: str

    def parse(self, search_url: str, document: str) -> list[ListingSearchResult]: ...


@dataclass(slots=True)
class BoligsidenSearchParser:
    source_name: str = "boligsiden"

    def parse(self, search_url: str, document: str) -> list[ListingSearchResult]:
        try:
            return self._parse_fixture_payload(search_url, document)
        except ListingIngestionError:
            return self._parse_visible_html(search_url, document)

    def _parse_fixture_payload(self, search_url: str, document: str) -> list[ListingSearchResult]:
        match = re.search(
            r'<script id="search-fixture" type="application/json">\s*(\{.*?\})\s*</script>',
            document,
            re.DOTALL,
        )
        if not match:
            raise ListingIngestionError("Search fixture JSON not found in HTML document")
        payload = json.loads(unescape(match.group(1)))
        return [self._result_from_payload(search_url, item) for item in payload.get("results", [])]

    def _result_from_payload(
        self, search_url: str, payload: dict[str, object]
    ) -> ListingSearchResult:
        listing_id = str(payload["listing_id"])
        url = str(payload["url"])
        address_payload = payload["address"]
        if not isinstance(address_payload, dict):
            raise ListingIngestionError("Search result address payload is invalid.")
        title = str(payload.get("title") or address_payload["street"])
        return ListingSearchResult(
            listing_id=listing_id,
            source=str(payload.get("source", self.source_name)),
            url=url,
            title=title,
            address=Address(**address_payload),
            asking_price_dkk=_optional_int(payload.get("asking_price_dkk")),
            area_sqm=_optional_float(payload.get("area_sqm")),
            rooms=_optional_float(payload.get("rooms")),
            owner_cost_monthly_dkk=_optional_int(payload.get("owner_cost_monthly_dkk")),
            raw_payload={
                "source_document": "search_fixture",
                "search_url": search_url,
            },
            citations=[
                SourceCitation(
                    source_id=f"{listing_id}-search",
                    label="Boligsiden search fixture",
                    locator=search_url,
                    snippet=title,
                )
            ],
        )

    def _parse_visible_html(self, search_url: str, document: str) -> list[ListingSearchResult]:
        text = _collapse_whitespace(_strip_tags(document))
        _raise_if_blocked_page(text)
        results = []
        seen_urls = set()
        for match in re.finditer(
            r'<a\b[^>]*href=["\'](?P<href>[^"\']*/adresse/[^"\']+)["\'][^>]*>'
            r"(?P<body>.*?)</a>",
            document,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            url = urljoin(search_url, unescape(match.group("href")))
            if url in seen_urls:
                continue
            seen_urls.add(url)
            block = _collapse_whitespace(_strip_tags(match.group("body")))
            if not block:
                continue
            results.append(self._result_from_visible_block(search_url, url, block))

        if not results:
            raise ListingIngestionError("No apartment search result links found in search HTML.")
        return results

    def _result_from_visible_block(
        self, search_url: str, url: str, block: str
    ) -> ListingSearchResult:
        address = _parse_address(block)
        listing_id = url.rstrip("/").split("/")[-1]
        return ListingSearchResult(
            listing_id=listing_id,
            source=self.source_name,
            url=url,
            title=address.street,
            address=address,
            asking_price_dkk=_extract_int(
                block,
                [
                    r"(\d[\d\.]+)\s*kr\.",
                    r"Kontantpris\s*(\d[\d\.]+)\s*kr",
                    r"Pris\s*(\d[\d\.]+)\s*kr",
                ],
                required=False,
            ),
            area_sqm=_extract_float(
                block,
                [
                    r"(\d+(?:[,.]\d+)?)\s*m[²2]",
                    r"Boligareal\s*(\d+(?:[,.]\d+)?)",
                ],
                required=False,
            ),
            rooms=_extract_float(
                block,
                [r"(\d+(?:[,.]\d+)?)\s+værelser", r"Rum\s*(\d+(?:[,.]\d+)?)"],
                required=False,
            ),
            owner_cost_monthly_dkk=_extract_int(
                block,
                [r"Ejerudgift\s*(\d[\d\.]+)\s*kr"],
                required=False,
            ),
            raw_payload={
                "source_document": "search_visible_html",
                "search_url": search_url,
            },
            citations=[
                SourceCitation(
                    source_id=f"{listing_id}-search",
                    label="Boligsiden search page",
                    locator=search_url,
                    snippet=block[:240],
                )
            ],
        )


@dataclass(slots=True)
class ListingSearchService:
    fixture_store: FixtureStore
    config: AppConfig | None = None
    fetcher: HttpPageFetcher | None = None
    parsers: dict[str, SearchPageParser] | None = None

    def __post_init__(self) -> None:
        self.parsers = self.parsers or {"boligsiden": BoligsidenSearchParser()}
        self.fetcher = self.fetcher or self._build_fetcher()

    def search(self, criteria: ListingSearchCriteria) -> ListingSearchRun:
        criteria = self._normalize_criteria(criteria)
        parser = self._parser_for(criteria.source)
        search_url = criteria.search_url or self._build_search_url(criteria)

        document_source = "fixture"
        if self.config and self.config.enable_live_listing_fetch:
            log_kv(
                logger,
                20,
                "listing_search_live_fetch_started",
                city=criteria.city,
                source=criteria.source,
                url=search_url,
            )
            document = self.fetcher.fetch_text(search_url)
            document_source = "live_fetch"
        else:
            try:
                document = self.fixture_store.load_search_document(
                    source=criteria.source,
                    city=criteria.city,
                    property_type=criteria.property_type,
                )
            except FixtureNotFoundError as exc:
                raise ListingIngestionError(
                    "No search fixture matched the criteria and live listing fetch is disabled."
                ) from exc

        parsed_results = parser.parse(search_url, document)
        results = self._filter_results(criteria, parsed_results)
        for result in results:
            result.raw_payload["ingestion_source"] = document_source
        run = ListingSearchRun(
            search_id=self._new_search_id(criteria),
            criteria=criteria,
            results=results[: criteria.max_results],
        )
        log_kv(
            logger,
            20,
            "listing_search_completed",
            city=criteria.city,
            source=criteria.source,
            result_count=len(run.results),
            search_id=run.search_id,
        )
        return run

    def _normalize_criteria(self, criteria: ListingSearchCriteria) -> ListingSearchCriteria:
        city = criteria.city.strip()
        if not city:
            raise ListingIngestionError("Search city is required.")
        if criteria.source not in SUPPORTED_SEARCH_SOURCES:
            raise ListingIngestionError(
                f"Unsupported search source: {criteria.source}. Supported sources: boligsiden"
            )
        if criteria.max_results <= 0:
            raise ListingIngestionError("Search max_results must be positive.")
        return replace(
            criteria,
            city=city,
            property_type=criteria.property_type.strip() or "ejerlejlighed",
            query=criteria.query.strip() if criteria.query else None,
            max_results=min(criteria.max_results, 100),
        )

    def _parser_for(self, source: str) -> SearchPageParser:
        assert self.parsers is not None
        try:
            return self.parsers[source]
        except KeyError as exc:
            raise ListingIngestionError(
                f"No search parser configured for source: {source}"
            ) from exc

    def _build_search_url(self, criteria: ListingSearchCriteria) -> str:
        search_text = criteria.city if not criteria.query else f"{criteria.city} {criteria.query}"
        property_path = "ejerlejlighed" if criteria.property_type == "ejerlejlighed" else ""
        path = f"/tilsalg/{property_path}".rstrip("/")
        return f"https://www.boligsiden.dk{path}?search={quote_plus(search_text)}"

    def _filter_results(
        self, criteria: ListingSearchCriteria, results: list[ListingSearchResult]
    ) -> list[ListingSearchResult]:
        filtered = []
        for result in results:
            if criteria.city.lower() not in result.address.city.lower():
                continue
            if criteria.min_price_dkk is not None and (
                result.asking_price_dkk is None or result.asking_price_dkk < criteria.min_price_dkk
            ):
                continue
            if criteria.max_price_dkk is not None and (
                result.asking_price_dkk is None or result.asking_price_dkk > criteria.max_price_dkk
            ):
                continue
            if criteria.min_area_sqm is not None and (
                result.area_sqm is None or result.area_sqm < criteria.min_area_sqm
            ):
                continue
            if criteria.max_area_sqm is not None and (
                result.area_sqm is None or result.area_sqm > criteria.max_area_sqm
            ):
                continue
            if criteria.min_rooms is not None and (
                result.rooms is None or result.rooms < criteria.min_rooms
            ):
                continue
            filtered.append(result)
        return filtered

    def _new_search_id(self, criteria: ListingSearchCriteria) -> str:
        generated_at = datetime.now(timezone.utc).isoformat()
        slug = _slugify(criteria.city)
        fingerprint = hashlib.sha1(
            f"{criteria.source}:{criteria.property_type}:{criteria.query}:{generated_at}".encode()
        ).hexdigest()[:10]
        return f"{slug}-{fingerprint}"

    def _build_fetcher(self):
        timeout_seconds = self.config.http_timeout_seconds if self.config else 20
        primary = HttpPageFetcher(timeout_seconds=timeout_seconds)
        if self.config and self.config.enable_browser_listing_fetch:
            browser_fetcher = BrowserCommandPageFetcher(
                command_template=self.config.browser_listing_fetch_command or "",
                timeout_seconds=self.config.browser_fetch_timeout_seconds,
                storage_state_path=self.config.browser_storage_state_path,
            )
            return BlockedPageFallbackFetcher(
                primary=primary,
                blocked_fallback=browser_fetcher,
            )
        return primary


def _parse_address(text: str) -> Address:
    match = re.search(
        r"(?P<street>.+?)\s+(?P<postal>\d{4})\s+(?P<city>[A-Za-zÆØÅæøå .-]+)"
        r"(?:\s+Ejerlejlighed|\s+\d[\d\.]+\s*kr\.|$)",
        text,
    )
    if not match:
        raise ListingIngestionError("Could not extract search result address.")
    city = match.group("city").strip()
    return Address(
        street=match.group("street").strip(" ,"),
        postal_code=match.group("postal"),
        city=city,
        municipality=city,
    )


def _extract_int(text: str, patterns: list[str], required: bool = True) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1).replace(".", ""))
    if required:
        raise ListingIngestionError(
            f"Could not extract required integer field from text: {patterns}"
        )
    return None


def _extract_float(text: str, patterns: list[str], required: bool = True) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(".", "").replace(",", "."))
    if required:
        raise ListingIngestionError(
            f"Could not extract required numeric field from text: {patterns}"
        )
    return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _strip_tags(document: str) -> str:
    without_head = re.sub(r"<head\b.*?</head>", " ", document, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<[^>]+>", " ", unescape(without_head))


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _raise_if_blocked_page(text: str) -> None:
    normalized = text.lower()
    blocked_markers = (
        "checking if the site connection is secure",
        "enable javascript and cookies",
        "access denied",
        "cloudflare",
        "captcha",
    )
    if any(marker in normalized for marker in blocked_markers):
        raise ListingIngestionError("Blocked search page detected before extraction.")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "search"
