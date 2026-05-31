from __future__ import annotations

import argparse
from pathlib import Path

from apartment_agents.captured.importer import CapturedListingImporter


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a captured listing HTML file into examples/captured_listings."
    )
    parser.add_argument("url", help="Listing URL the captured HTML belongs to.")
    parser.add_argument("html_path", help="Path to the captured HTML file.")
    parser.add_argument(
        "--document-name",
        help="Optional destination file name inside examples/captured_listings.",
    )
    parser.add_argument(
        "--root",
        default="examples",
        help="Fixture root directory. Defaults to examples.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    importer = CapturedListingImporter(root=Path(args.root))
    result = importer.import_html(
        url=args.url,
        source_html_path=Path(args.html_path),
        document_name=args.document_name,
    )
    print(str(result.document_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
