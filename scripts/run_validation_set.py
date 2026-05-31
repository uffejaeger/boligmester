from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from apartment_agents.app.services import AnalyzeApartmentService
from apartment_agents.config import AppConfig
from apartment_agents.validation.harness import (
    ValidationHarness,
    batch_report_to_json,
    build_batch_report,
    load_url_file,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a listing URL validation set through the analysis service."
    )
    parser.add_argument("url_file", help="Path to a text file with one listing URL per line.")
    parser.add_argument(
        "--buyer-profile-id",
        default="solo_engineer",
        help="Buyer profile fixture id to use for the validation run.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to write the JSON validation summary.",
    )
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Print the full JSON batch report to stdout after writing it.",
    )
    parser.add_argument(
        "--log-level",
        default="ERROR",
        help="Runtime log level for the validation run. Default keeps JSON output clean.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    os.environ["LOG_LEVEL"] = args.log_level
    config = AppConfig.load()
    service = AnalyzeApartmentService(config=config)
    harness = ValidationHarness(service)
    url_file = Path(args.url_file)
    results = harness.run_urls(
        urls=load_url_file(url_file),
        buyer_profile_id=args.buyer_profile_id,
    )
    batch_report = build_batch_report(
        results,
        buyer_profile_id=args.buyer_profile_id,
        input_label=str(url_file),
    )
    payload = batch_report_to_json(batch_report)
    output_path = Path(args.output_json) if args.output_json else default_output_path(
        config.output_dir,
        url_file,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")
    if args.stdout_json:
        sys.stdout.write(payload)
    else:
        summary = batch_report.summary
        print(str(output_path))
        print(
            f"total={summary.total} status_counts={summary.status_counts} "
            f"recommendation_counts={summary.recommendation_counts}"
        )
    return 0


def default_output_path(output_dir: Path, url_file: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return output_dir / "validation" / f"{url_file.stem}_{timestamp}.json"


if __name__ == "__main__":
    raise SystemExit(main())
