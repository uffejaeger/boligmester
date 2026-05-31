import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apartment_agents.config import AppConfig
from apartment_agents.models import ListingSearchCriteria
from apartment_agents.storage.fixtures import FixtureStore
from apartment_agents.tools.search import BoligsidenSearchParser, ListingSearchService


class ListingSearchServiceTest(unittest.TestCase):
    def test_search_uses_fixture_and_filters_results(self) -> None:
        service = ListingSearchService(FixtureStore())

        run = service.search(
            ListingSearchCriteria(
                city="Aarhus C",
                max_price_dkk=3700000,
                min_area_sqm=50,
                max_results=10,
            )
        )

        self.assertEqual(run.criteria.city, "Aarhus C")
        self.assertEqual(len(run.results), 2)
        self.assertEqual(run.results[0].address.city, "Aarhus C")
        self.assertEqual(run.results[0].raw_payload["ingestion_source"], "fixture")
        self.assertEqual(run.results[0].price_per_sqm_dkk, 43355)

    def test_parser_extracts_visible_search_html(self) -> None:
        parser = BoligsidenSearchParser()
        html = """
        <html><body>
          <a href="/adresse/odensegade-21-3-th-8000-aarhus-c">
            Odensegade 21, 3. th. 8000 Aarhus C Ejerlejlighed
            3.698.000 kr. 51 m² 2 værelser Ejerudgift 2.620 kr
          </a>
        </body></html>
        """

        results = parser.parse("https://www.boligsiden.dk/tilsalg/ejerlejlighed", html)

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0].url, "https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c"
        )
        self.assertEqual(results[0].asking_price_dkk, 3698000)
        self.assertEqual(results[0].area_sqm, 51)
        self.assertEqual(results[0].rooms, 2)

    def test_live_search_fetches_when_enabled(self) -> None:
        class SearchFetcher:
            def fetch_text(self, url: str) -> str:
                self.url = url
                return """
                <html><body>
                  <a href="https://www.boligsiden.dk/adresse/skovvejen-44-2-tv-8000-aarhus-c">
                    Skovvejen 44, 2. tv. 8000 Aarhus C Ejerlejlighed
                    4.495.000 kr. 89 m² 3 værelser
                  </a>
                </body></html>
                """

        with TemporaryDirectory() as tmpdir:
            fetcher = SearchFetcher()
            service = ListingSearchService(
                FixtureStore(),
                config=AppConfig(
                    output_dir=Path(tmpdir),
                    adk_backend="mock",
                    enable_live_listing_fetch=True,
                ),
                fetcher=fetcher,  # type: ignore[arg-type]
            )

            run = service.search(ListingSearchCriteria(city="Aarhus C", max_results=5))

        self.assertEqual(len(run.results), 1)
        self.assertEqual(run.results[0].raw_payload["ingestion_source"], "live_fetch")
        self.assertIn("search=Aarhus+C", fetcher.url)


if __name__ == "__main__":
    unittest.main()
