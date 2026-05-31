from __future__ import annotations

from apartment_agents.app.errors import ApartmentAgentsError
from apartment_agents.app.services import AnalyzeApartmentService
from apartment_agents.config import AppConfig
from apartment_agents.logging import get_logger, log_kv

APP_TITLE = "Boligmester"

MENU_ITEMS = [
    "1 Analyze Apartment URL",
    "2 Search Apartments",
    "3 Analyze Documents",
    "4 Affordability Simulator",
    "5 Compare Apartments",
    "6 Watchlist",
    "7 Reports",
    "8 Settings",
]

PLACEHOLDER_SCREENS = {
    "2": {
        "title": "Search Apartments",
        "status": "Planned",
        "message": "Search workflow is not implemented yet. The next build step is saved search and filter support.",
    },
    "3": {
        "title": "Analyze Documents",
        "status": "Planned",
        "message": "Document analysis is not implemented yet. The next build step is document ingestion and due diligence parsing.",
    },
    "4": {
        "title": "Affordability Simulator",
        "status": "Planned",
        "message": "Standalone affordability simulation is not implemented yet. Finance calculations currently run through apartment analysis only.",
    },
    "5": {
        "title": "Compare Apartments",
        "status": "Planned",
        "message": "Apartment comparison is not implemented yet. The next build step is structured multi-listing comparison.",
    },
    "6": {
        "title": "Watchlist",
        "status": "Planned",
        "message": "Watchlist support is not implemented yet. The next build step is local saved-apartment storage and change tracking.",
    },
    "7": {
        "title": "Reports",
        "status": "Planned",
        "message": "Report browsing is not implemented yet. Reports are currently written directly to the output directory.",
    },
    "8": {
        "title": "Settings",
        "status": "Planned",
        "message": "Interactive settings are not implemented yet. Runtime behavior is currently configured through environment variables.",
    },
}

logger = get_logger("tui")


def render_main_menu() -> str:
    menu = "\n".join(MENU_ITEMS)
    return f"{APP_TITLE}\n\n{menu}\n"


def render_placeholder_screen(choice: str) -> str:
    screen = PLACEHOLDER_SCREENS.get(choice)
    if screen is None:
        return "Unknown menu selection. Choose one of the listed options."
    return f"{screen['title']}\n\nStatus: {screen['status']}\n\n{screen['message']}"


def _load_textual_launcher():
    try:
        from apartment_agents.tui.textual_ui import run_textual_app
    except ImportError as exc:  # pragma: no cover - exercised only when dependency is absent
        raise RuntimeError(
            "Textual is not installed. Install the TUI extra with `pip install -e '.[tui]'`."
        ) from exc
    return run_textual_app


def run(
    input_func=input,
    output_func=print,
    service: AnalyzeApartmentService | None = None,
) -> None:
    del input_func, output_func
    try:
        service = service or AnalyzeApartmentService(config=AppConfig.load())
    except ApartmentAgentsError as exc:
        log_kv(logger, 40, "tui_startup_failed", error=str(exc))
        raise

    log_kv(logger, 20, "tui_started")
    launcher = _load_textual_launcher()
    launcher(service)
