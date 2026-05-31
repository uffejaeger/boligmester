from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass

from apartment_agents.app.errors import ConfigValidationError, ListingFetchError
from apartment_agents.tools.http import detect_blocked_listing_html


@dataclass(slots=True)
class BrowserCommandPageFetcher:
    command_template: str
    timeout_seconds: int = 45

    def __post_init__(self) -> None:
        if not self.command_template.strip():
            raise ConfigValidationError("Browser fetch command cannot be empty.")
        if "{url}" not in self.command_template:
            raise ConfigValidationError("Browser fetch command must contain a {url} placeholder.")
        if self.timeout_seconds <= 0:
            raise ConfigValidationError("Browser fetch timeout must be positive.")
        argv = shlex.split(self.command_template)
        executable = argv[0]
        if "/" in executable:
            if not shutil.which(executable):
                raise ConfigValidationError(
                    f"Browser fetch executable is not available: {executable}"
                )
        elif shutil.which(executable) is None:
            raise ConfigValidationError(
                f"Browser fetch executable is not available on PATH: {executable}"
            )

    def fetch_text(self, url: str) -> str:
        argv = [part.replace("{url}", url) for part in shlex.split(self.command_template)]
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ListingFetchError(
                f"Browser fetch timed out after {self.timeout_seconds}s for URL: {url}"
            ) from exc
        except OSError as exc:
            raise ListingFetchError(f"Browser fetch could not start for URL: {url}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            detail = stderr[:240] if stderr else f"exit code {result.returncode}"
            raise ListingFetchError(f"Browser fetch failed for URL: {url} ({detail})")

        document = result.stdout
        blocked_message = detect_blocked_listing_html(document)
        if blocked_message is not None:
            raise ListingFetchError(
                f"Browser fetch completed but returned a blocked page for URL: {url} ({blocked_message})"
            )
        return document
