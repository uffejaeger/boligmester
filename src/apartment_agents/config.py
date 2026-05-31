from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from apartment_agents.app.errors import ConfigValidationError
from apartment_agents.logging import configure_logging, get_logger, log_kv


logger = get_logger("config")


@dataclass(slots=True)
class AppConfig:
    app_env: str = "development"
    log_level: str = "INFO"
    output_dir: Path = Path("output")
    workspace_dir: Path | None = None
    adk_backend: str = "mock"
    adk_model: str = "gemini-2.5-pro"
    adk_timeout_seconds: int = 30
    http_timeout_seconds: int = 20
    enable_live_listing_fetch: bool = False
    enable_browser_listing_fetch: bool = False
    browser_fetch_timeout_seconds: int = 45
    browser_listing_fetch_command: str | None = None
    browser_storage_state_path: Path | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None

    def __post_init__(self) -> None:
        if self.workspace_dir is None:
            self.workspace_dir = self.output_dir / "workspace"
        configure_logging(self.log_level)
        self.validate()
        self.ensure_directories()
        log_kv(
            logger,
            20,
            "config_initialized",
            app_env=self.app_env,
            adk_backend=self.adk_backend,
            output_dir=str(self.output_dir),
            workspace_dir=str(self.workspace_dir),
            log_level=self.log_level,
        )

    @classmethod
    def load(cls) -> "AppConfig":
        output_dir = Path(os.getenv("REPORT_OUTPUT_DIR", "output"))
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            output_dir=output_dir,
            workspace_dir=_optional_path_from_env("BOLIGMESTER_WORKSPACE_DIR"),
            adk_backend=os.getenv("ADK_BACKEND", "mock"),
            adk_model=os.getenv("ADK_MODEL", "gemini-2.5-pro"),
            adk_timeout_seconds=int(os.getenv("ADK_TIMEOUT_SECONDS", "30")),
            http_timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
            enable_live_listing_fetch=os.getenv("ENABLE_LIVE_LISTING_FETCH", "false").lower()
            in {"1", "true", "yes"},
            enable_browser_listing_fetch=os.getenv("ENABLE_BROWSER_LISTING_FETCH", "false").lower()
            in {"1", "true", "yes"},
            browser_fetch_timeout_seconds=int(os.getenv("BROWSER_FETCH_TIMEOUT_SECONDS", "45")),
            browser_listing_fetch_command=os.getenv("BROWSER_LISTING_FETCH_COMMAND") or None,
            browser_storage_state_path=_optional_path_from_env("BROWSER_STORAGE_STATE_PATH"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            google_api_key=os.getenv("GOOGLE_API_KEY") or None,
        )

    def ensure_directories(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        assert self.workspace_dir is not None
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        if self.adk_backend not in {"mock", "google_adk"}:
            raise ConfigValidationError(
                f"Unsupported ADK_BACKEND '{self.adk_backend}'. Expected 'mock' or 'google_adk'."
            )
        if self.adk_backend == "google_adk" and not self.google_api_key:
            raise ConfigValidationError("GOOGLE_API_KEY is required when ADK_BACKEND=google_adk.")
        if self.adk_timeout_seconds <= 0:
            raise ConfigValidationError("ADK_TIMEOUT_SECONDS must be a positive integer.")
        if self.http_timeout_seconds <= 0:
            raise ConfigValidationError("HTTP_TIMEOUT_SECONDS must be a positive integer.")
        if self.browser_fetch_timeout_seconds <= 0:
            raise ConfigValidationError("BROWSER_FETCH_TIMEOUT_SECONDS must be a positive integer.")
        if self.enable_browser_listing_fetch and not self.browser_listing_fetch_command:
            raise ConfigValidationError(
                "BROWSER_LISTING_FETCH_COMMAND is required when ENABLE_BROWSER_LISTING_FETCH=true."
            )
        if self.browser_listing_fetch_command and "{url}" not in self.browser_listing_fetch_command:
            raise ConfigValidationError(
                "BROWSER_LISTING_FETCH_COMMAND must contain a {url} placeholder."
            )
        if (
            self.browser_storage_state_path is not None
            and not self.browser_storage_state_path.is_file()
        ):
            raise ConfigValidationError(
                "BROWSER_STORAGE_STATE_PATH must point to an existing file."
            )


def _optional_path_from_env(name: str) -> Path | None:
    value = os.getenv(name)
    if not value:
        return None
    return Path(value).expanduser()
