import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apartment_agents.app.errors import (
    ListingFetchBlockedError,
    ListingIngestionError,
    UnsupportedListingDomainError,
)
from apartment_agents.config import AppConfig
from apartment_agents.storage.fixtures import FixtureStore
from apartment_agents.tools.listing_parsers import BoligsidenParser
from apartment_agents.tools.listings import ListingIngestionService

REGRESSION_FIXTURE_ROOT = Path("examples/listing_regressions")


class ListingIngestionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ListingIngestionService(FixtureStore())

    def test_parses_supported_boligsiden_fixture(self) -> None:
        listing = self.service.parse_listing_url(
            "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c"
        )

        self.assertEqual(listing.source, "boligsiden")
        self.assertEqual(listing.address.city, "Aarhus C")
        self.assertEqual(listing.raw_payload["ingestion_source"], "fixture")

    def test_parses_imported_captured_listing_before_live_fetch(self) -> None:
        listing = self.service.parse_listing_url(
            "https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c-07510157___21___3____th"
        )

        self.assertEqual(listing.address.street, "Odensegade 21, 3. th.")
        self.assertEqual(listing.asking_price_dkk, 3698000)
        self.assertEqual(listing.raw_payload["ingestion_source"], "captured_listing")

    def test_prefer_captured_mode_uses_capture_before_fixture(self) -> None:
        service = ListingIngestionService(
            FixtureStore(),
            prefer_captured_listings=True,
        )

        listing = service.parse_listing_url(
            "https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c-07510157___21___3____th"
        )

        self.assertEqual(listing.raw_payload["ingestion_source"], "captured_listing")

    def test_rejects_unsupported_domain(self) -> None:
        with self.assertRaises(UnsupportedListingDomainError):
            self.service.parse_listing_url("https://example.com/apartment/123")

    def test_boligsiden_parser_can_extract_from_visible_html(self) -> None:
        parser = BoligsidenParser()
        html = """
        <html><body>
        <h1>Odensegade 21, 3. th. 8000 Aarhus C Ejerlejlighed</h1>
        <div>Til salg: 3.698.000 kr.</div>
        <div>Boligareal: 51 m²</div>
        <div>2 værelser</div>
        <div>Ejerudgift 2.620 kr/md</div>
        <div>1903</div>
        <div>Elevator: Nej</div>
        <div>Altan: Ja</div>
        </body></html>
        """

        listing = parser.parse(
            "https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c", html
        )

        self.assertEqual(listing.asking_price_dkk, 3698000)
        self.assertEqual(listing.owner_cost_monthly_dkk, 2620)
        self.assertEqual(listing.address.city, "Aarhus C")
        self.assertTrue(listing.balcony)
        self.assertEqual(listing.raw_payload["field_coverage_ratio"], 1.0)
        self.assertEqual(listing.raw_payload["missing_fields"], [])

    def test_boligsiden_parser_records_missing_live_html_fields(self) -> None:
        parser = BoligsidenParser()
        html = """
        <html><body>
        <h1>Odensegade 21, 3. th. 8000 Aarhus C Ejerlejlighed</h1>
        <div>Til salg: 3.698.000 kr.</div>
        <div>Boligareal: 51 m²</div>
        </body></html>
        """

        listing = parser.parse(
            "https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c", html
        )

        self.assertIsNone(listing.rooms)
        self.assertIn("rooms", listing.raw_payload["missing_fields"])
        self.assertIn("owner_cost_monthly_dkk", listing.raw_payload["missing_fields"])
        self.assertLess(listing.raw_payload["field_coverage_ratio"], 1.0)

    def test_listing_regression_fixtures_cover_layout_and_failure_classes(self) -> None:
        service = ListingIngestionService(FixtureStore())
        manifest = json.loads((REGRESSION_FIXTURE_ROOT / "manifest.json").read_text())
        cases = manifest["cases"]

        self.assertGreaterEqual(len(cases), 5)
        self.assertIn(
            "blocked_page",
            {
                case["expected"].get("failure_class")
                for case in cases
                if case["expected"]["outcome"] == "failure"
            },
        )
        self.assertIn(
            "missing_listing_markup",
            {
                case["expected"].get("failure_class")
                for case in cases
                if case["expected"]["outcome"] == "failure"
            },
        )

        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                parser = service.parsers[case["source"]]
                document = (REGRESSION_FIXTURE_ROOT / case["document"]).read_text(encoding="utf-8")
                expected = case["expected"]

                if expected["outcome"] == "failure":
                    with self.assertRaises(ListingIngestionError) as raised:
                        parser.parse(case["url"], document)
                    self.assertIn(expected["error_contains"], str(raised.exception))
                    continue

                listing = parser.parse(case["url"], document)

                self.assertEqual(listing.source, case["source"])
                self.assertEqual(listing.url, case["url"])
                self.assertEqual(listing.asking_price_dkk, expected["asking_price_dkk"])
                self.assertEqual(listing.area_sqm, expected["area_sqm"])
                self.assertEqual(listing.rooms, expected["rooms"])
                if "field_coverage_ratio" in expected:
                    self.assertEqual(
                        listing.raw_payload["field_coverage_ratio"],
                        expected["field_coverage_ratio"],
                    )
                    self.assertEqual(
                        listing.raw_payload["missing_fields"],
                        expected["missing_fields"],
                    )
                if "source_document" in expected:
                    self.assertEqual(
                        listing.raw_payload["source_document"],
                        expected["source_document"],
                    )

    def test_live_fetch_path_raises_blocked_error_for_cloudflare_page(self) -> None:
        class BlockedFetcher:
            def fetch_text(self, url: str) -> str:
                raise ListingFetchBlockedError("blocked")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "listings").mkdir(parents=True)
            (root / "listings" / "index.json").write_text('{"items": []}', encoding="utf-8")
            (root / "buyers").mkdir(parents=True)
            config = AppConfig(
                output_dir=root / "output",
                adk_backend="mock",
                enable_live_listing_fetch=True,
            )
            service = ListingIngestionService(
                FixtureStore(root=root),
                config=config,
                fetcher=BlockedFetcher(),  # type: ignore[arg-type]
            )

            with self.assertRaises(ListingFetchBlockedError):
                service.parse_listing_url(
                    "https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c"
                )

    def test_live_fetch_path_can_parse_boligsiden_html_when_enabled(self) -> None:
        class HtmlFetcher:
            def fetch_text(self, url: str) -> str:
                return """
                <html><body>
                <h1>Odensegade 21, 3. th. 8000 Aarhus C Ejerlejlighed</h1>
                <div>Til salg: 3.698.000 kr.</div>
                <div>Boligareal: 51 m²</div>
                <div>2 værelser</div>
                <div>Ejerudgift 2.620 kr/md</div>
                <div>1903</div>
                <div>Elevator: Nej</div>
                <div>Altan: Ja</div>
                </body></html>
                """

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "listings").mkdir(parents=True)
            (root / "listings" / "index.json").write_text('{"items": []}', encoding="utf-8")
            (root / "buyers").mkdir(parents=True)
            config = AppConfig(
                output_dir=root / "output",
                adk_backend="mock",
                enable_live_listing_fetch=True,
            )
            service = ListingIngestionService(
                FixtureStore(root=root),
                config=config,
                fetcher=HtmlFetcher(),  # type: ignore[arg-type]
            )

            listing = service.parse_listing_url(
                "https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c"
            )

        self.assertEqual(listing.asking_price_dkk, 3698000)
        self.assertEqual(listing.address.city, "Aarhus C")
        self.assertTrue(listing.balcony)
        self.assertEqual(listing.raw_payload["extraction_method"], "visible_html_regex")

    def test_browser_fetcher_is_configured_when_enabled(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "listings").mkdir(parents=True)
            (root / "listings" / "index.json").write_text('{"items": []}', encoding="utf-8")
            (root / "buyers").mkdir(parents=True)
            config = AppConfig(
                output_dir=root / "output",
                adk_backend="mock",
                enable_live_listing_fetch=True,
                enable_browser_listing_fetch=True,
                browser_listing_fetch_command="python3 script.py {url}",
            )
            from unittest.mock import patch

            with patch("shutil.which", return_value="/usr/bin/python3"):
                service = ListingIngestionService(FixtureStore(root=root), config=config)

        self.assertIsNotNone(service.fetcher)


if __name__ == "__main__":
    unittest.main()
