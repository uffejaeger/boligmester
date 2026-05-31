from __future__ import annotations

from apartment_agents.app.errors import ApartmentAgentsError
from apartment_agents.app.services import AnalyzeApartmentRequest, AnalyzeApartmentService
from apartment_agents.config import AppConfig
from apartment_agents.logging import get_logger, log_kv

APP_TITLE = "ApartmentBuyingAgents DK"

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
    return (
        f"{screen['title']}\n\n"
        f"Status: {screen['status']}\n\n"
        f"{screen['message']}"
    )


def run(
    input_func=input,
    output_func=print,
    service: AnalyzeApartmentService | None = None,
) -> None:
    try:
        service = service or AnalyzeApartmentService(config=AppConfig.load())
    except ApartmentAgentsError as exc:
        log_kv(logger, 40, "tui_startup_failed", error=str(exc))
        output_func(f"Startup error: {exc}")
        return

    log_kv(logger, 20, "tui_started")
    output_func(render_main_menu())
    choice = input_func("Choose an option: ").strip()
    log_kv(logger, 20, "tui_choice_selected", choice=choice)
    if choice in PLACEHOLDER_SCREENS:
        output_func(render_placeholder_screen(choice))
        return
    if choice != "1":
        output_func(render_placeholder_screen(choice))
        return

    output_func("Available buyer profiles:")
    for profile in service.available_buyer_profiles():
        output_func(
            f"- {profile.buyer_id}: net {profile.net_monthly_income_dkk:,} DKK/month, "
            f"savings {profile.savings_dkk:,} DKK"
        )

    listing_url = input_func("Listing URL: ").strip()
    buyer_profile_id = input_func("Buyer profile id: ").strip()

    if not listing_url:
        log_kv(logger, 30, "tui_validation_failed", field="listing_url")
        output_func("Analysis error: Listing URL is required.")
        return
    if not buyer_profile_id:
        log_kv(logger, 30, "tui_validation_failed", field="buyer_profile_id")
        output_func("Analysis error: Buyer profile id is required.")
        return

    output_func("Running analysis...")
    try:
        result = service.analyze(
            AnalyzeApartmentRequest(
                listing_url=listing_url,
                buyer_profile_id=buyer_profile_id,
            )
        )
    except ApartmentAgentsError as exc:
        log_kv(logger, 40, "tui_analysis_failed", error=str(exc))
        output_func(f"Analysis error: {exc}")
        return
    output_func("")
    output_func(f"Recommendation: {result.report.recommendation.value}")
    output_func(f"Report written to: {result.report_path}")
    output_func("")
    output_func(result.report_markdown)
