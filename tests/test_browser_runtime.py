import unittest
from io import StringIO
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


if __name__ == "__main__":
    unittest.main()
