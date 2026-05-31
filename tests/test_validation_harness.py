import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from apartment_agents.app.errors import ListingFetchBlockedError
from apartment_agents.app.services import AnalyzeApartmentRequest, AnalyzeApartmentService
from apartment_agents.config import AppConfig
from apartment_agents.validation.harness import (
    ValidationHarness,
    build_batch_report,
    load_url_file,
    results_to_json,
    summarize_results,
)
from scripts.run_validation_set import main


class ValidationHarnessTest(unittest.TestCase):
    def test_run_url_classifies_fixture_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
            )
            harness = ValidationHarness(service)

            result = harness.run_url(
                "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c",
                buyer_profile_id="solo_engineer",
            )

        self.assertEqual(result.status, "fixture")
        self.assertEqual(result.recommendation, "BUY")
        self.assertEqual(result.source_document, "html_fixture")

    def test_run_url_classifies_imported_capture_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AnalyzeApartmentService(
                config=AppConfig(output_dir=Path(tmpdir), adk_backend="mock"),
            )
            harness = ValidationHarness(service)

            result = harness.run_url(
                "https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c-07510157___21___3____th",
                buyer_profile_id="solo_engineer",
            )

        self.assertEqual(result.status, "imported_capture")
        self.assertEqual(result.extraction_method, "visible_html_regex")

    def test_run_url_classifies_blocked_listing_fetch(self) -> None:
        class BlockingService:
            def analyze(self, request: AnalyzeApartmentRequest):
                raise ListingFetchBlockedError("blocked by challenge")

        harness = ValidationHarness(BlockingService())  # type: ignore[arg-type]
        result = harness.run_url(
            "https://www.boligsiden.dk/adresse/blocked",
            buyer_profile_id="solo_engineer",
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.error_type, "ListingFetchBlockedError")

    def test_load_url_file_ignores_comments_and_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "urls.txt"
            path.write_text(
                "# comment\n\nhttps://example.com/1\n  https://example.com/2  \n",
                encoding="utf-8",
            )

            urls = load_url_file(path)

        self.assertEqual(urls, ["https://example.com/1", "https://example.com/2"])

    def test_results_to_json_serializes_result_list(self) -> None:
        payload = results_to_json(
            [
                ValidationHarnessTest._result(
                    url="https://example.com/1",
                    status="blocked",
                    error_type="ListingFetchBlockedError",
                )
            ]
        )
        parsed = json.loads(payload)

        self.assertEqual(parsed[0]["status"], "blocked")

    def test_summarize_results_counts_statuses_and_recommendations(self) -> None:
        summary = summarize_results(
            [
                ValidationHarnessTest._result(
                    url="https://example.com/1",
                    status="fixture",
                    recommendation="BUY",
                    field_coverage_ratio=1.0,
                ),
                ValidationHarnessTest._result(
                    url="https://example.com/2",
                    status="ingestion_error",
                ),
                ValidationHarnessTest._result(
                    url="https://example.com/3",
                    status="imported_capture",
                    recommendation="MAYBE",
                    field_coverage_ratio=0.5,
                ),
            ]
        )

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.status_counts["fixture"], 1)
        self.assertEqual(summary.status_counts["ingestion_error"], 1)
        self.assertEqual(summary.recommendation_counts["BUY"], 1)
        self.assertEqual(summary.average_field_coverage_ratio, 0.75)

    def test_build_batch_report_includes_summary(self) -> None:
        report = build_batch_report(
            [
                ValidationHarnessTest._result(
                    url="https://example.com/1",
                    status="fixture",
                    recommendation="BUY",
                )
            ],
            buyer_profile_id="solo_engineer",
            input_label="examples/validation/aarhus_urls.txt",
        )

        self.assertEqual(report.buyer_profile_id, "solo_engineer")
        self.assertEqual(report.summary.total, 1)

    def test_validation_cli_persists_timestamped_output_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            url_file = Path(tmpdir) / "urls.txt"
            url_file.write_text(
                "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c\n",
                encoding="utf-8",
            )
            with (
                patch.dict(
                    os.environ,
                    {
                        "ADK_BACKEND": "mock",
                        "REPORT_OUTPUT_DIR": str(output_dir),
                        "LOG_LEVEL": "ERROR",
                    },
                    clear=False,
                ),
                patch("sys.stdout", new_callable=StringIO) as stdout,
            ):
                exit_code = main([str(url_file), "--buyer-profile-id", "solo_engineer"])

            validation_dir = output_dir / "validation"
            written = sorted(validation_dir.glob("urls_*.json"))

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(written), 1)
            self.assertIn(str(written[0]), stdout.getvalue())

    def test_validation_cli_can_print_full_json_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            url_file = Path(tmpdir) / "urls.txt"
            url_file.write_text(
                "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c\n",
                encoding="utf-8",
            )
            explicit_output = Path(tmpdir) / "report.json"
            with (
                patch.dict(
                    os.environ,
                    {
                        "ADK_BACKEND": "mock",
                        "REPORT_OUTPUT_DIR": str(output_dir),
                        "LOG_LEVEL": "ERROR",
                    },
                    clear=False,
                ),
                patch("sys.stdout", new_callable=StringIO) as stdout,
            ):
                exit_code = main(
                    [
                        str(url_file),
                        "--buyer-profile-id",
                        "solo_engineer",
                        "--output-json",
                        str(explicit_output),
                        "--stdout-json",
                    ]
                )

            payload = json.loads(stdout.getvalue())

            self.assertEqual(exit_code, 0)
            self.assertTrue(explicit_output.exists())
            self.assertEqual(payload["summary"]["total"], 1)

    @staticmethod
    def _result(**kwargs):
        from apartment_agents.validation.harness import ValidationRunResult

        return ValidationRunResult(**kwargs)


if __name__ == "__main__":
    unittest.main()
