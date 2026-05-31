from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Protocol
from urllib.parse import urlparse

from apartment_agents.app.errors import ListingIngestionError
from apartment_agents.models import Address, Listing, SourceCitation


class ListingParser(Protocol):
    source_name: str

    def parse(self, url: str, document: str) -> Listing: ...


@dataclass(slots=True)
class HtmlListingParser:
    source_name: str

    def parse(self, url: str, document: str) -> Listing:
        payload = self._extract_listing_payload(document)
        citations = [
            SourceCitation(
                source_id=f"{payload['listing_id']}-html",
                label=f"{self.source_name} listing fixture",
                locator=url,
                snippet=payload.get("citation_snippet"),
            )
        ]
        return Listing(
            listing_id=payload["listing_id"],
            source=self.source_name,
            url=url,
            address=Address(**payload["address"]),
            asking_price_dkk=int(payload["asking_price_dkk"]),
            area_sqm=float(payload["area_sqm"]),
            rooms=float(payload["rooms"]) if payload.get("rooms") is not None else None,
            owner_cost_monthly_dkk=payload.get("owner_cost_monthly_dkk"),
            build_year=payload.get("build_year"),
            floor_label=payload.get("floor_label"),
            balcony=payload.get("balcony"),
            elevator=payload.get("elevator"),
            energy_label=payload.get("energy_label"),
            raw_payload={"source_document": "html_fixture", "extracted_payload": payload},
            citations=citations,
        )

    def _extract_listing_payload(self, document: str) -> dict[str, object]:
        match = re.search(
            r'<script id="listing-fixture" type="application/json">\s*(\{.*?\})\s*</script>',
            document,
            re.DOTALL,
        )
        if not match:
            raise ListingIngestionError("Listing fixture JSON not found in HTML document")
        return json.loads(unescape(match.group(1)))


class BoligsidenParser(HtmlListingParser):
    LIVE_HTML_FIELDS = (
        "address",
        "asking_price_dkk",
        "area_sqm",
        "rooms",
        "owner_cost_monthly_dkk",
        "build_year",
        "elevator",
        "balcony",
    )

    def __init__(self) -> None:
        super().__init__(source_name="boligsiden")

    def parse(self, url: str, document: str) -> Listing:
        try:
            return super().parse(url, document)
        except ListingIngestionError:
            return self._parse_visible_html(url, document)

    def _parse_visible_html(self, url: str, document: str) -> Listing:
        text = self._collapse_whitespace(self._strip_tags(document))

        address_match = re.search(
            r"#?\s*([^#]+?)\s*(\d{4})\s+([A-Za-zÆØÅæøå .-]+)\s+Ejerlejlighed",
            text,
        )
        if not address_match:
            raise ListingIngestionError("Could not extract address from Boligsiden HTML.")

        address_line = address_match.group(1).strip()
        postal_code = address_match.group(2).strip()
        city = address_match.group(3).strip()

        price = self._extract_int(text, [r"(\d[\d\.]+)\s*kr\.", r"Til salg:\s*(\d[\d\.]+)\s*kr"])
        area_sqm = self._extract_float(text, [r"Boligareal:\s*(\d+)\s*m²"])
        rooms = self._extract_float(text, [r"(\d+)\s+værelser"], required=False)
        owner_cost = self._extract_int(text, [r"Ejerudgift\s*(\d[\d\.]+)\s*kr/md"], required=False)
        build_year = self._extract_int(text, [r"\b(18\d{2}|19\d{2}|20\d{2})\b"], required=False)
        elevator = self._extract_bool(text, "Elevator")
        balcony = self._extract_bool(text, "Altan")
        extracted_fields = ["address", "asking_price_dkk", "area_sqm"]
        missing_fields = []
        for field_name, value in {
            "rooms": rooms,
            "owner_cost_monthly_dkk": owner_cost,
            "build_year": build_year,
            "elevator": elevator,
            "balcony": balcony,
        }.items():
            if value is None:
                missing_fields.append(field_name)
            else:
                extracted_fields.append(field_name)
        field_coverage_ratio = round(len(extracted_fields) / len(self.LIVE_HTML_FIELDS), 2)
        extraction_warnings = []
        if missing_fields:
            extraction_warnings.append(
                "Live HTML fallback could not extract all expected Boligsiden fields."
            )

        parsed = urlparse(url)
        street = address_line
        municipality = city
        listing_id = parsed.path.rstrip("/").split("/")[-1]

        return Listing(
            listing_id=listing_id,
            source=self.source_name,
            url=url,
            address=Address(
                street=street,
                postal_code=postal_code,
                city=city,
                municipality=municipality,
            ),
            asking_price_dkk=price,
            area_sqm=area_sqm,
            rooms=rooms,
            owner_cost_monthly_dkk=owner_cost,
            build_year=build_year,
            balcony=balcony,
            elevator=elevator,
            raw_payload={
                "source_document": "live_html_text",
                "extraction_method": "visible_html_regex",
                "extracted_fields": extracted_fields,
                "missing_fields": missing_fields,
                "field_coverage_ratio": field_coverage_ratio,
                "warnings": extraction_warnings,
            },
            citations=[
                SourceCitation(
                    source_id=f"{listing_id}-html",
                    label="Boligsiden listing page (live HTML fallback)",
                    locator=url,
                    snippet=text[:240],
                )
            ],
        )

    def _strip_tags(self, document: str) -> str:
        without_head = re.sub(r"<head\b.*?</head>", " ", document, flags=re.DOTALL | re.IGNORECASE)
        return re.sub(r"<[^>]+>", " ", unescape(without_head))

    def _collapse_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _extract_int(self, text: str, patterns: list[str], required: bool = True) -> int | None:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1).replace(".", ""))
        if required:
            raise ListingIngestionError(
                f"Could not extract required integer field from text: {patterns}"
            )
        return None

    def _extract_float(self, text: str, patterns: list[str], required: bool = True) -> float | None:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1).replace(".", "").replace(",", "."))
        if required:
            raise ListingIngestionError(
                f"Could not extract required numeric field from text: {patterns}"
            )
        return None

    def _extract_bool(self, text: str, label: str) -> bool | None:
        match = re.search(rf"{label}:\s*(Ja|Nej)", text)
        if not match:
            return None
        return match.group(1) == "Ja"


class EstateParser(HtmlListingParser):
    def __init__(self) -> None:
        super().__init__(source_name="estate_agent")
