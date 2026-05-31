import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from apartment_agents.captured.importer import CapturedListingImporter
from scripts.import_captured_listing import main


class CapturedListingImporterTest(unittest.TestCase):
    def test_import_html_creates_manifest_and_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "capture.html"
            source.write_text("<html>captured</html>", encoding="utf-8")

            importer = CapturedListingImporter(root=root)
            result = importer.import_html(
                url="https://www.boligsiden.dk/adresse/test-apartment",
                source_html_path=source,
            )

            index = json.loads(
                (root / "captured_listings" / "index.json").read_text(encoding="utf-8")
            )
            document_exists = result.document_path.exists()

        self.assertFalse(result.replaced_existing)
        self.assertTrue(document_exists)
        self.assertEqual(
            index["items"][0]["url"], "https://www.boligsiden.dk/adresse/test-apartment"
        )
        self.assertEqual(index["items"][0]["document"], "test_apartment_capture.html")

    def test_import_html_reuses_existing_entry_for_same_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            capture_dir = root / "captured_listings"
            capture_dir.mkdir(parents=True)
            (capture_dir / "index.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "url": "https://www.boligsiden.dk/adresse/test-apartment",
                                "document": "existing_capture.html",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            source = root / "capture.html"
            source.write_text("<html>updated</html>", encoding="utf-8")

            importer = CapturedListingImporter(root=root)
            result = importer.import_html(
                url="https://www.boligsiden.dk/adresse/test-apartment",
                source_html_path=source,
            )

            saved = (capture_dir / "existing_capture.html").read_text(encoding="utf-8")

        self.assertTrue(result.replaced_existing)
        self.assertEqual(result.document_name, "existing_capture.html")
        self.assertIn("updated", saved)

    def test_cli_import_prints_destination_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "capture.html"
            source.write_text("<html>captured</html>", encoding="utf-8")

            with patch("sys.stdout", new_callable=StringIO) as stdout:
                exit_code = main(
                    [
                        "https://www.boligsiden.dk/adresse/test-apartment",
                        str(source),
                        "--root",
                        str(root),
                    ]
                )

            output = stdout.getvalue().strip()

        self.assertEqual(exit_code, 0)
        self.assertTrue(output.endswith("captured_listings/test_apartment_capture.html"))


if __name__ == "__main__":
    unittest.main()
