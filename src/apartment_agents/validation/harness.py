from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from apartment_agents.app.errors import ListingFetchBlockedError, ListingIngestionError
from apartment_agents.app.services import AnalyzeApartmentRequest, AnalyzeApartmentService


@dataclass(slots=True)
class ValidationRunResult:
    url: str
    status: str
    recommendation: str | None = None
    report_path: str | None = None
    source_document: str | None = None
    extraction_method: str | None = None
    field_coverage_ratio: float | None = None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class ValidationSummary:
    total: int
    status_counts: dict[str, int]
    recommendation_counts: dict[str, int]
    average_field_coverage_ratio: float | None


@dataclass(slots=True)
class ValidationBatchReport:
    generated_at: str
    buyer_profile_id: str
    input_label: str | None
    listing_source_mode: str
    results: list[ValidationRunResult]
    summary: ValidationSummary


class ValidationHarness:
    def __init__(self, service: AnalyzeApartmentService) -> None:
        self.service = service

    def run_url(self, url: str, buyer_profile_id: str) -> ValidationRunResult:
        try:
            result = self.service.analyze(
                AnalyzeApartmentRequest(
                    listing_url=url,
                    buyer_profile_id=buyer_profile_id,
                )
            )
        except ListingFetchBlockedError as exc:
            return ValidationRunResult(
                url=url,
                status="blocked",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        except ListingIngestionError as exc:
            return ValidationRunResult(
                url=url,
                status="ingestion_error",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        except Exception as exc:
            return ValidationRunResult(
                url=url,
                status="analysis_error",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        raw_payload = result.report.listing.raw_payload
        source_document = raw_payload.get("source_document")
        ingestion_source = raw_payload.get("ingestion_source")
        if ingestion_source == "captured_listing":
            status = "imported_capture"
        elif source_document == "live_html_text":
            status = "live_html"
        elif source_document == "html_fixture":
            status = "fixture"
        else:
            status = "analyzed"

        return ValidationRunResult(
            url=url,
            status=status,
            recommendation=result.report.recommendation.value,
            report_path=str(result.report_path),
            source_document=source_document,
            extraction_method=raw_payload.get("extraction_method"),
            field_coverage_ratio=raw_payload.get("field_coverage_ratio"),
        )

    def run_urls(self, urls: list[str], buyer_profile_id: str) -> list[ValidationRunResult]:
        return [self.run_url(url=url, buyer_profile_id=buyer_profile_id) for url in urls]


def load_url_file(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def summarize_results(results: list[ValidationRunResult]) -> ValidationSummary:
    status_counts: dict[str, int] = {}
    recommendation_counts: dict[str, int] = {}
    coverage_values: list[float] = []
    for result in results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1
        if result.recommendation:
            recommendation_counts[result.recommendation] = (
                recommendation_counts.get(result.recommendation, 0) + 1
            )
        if result.field_coverage_ratio is not None:
            coverage_values.append(float(result.field_coverage_ratio))
    average_field_coverage_ratio = None
    if coverage_values:
        average_field_coverage_ratio = round(sum(coverage_values) / len(coverage_values), 2)
    return ValidationSummary(
        total=len(results),
        status_counts=status_counts,
        recommendation_counts=recommendation_counts,
        average_field_coverage_ratio=average_field_coverage_ratio,
    )


def build_batch_report(
    results: list[ValidationRunResult],
    *,
    buyer_profile_id: str,
    input_label: str | None = None,
    listing_source_mode: str = "default",
) -> ValidationBatchReport:
    return ValidationBatchReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        buyer_profile_id=buyer_profile_id,
        input_label=input_label,
        listing_source_mode=listing_source_mode,
        results=results,
        summary=summarize_results(results),
    )


def results_to_json(results: list[ValidationRunResult]) -> str:
    return json.dumps([asdict(result) for result in results], indent=2, ensure_ascii=True) + "\n"


def batch_report_to_json(report: ValidationBatchReport) -> str:
    return json.dumps(asdict(report), indent=2, ensure_ascii=True) + "\n"
