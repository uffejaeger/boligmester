from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from apartment_agents.app.errors import ListingFetchError


DEFAULT_TIMEOUT_MS = 45_000


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a rendered listing page with Playwright and print HTML to stdout."
    )
    parser.add_argument("url", help="Listing URL to load in the browser.")
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help="Navigation timeout in milliseconds.",
    )
    parser.add_argument(
        "--wait-until",
        default="domcontentloaded",
        choices=["load", "domcontentloaded", "networkidle", "commit"],
        help="Playwright wait strategy for navigation.",
    )
    parser.add_argument(
        "--storage-state",
        help="Optional Playwright storage-state JSON file for session-backed fetches.",
    )
    return parser.parse_args(argv)


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ListingFetchError("Browser runtime requires an absolute http(s) listing URL.")


def fetch_rendered_html(
    url: str,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    wait_until: str = "domcontentloaded",
    storage_state_path: str | Path | None = None,
) -> str:
    validate_url(url)
    if timeout_ms <= 0:
        raise ListingFetchError("Browser runtime timeout must be positive.")
    resolved_storage_state = _resolve_storage_state_path(storage_state_path)
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ListingFetchError(
            "Playwright is not installed. Install the optional browser dependency first."
        ) from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context_kwargs = {}
            if resolved_storage_state is not None:
                context_kwargs["storage_state"] = str(resolved_storage_state)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            html = page.content()
            context.close()
            browser.close()
            return html
    except PlaywrightError as exc:
        raise ListingFetchError(f"Playwright could not render the listing page: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        html = fetch_rendered_html(
            args.url,
            timeout_ms=args.timeout_ms,
            wait_until=args.wait_until,
            storage_state_path=args.storage_state,
        )
    except ListingFetchError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    sys.stdout.write(html)
    return 0


def _resolve_storage_state_path(storage_state_path: str | Path | None) -> Path | None:
    value = storage_state_path or os.getenv("BROWSER_STORAGE_STATE_PATH")
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_file():
        raise ListingFetchError(
            f"Browser storage-state file does not exist or is not a file: {path}"
        )
    return path


if __name__ == "__main__":
    raise SystemExit(main())
