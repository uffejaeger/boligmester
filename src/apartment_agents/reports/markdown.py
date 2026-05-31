from __future__ import annotations

from pathlib import Path

from apartment_agents.finance.models import FinanceResult
from apartment_agents.models import AnalysisReport


def render_report_markdown(report: AnalysisReport, finance_result: FinanceResult) -> str:
    lines = [
        "# Apartment Analysis Report",
        "",
        f"Recommendation: **{report.recommendation.value}**",
        "",
        "## Listing",
        "",
        f"- Address: {report.listing.address.street}, {report.listing.address.postal_code} {report.listing.address.city}",
        f"- Asking price: {report.listing.asking_price_dkk:,} DKK",
        f"- Area: {report.listing.area_sqm} sqm",
        f"- Rooms: {report.listing.rooms if report.listing.rooms is not None else 'n/a'}",
    ]
    extraction_method = report.listing.raw_payload.get("extraction_method")
    if extraction_method:
        lines.append(f"- Extraction method: {extraction_method}")
    field_coverage = report.listing.raw_payload.get("field_coverage_ratio")
    if field_coverage is not None:
        lines.append(f"- Listing field coverage: {field_coverage}")
    missing_fields = report.listing.raw_payload.get("missing_fields", [])
    if missing_fields:
        lines.append(f"- Missing extracted fields: {', '.join(str(item) for item in missing_fields)}")
    lines.extend(
        [
            "",
            "## Affordability",
            "",
            f"- Approval likelihood: {finance_result.approval_likelihood}",
            f"- Debt factor: {finance_result.debt_factor}",
            f"- Monthly housing cost: {finance_result.housing_cost_monthly_dkk:,} DKK",
            f"- Safe maximum purchase price: {finance_result.maximum_safe_purchase_price_dkk:,} DKK",
            "",
            "## Findings",
            "",
        ]
    )

    for finding in report.findings:
        lines.append(f"### {finding.agent_name}")
        lines.append("")
        lines.append(finding.summary)
        lines.append("")
        if finding.details:
            for key, value in finding.details.items():
                lines.append(f"- {key}: {value}")
        if finding.warnings:
            lines.append("- warnings:")
            for warning in finding.warnings:
                lines.append(f"  - {warning}")
        if finding.citations:
            lines.append("- citations:")
            for citation in finding.citations:
                lines.append(f"  - {citation.label}: {citation.locator}")
        lines.append("")

    lines.extend(
        [
            "## Assumptions",
            "",
            *[f"- {item}" for item in report.assumptions],
            "",
            "## Unresolved Questions",
            "",
            *[f"- {item}" for item in report.unresolved_questions],
            "",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def report_file_path(output_dir: Path, report_id: str) -> Path:
    return output_dir / f"{report_id}.md"
