from __future__ import annotations

from pathlib import Path

from apartment_agents.models import ApartmentComparison, ApartmentComparisonItem


def render_comparison_markdown(comparison: ApartmentComparison) -> str:
    lines = [
        "# Apartment Comparison",
        "",
        comparison.summary,
        "",
        f"- Buyer profile: {comparison.buyer_profile_id}",
        f"- Recommended saved id: {comparison.recommended_saved_id or 'n/a'}",
        f"- Compared apartments: {len(comparison.items)}",
        "",
        "## Overview",
        "",
        ("| Apartment | Price | Area | Price/m2 | Approval | Monthly housing | Safe gap |"),
        "| --- | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for item in comparison.items:
        lines.append(
            "| "
            f"{item.title} | "
            f"{_format_optional_dkk(item.asking_price_dkk)} | "
            f"{_format_optional_sqm(item.area_sqm)} | "
            f"{_format_optional_dkk(item.price_per_sqm_dkk)} | "
            f"{item.approval_likelihood or 'n/a'} | "
            f"{_format_optional_dkk(item.monthly_housing_cost_dkk)} | "
            f"{_format_optional_dkk(item.safe_purchase_price_gap_dkk)} |"
        )

    lines.extend(["", "## Apartment Details", ""])
    for item in comparison.items:
        lines.extend(_item_lines(item))

    return "\n".join(lines).rstrip() + "\n"


def comparison_file_path(output_dir: Path, comparison_id: str) -> Path:
    return output_dir / f"{comparison_id}.md"


def _item_lines(item: ApartmentComparisonItem) -> list[str]:
    lines = [
        f"### {item.title}",
        "",
        f"- Saved id: {item.saved_id}",
        f"- URL: {item.url}",
        f"- Address: {item.address.street}, {item.address.postal_code} {item.address.city}",
        f"- Asking price: {_format_optional_dkk(item.asking_price_dkk)}",
        f"- Area: {_format_optional_sqm(item.area_sqm)}",
        f"- Rooms: {_format_optional_float(item.rooms)}",
        f"- Owner cost: {_format_optional_dkk(item.owner_cost_monthly_dkk)}",
        f"- Finance approval: {item.approval_likelihood or 'n/a'}",
        f"- Debt factor: {_format_optional_float(item.debt_factor)}",
        f"- Monthly housing cost: {_format_optional_dkk(item.monthly_housing_cost_dkk)}",
        f"- Safe purchase price gap: {_format_optional_dkk(item.safe_purchase_price_gap_dkk)}",
        "",
        "Tradeoffs:",
        "",
    ]
    lines.extend(f"- {tradeoff}" for tradeoff in item.tradeoffs)
    if not item.tradeoffs:
        lines.append("- No material tradeoffs surfaced from available structured fields.")

    lines.extend(["", "Missing evidence:", ""])
    lines.extend(f"- {evidence}" for evidence in item.missing_evidence)
    if not item.missing_evidence:
        lines.append("- No missing evidence flagged in the saved apartment fields.")
    lines.append("")
    return lines


def _format_optional_dkk(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,}".replace(",", ".") + " DKK"


def _format_optional_sqm(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:g} m2"


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:g}"
