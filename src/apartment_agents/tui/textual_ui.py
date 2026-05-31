from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rich.text import Text

from apartment_agents.app.services import (
    AnalyzeApartmentRequest,
    AnalyzeApartmentService,
    SearchApartmentsRequest,
)
from apartment_agents.models import (
    BuyerProfile,
    HouseholdProfile,
    ListingSearchResult,
    SavedApartment,
)

try:
    from textual import events, on
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.screen import Screen
    from textual.widgets import DataTable, Input, Markdown, Select, Static
except ImportError:  # pragma: no cover - depends on the optional tui extra
    raise


SAMPLE_LISTING_URL = "https://www.boligsiden.dk/adresse/frederiks-alle-12-3-th-8000-aarhus-c"


@dataclass(frozen=True, slots=True)
class MenuEntry:
    key: str
    namespace: str
    name: str
    ready: str
    status: str
    kind: str
    summary: str
    detail: str


@dataclass(slots=True)
class PlaceholderContent:
    title: str
    message: str


MENU_ENTRIES = [
    MenuEntry(
        key="analyze",
        namespace="default",
        name="apartment-url",
        ready="1/1",
        status="Running",
        kind="Analyzer",
        summary="Analyze one apartment listing against a buyer profile.",
        detail=(
            "Runs listing ingestion, deterministic finance checks, specialist findings, "
            "and committee synthesis. Reports are written as markdown under the output directory."
        ),
    ),
    MenuEntry(
        key="search",
        namespace="default",
        name="saved-searches",
        ready="1/1",
        status="Running",
        kind="Workflow",
        summary="Search apartments by city and filters.",
        detail=(
            "Runs apartment search, parses structured result rows, and saves each search "
            "run to the local workspace."
        ),
    ),
    MenuEntry(
        key="documents",
        namespace="default",
        name="documents",
        ready="0/1",
        status="Planned",
        kind="Workflow",
        summary="Document ingestion and due diligence.",
        detail=(
            "Document analysis is not implemented yet. Next build step is document "
            "ingestion and due diligence parsing."
        ),
    ),
    MenuEntry(
        key="finance",
        namespace="finance",
        name="affordability",
        ready="0/1",
        status="Planned",
        kind="Simulator",
        summary="Standalone affordability simulation.",
        detail=(
            "Standalone affordability simulation is not implemented yet. Finance calculations "
            "currently run through apartment analysis only."
        ),
    ),
    MenuEntry(
        key="compare",
        namespace="default",
        name="comparisons",
        ready="0/1",
        status="Planned",
        kind="Workflow",
        summary="Structured multi-listing comparison.",
        detail="Apartment comparison is not implemented yet. Next build step is comparison reports.",
    ),
    MenuEntry(
        key="watchlist",
        namespace="default",
        name="saved-apartments",
        ready="1/1",
        status="Running",
        kind="Store",
        summary="Save apartments and revisit them.",
        detail=(
            "Saved apartments are stored locally and can be reopened in the URL analyzer. "
            "Change tracking remains a later watchlist workflow."
        ),
    ),
    MenuEntry(
        key="profiles",
        namespace="workspace",
        name="buyer-profiles",
        ready="1/1",
        status="Running",
        kind="Store",
        summary="Create and save buyer profiles.",
        detail=(
            "Buyer profiles can be created from the TUI and are saved to the local "
            "workspace so they are available next time Boligmester starts."
        ),
    ),
    MenuEntry(
        key="reports",
        namespace="reports",
        name="markdown-reports",
        ready="0/1",
        status="Planned",
        kind="Browser",
        summary="Browse generated reports.",
        detail=(
            "Report browsing is not implemented yet. Reports are currently written directly "
            "to the output directory."
        ),
    ),
    MenuEntry(
        key="settings",
        namespace="system",
        name="runtime-config",
        ready="0/1",
        status="Planned",
        kind="Config",
        summary="Runtime behavior and credentials.",
        detail=(
            "Interactive settings are not implemented yet. Runtime behavior is currently "
            "configured through environment variables."
        ),
    ),
]


def _format_dkk(value: int) -> str:
    return f"{value:,}".replace(",", ".") + " DKK"


def _format_optional_dkk(value: int | None) -> str:
    return _format_dkk(value) if value is not None else "-"


def _format_optional_sqm(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:g} m2"


def _format_optional_rooms(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:g}"


def _profile_options(profiles: list[BuyerProfile]) -> list[tuple[str, str]]:
    if not profiles:
        return [("No buyer profiles found", "")]
    return [
        (
            f"{profile.buyer_id}  net={_format_dkk(profile.net_monthly_income_dkk)}/mo",
            profile.buyer_id,
        )
        for profile in profiles
    ]


def _profile_rows(profiles: list[BuyerProfile]) -> str:
    if not profiles:
        return "No buyer profiles found."
    rows = ["NAME                NET/MO         SAVINGS        RISK"]
    for profile in profiles:
        rows.append(
            f"{profile.buyer_id:<19} "
            f"{_format_dkk(profile.net_monthly_income_dkk):<14} "
            f"{_format_dkk(profile.savings_dkk):<14} "
            f"{profile.risk_tolerance}"
        )
    return "\n".join(rows)


def _top_bar(view: str, service: AnalyzeApartmentService) -> Static:
    return Static(
        (
            f"CTX local  APP boligmester  VIEW {view}  "
            f"BACKEND {service.config.adk_backend}  OUT {service.config.output_dir.name}"
        ),
        classes="top-bar",
    )


def _key_bar(*items: tuple[str, str]) -> Static:
    body = "  ".join(f"[b]{key}[/b] {label}" for key, label in items)
    return Static(body, classes="key-bar")


def _entry_detail(entry: MenuEntry, service: AnalyzeApartmentService) -> str:
    return (
        f"[b]{entry.kind}/{entry.name}[/b]\n"
        f"Namespace: {entry.namespace}\n"
        f"Ready:     {entry.ready}\n"
        f"Status:    {entry.status}\n\n"
        f"{entry.summary}\n\n"
        f"{entry.detail}\n\n"
        f"Profiles: {len(service.available_buyer_profiles())}\n"
        f"Saved:    {len(service.available_saved_apartments())}\n"
        f"Output:   {service.config.output_dir}"
    )


class NavigationInput(Input):
    BINDINGS = [
        Binding("enter", "run_analysis", show=False, priority=True),
        Binding("down", "focus_next_control", show=False, priority=True),
        Binding("up", "focus_previous_control", show=False, priority=True),
        Binding("ctrl+r", "run_analysis", show=False, priority=True),
        Binding("ctrl+s", "load_sample", show=False, priority=True),
    ]

    def action_focus_next_control(self) -> None:
        self.app.action_focus_next_control()

    def action_focus_previous_control(self) -> None:
        self.app.action_focus_previous_control()

    async def action_run_analysis(self) -> None:
        await self.app.screen.action_run_analysis()

    def action_load_sample(self) -> None:
        self.app.screen.action_load_sample()

    async def _on_key(self, event: events.Key) -> None:
        if event.key in {"enter", "ctrl+r"}:
            event.stop()
            event.prevent_default()
            await self.app.screen.action_run_analysis()
            return
        if event.key == "ctrl+s":
            event.stop()
            event.prevent_default()
            self.app.screen.action_load_sample()
            return
        await super()._on_key(event)


class CommandTable(DataTable):
    def action_select_cursor(self) -> None:
        row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
        if row_key.value == "run":
            asyncio.create_task(self.app.screen.action_run_analysis())
        elif row_key.value == "sample":
            self.app.screen.action_load_sample()
        elif row_key.value == "search":
            asyncio.create_task(self.app.screen.action_run_search())
        elif row_key.value == "save-apartment":
            self.app.screen.action_save_selected_apartment()
        elif row_key.value == "analyze-selected":
            self.app.screen.action_analyze_selected()
        elif row_key.value == "save":
            asyncio.create_task(self.app.screen.action_save_profile())


class MenuScreen(Screen[None]):
    BINDINGS = [
        Binding("1", "open_analyzer", "Analyze"),
        Binding("2", "open_search", "Search"),
        Binding("6", "open_watchlist", "Saved"),
        Binding("p", "open_profiles", "Profiles"),
        Binding("9", "open_profiles", "Profiles"),
        Binding("7", "open_reports", "Reports"),
        Binding("8", "open_settings", "Settings"),
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            _top_bar("resources", self.app.service),
            Horizontal(
                Vertical(
                    Static("RESOURCE", classes="pane-title"),
                    DataTable(
                        id="resource-table",
                        cursor_type="row",
                        show_row_labels=False,
                        zebra_stripes=True,
                    ),
                    classes="resource-pane",
                ),
                Vertical(
                    Static("DESCRIBE", classes="pane-title"),
                    Static("", id="describe-body", classes="describe-body"),
                    classes="describe-pane",
                ),
                classes="main-split",
            ),
            _key_bar(
                ("up/down", "Move"),
                ("enter", "Open"),
                ("1", "Analyze"),
                ("2", "Search"),
                ("6", "Saved"),
                ("p", "Profiles"),
                ("7", "Reports"),
                ("esc", "Back"),
                ("q", "Quit"),
            ),
            classes="screen-frame",
        )

    def on_mount(self) -> None:
        table = self.query_one("#resource-table", DataTable)
        table.add_column("NAMESPACE", width=11)
        table.add_column("NAME", width=20)
        table.add_column("READY", width=7)
        table.add_column("STATUS", width=10)
        table.add_column("KIND", width=12)
        for entry in MENU_ENTRIES:
            table.add_row(
                entry.namespace,
                entry.name,
                entry.ready,
                entry.status,
                entry.kind,
                key=entry.key,
            )
        table.focus()
        self._show_entry(MENU_ENTRIES[0].key)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "resource-table" and event.row_key.value is not None:
            self._show_entry(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "resource-table" and event.row_key.value is not None:
            event.stop()
            self._open_entry(event.row_key.value)

    def action_open_analyzer(self) -> None:
        self._open_entry("analyze")

    def action_open_search(self) -> None:
        self._open_entry("search")

    def action_open_watchlist(self) -> None:
        self._open_entry("watchlist")

    def action_open_profiles(self) -> None:
        self._open_entry("profiles")

    def action_open_reports(self) -> None:
        self._open_entry("reports")

    def action_open_settings(self) -> None:
        self._open_entry("settings")

    def _show_entry(self, key: str) -> None:
        entry = _entry_by_key(key)
        self.query_one("#describe-body", Static).update(_entry_detail(entry, self.app.service))

    def _open_entry(self, key: str) -> None:
        if key == "analyze":
            self.app.push_screen(AnalyzeScreen(self.app.service))
            return
        if key == "search":
            self.app.push_screen(SearchScreen(self.app.service))
            return
        if key == "watchlist":
            self.app.push_screen(SavedApartmentsScreen(self.app.service))
            return
        if key == "profiles":
            self.app.push_screen(ProfileScreen(self.app.service))
            return

        entry = _entry_by_key(key)
        self.app.push_screen(PlaceholderScreen(PlaceholderContent(entry.name, entry.detail)))


class PlaceholderScreen(Screen[None]):
    def __init__(self, content: PlaceholderContent) -> None:
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        yield Vertical(
            _top_bar(self.content.title, self.app.service),
            Vertical(
                Static("DESCRIBE", classes="pane-title"),
                Static(
                    f"[b]{self.content.title}[/b]\nStatus: Planned\n\n{self.content.message}",
                    classes="describe-body",
                ),
                classes="single-pane",
            ),
            _key_bar(("esc", "Back"), ("q", "Quit")),
            classes="screen-frame",
        )


class SearchScreen(Screen[None]):
    BINDINGS = [
        Binding("f", "run_search", "Search"),
        Binding("s", "save_selected_apartment", "Save"),
        Binding("a", "analyze_selected", "Analyze"),
    ]

    def __init__(self, service: AnalyzeApartmentService) -> None:
        super().__init__()
        self.service = service
        self._results: list[ListingSearchResult] = []
        self._selected_url: str | None = None
        self._search_running = False

    def compose(self) -> ComposeResult:
        yield Vertical(
            _top_bar("search/apartments", self.service),
            Horizontal(
                VerticalScroll(
                    Static("SEARCH", classes="pane-title"),
                    Static("CITY", classes="field-label"),
                    Input(value="Aarhus C", id="search-city"),
                    Static("MAX PRICE DKK", classes="field-label"),
                    Input(placeholder="4500000", id="search-max-price"),
                    Static("MIN AREA M2", classes="field-label"),
                    Input(placeholder="50", id="search-min-area"),
                    Static("MIN ROOMS", classes="field-label"),
                    Input(placeholder="2", id="search-min-rooms"),
                    Static("MAX RESULTS", classes="field-label"),
                    Input(value="10", id="search-max-results"),
                    Static("SEARCH URL", classes="field-label"),
                    Input(placeholder="Optional source search URL", id="search-url"),
                    CommandTable(
                        id="search-command-table",
                        cursor_type="row",
                        show_header=False,
                        show_row_labels=False,
                    ),
                    Static("", id="search-status", classes="status-line"),
                    classes="form-pane",
                ),
                Vertical(
                    Static("RESULTS", classes="pane-title"),
                    DataTable(
                        id="search-results",
                        cursor_type="row",
                        show_row_labels=False,
                        zebra_stripes=True,
                    ),
                    Static("", id="search-detail", classes="describe-body"),
                    classes="output-pane",
                ),
                classes="main-split",
            ),
            _key_bar(
                ("up/down", "Move"),
                ("enter", "Run command"),
                ("f", "Search"),
                ("s", "Save selected"),
                ("a", "Analyze selected"),
                ("esc", "Back"),
                ("q", "Quit"),
            ),
            classes="screen-frame",
        )

    def on_mount(self) -> None:
        commands = self.query_one("#search-command-table", DataTable)
        commands.add_column("KEY", width=5)
        commands.add_column("ACTION", width=24)
        commands.add_row("f", "search-apartments", key="search")
        commands.add_row("s", "save-selected", key="save-apartment")
        commands.add_row("a", "analyze-selected", key="analyze-selected")

        results = self.query_one("#search-results", DataTable)
        results.add_column("ADDRESS", width=30)
        results.add_column("PRICE", width=14)
        results.add_column("AREA", width=9)
        results.add_column("ROOMS", width=7)
        self.set_timer(0.05, self.query_one("#search-city", Input).focus)

    @on(DataTable.RowSelected, "#search-command-table")
    async def search_command_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value == "search":
            await self.action_run_search()
        elif event.row_key.value == "save-apartment":
            self.action_save_selected_apartment()
        elif event.row_key.value == "analyze-selected":
            self.action_analyze_selected()

    @on(DataTable.RowHighlighted, "#search-results")
    def search_result_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key.value is not None:
            self._selected_url = str(event.row_key.value)
            self._show_search_result_detail(self._selected_url)

    @on(DataTable.RowSelected, "#search-results")
    def search_result_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is not None:
            self._selected_url = str(event.row_key.value)
            self.action_analyze_selected()

    async def action_run_search(self) -> None:
        if self._search_running:
            return

        status = self.query_one("#search-status", Static)
        self._search_running = True
        status.update(Text("running search/apartments", style="bold #ffd166"))
        try:
            result = await asyncio.to_thread(
                self.service.search_apartments,
                SearchApartmentsRequest(
                    city=self._input_value("search-city"),
                    max_price_dkk=self._optional_int("search-max-price"),
                    min_area_sqm=self._optional_float("search-min-area"),
                    min_rooms=self._optional_float("search-min-rooms"),
                    max_results=self._required_int("search-max-results"),
                    search_url=self._input_value("search-url") or None,
                ),
            )
        except Exception as exc:
            status.update(Text(f"search error: {exc}", style="bold #ff6b6b"))
            return
        finally:
            self._search_running = False

        self._results = result.search_run.results
        self._refresh_search_table()
        if self._results:
            self._selected_url = self._results[0].url
            self._show_search_result_detail(self._selected_url)
        status.update(
            Text(
                f"search complete: {len(self._results)} results saved",
                style="bold #7ddf64",
            )
        )

    def action_analyze_selected(self) -> None:
        status = self.query_one("#search-status", Static)
        result = self._selected_result()
        if result is None:
            status.update(Text("select a search result first", style="bold #ff6b6b"))
            return
        self.app.push_screen(AnalyzeScreen(self.service, initial_listing_url=result.url))

    def action_save_selected_apartment(self) -> None:
        status = self.query_one("#search-status", Static)
        result = self._selected_result()
        if result is None:
            status.update(Text("select a search result first", style="bold #ff6b6b"))
            return
        saved = self.service.save_search_result_apartment(result)
        status.update(
            Text(
                f"saved apartment {saved.saved_apartment.saved_id}",
                style="bold #7ddf64",
            )
        )

    def _refresh_search_table(self) -> None:
        table = self.query_one("#search-results", DataTable)
        table.clear()
        for result in self._results:
            table.add_row(
                result.address.street,
                _format_optional_dkk(result.asking_price_dkk),
                _format_optional_sqm(result.area_sqm),
                _format_optional_rooms(result.rooms),
                key=result.url,
            )

    def _show_search_result_detail(self, url: str) -> None:
        result = next((candidate for candidate in self._results if candidate.url == url), None)
        if result is None:
            return
        self.query_one("#search-detail", Static).update(
            "\n".join(
                [
                    f"[b]{result.title}[/b]",
                    f"URL: {result.url}",
                    f"Address: {result.address.street}, {result.address.postal_code} {result.address.city}",
                    f"Price: {_format_optional_dkk(result.asking_price_dkk)}",
                    f"Area: {_format_optional_sqm(result.area_sqm)}",
                    f"Rooms: {_format_optional_rooms(result.rooms)}",
                    f"Owner cost: {_format_optional_dkk(result.owner_cost_monthly_dkk)}",
                    f"Price/m2: {_format_optional_dkk(result.price_per_sqm_dkk)}",
                ]
            )
        )

    def _selected_result(self) -> ListingSearchResult | None:
        if self._selected_url is None:
            return None
        return next(
            (candidate for candidate in self._results if candidate.url == self._selected_url),
            None,
        )

    def _input_value(self, widget_id: str) -> str:
        return self.query_one(f"#{widget_id}", Input).value.strip()

    def _required_int(self, widget_id: str) -> int:
        value = self._input_value(widget_id)
        if not value:
            raise ValueError(f"{widget_id.replace('-', ' ')} is required")
        return int(value)

    def _optional_int(self, widget_id: str) -> int | None:
        value = self._input_value(widget_id)
        if not value:
            return None
        return int(value)

    def _optional_float(self, widget_id: str) -> float | None:
        value = self._input_value(widget_id)
        if not value:
            return None
        return float(value.replace(",", "."))


class SavedApartmentsScreen(Screen[None]):
    BINDINGS = [
        Binding("a", "analyze_selected", "Analyze"),
    ]

    def __init__(self, service: AnalyzeApartmentService) -> None:
        super().__init__()
        self.service = service
        self._selected_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Vertical(
            _top_bar("workspace/saved-apartments", self.service),
            Horizontal(
                Vertical(
                    Static("SAVED APARTMENTS", classes="pane-title"),
                    DataTable(
                        id="saved-apartments",
                        cursor_type="row",
                        show_row_labels=False,
                        zebra_stripes=True,
                    ),
                    classes="resource-pane",
                ),
                Vertical(
                    Static("DETAIL", classes="pane-title"),
                    Static("", id="saved-apartment-detail", classes="describe-body"),
                    classes="describe-pane",
                ),
                classes="main-split",
            ),
            _key_bar(
                ("up/down", "Move"),
                ("enter", "Analyze"),
                ("a", "Analyze selected"),
                ("esc", "Back"),
                ("q", "Quit"),
            ),
            classes="screen-frame",
        )

    def on_mount(self) -> None:
        table = self.query_one("#saved-apartments", DataTable)
        table.add_column("ADDRESS", width=30)
        table.add_column("PRICE", width=14)
        table.add_column("AREA", width=9)
        table.add_column("TAGS", width=14)
        apartments = self.service.available_saved_apartments()
        for apartment in apartments:
            table.add_row(
                apartment.address.street,
                _format_optional_dkk(apartment.asking_price_dkk),
                _format_optional_sqm(apartment.area_sqm),
                ", ".join(apartment.tags) or "-",
                key=apartment.saved_id,
            )
        if apartments:
            self._selected_id = apartments[0].saved_id
            self._show_saved_apartment_detail(apartments[0].saved_id)
        else:
            self.query_one("#saved-apartment-detail", Static).update("No saved apartments.")
        self.set_timer(0.05, table.focus)

    @on(DataTable.RowHighlighted, "#saved-apartments")
    def saved_apartment_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key.value is not None:
            self._selected_id = str(event.row_key.value)
            self._show_saved_apartment_detail(self._selected_id)

    @on(DataTable.RowSelected, "#saved-apartments")
    def saved_apartment_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is not None:
            self._selected_id = str(event.row_key.value)
            self.action_analyze_selected()

    def action_analyze_selected(self) -> None:
        apartment = self._selected_apartment()
        if apartment is None:
            self.query_one("#saved-apartment-detail", Static).update("No saved apartment selected.")
            return
        self.app.push_screen(AnalyzeScreen(self.service, initial_listing_url=apartment.url))

    def _show_saved_apartment_detail(self, saved_id: str) -> None:
        apartment = next(
            (
                candidate
                for candidate in self.service.available_saved_apartments()
                if candidate.saved_id == saved_id
            ),
            None,
        )
        if apartment is None:
            return
        self.query_one("#saved-apartment-detail", Static).update(
            "\n".join(
                [
                    f"[b]{apartment.title}[/b]",
                    f"URL: {apartment.url}",
                    f"Address: {apartment.address.street}, {apartment.address.postal_code} {apartment.address.city}",
                    f"Price: {_format_optional_dkk(apartment.asking_price_dkk)}",
                    f"Area: {_format_optional_sqm(apartment.area_sqm)}",
                    f"Rooms: {_format_optional_rooms(apartment.rooms)}",
                    f"Owner cost: {_format_optional_dkk(apartment.owner_cost_monthly_dkk)}",
                    f"Price/m2: {_format_optional_dkk(apartment.price_per_sqm_dkk)}",
                    f"Tags: {', '.join(apartment.tags) or '-'}",
                    f"Notes: {apartment.notes or '-'}",
                ]
            )
        )

    def _selected_apartment(self) -> SavedApartment | None:
        if self._selected_id is None:
            return None
        return next(
            (
                candidate
                for candidate in self.service.available_saved_apartments()
                if candidate.saved_id == self._selected_id
            ),
            None,
        )


class AnalyzeScreen(Screen[None]):
    BINDINGS = [
        Binding("r", "run_analysis", "Run"),
        Binding("s", "load_sample", "Sample"),
    ]

    def __init__(
        self, service: AnalyzeApartmentService, initial_listing_url: str = SAMPLE_LISTING_URL
    ) -> None:
        super().__init__()
        self.service = service
        self.initial_listing_url = initial_listing_url
        self._analysis_running = False

    def compose(self) -> ComposeResult:
        profiles = self.service.available_buyer_profiles()
        default_profile = next(
            (profile.buyer_id for profile in profiles if profile.buyer_id == "solo_engineer"),
            profiles[0].buyer_id if profiles else "",
        )
        yield Vertical(
            _top_bar("analyzer/apartment-url", self.service),
            Horizontal(
                Vertical(
                    Static("FORM", classes="pane-title"),
                    Static("LISTING URL", classes="field-label"),
                    NavigationInput(
                        placeholder="Listing URL",
                        id="listing-url",
                        value=self.initial_listing_url,
                    ),
                    Static("BUYER PROFILE", classes="field-label"),
                    Select(
                        _profile_options(profiles),
                        id="buyer-profile-id",
                        value=default_profile,
                        allow_blank=False,
                        compact=True,
                    ),
                    Static("COMMANDS", classes="field-label"),
                    CommandTable(
                        id="command-table",
                        cursor_type="row",
                        show_header=False,
                        show_row_labels=False,
                    ),
                    Static("", id="analysis-status", classes="status-line"),
                    Static("BUYER PROFILES", classes="field-label"),
                    Static(_profile_rows(profiles), classes="profile-table"),
                    classes="form-pane",
                ),
                Vertical(
                    Horizontal(
                        Static(
                            "[b]--[/b]\nRECOMMENDATION", id="recommendation-tile", classes="tile"
                        ),
                        Static("[b]Not run[/b]\nREPORT", id="report-tile", classes="tile"),
                        Static("[b]Waiting[/b]\nEVIDENCE", id="evidence-tile", classes="tile"),
                        classes="tile-row",
                    ),
                    VerticalScroll(
                        Markdown(
                            "# Report preview\n\nPress `ctrl+r` to run the selected analyzer.",
                            id="analysis-report",
                        ),
                        classes="report-pane",
                    ),
                    classes="output-pane",
                ),
                classes="main-split",
            ),
            _key_bar(
                ("up/down", "Move"),
                ("enter", "Run command"),
                ("r", "Run"),
                ("s", "Sample URL"),
                ("esc", "Back"),
                ("q", "Quit"),
            ),
            classes="screen-frame",
        )

    def on_mount(self) -> None:
        commands = self.query_one("#command-table", DataTable)
        commands.add_column("KEY", width=5)
        commands.add_column("ACTION", width=24)
        commands.add_row("r", "run-analysis", key="run")
        commands.add_row("s", "load-sample-url", key="sample")
        self.set_timer(0.05, commands.focus)

    @on(DataTable.RowSelected, "#command-table")
    async def command_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is None:
            return
        if event.row_key.value == "run":
            await self.action_run_analysis()
        elif event.row_key.value == "sample":
            self.action_load_sample()

    def action_load_sample(self) -> None:
        self.query_one("#listing-url", Input).value = SAMPLE_LISTING_URL
        self.query_one("#analysis-status", Static).update(
            Text("sample listing loaded", style="bold #7ddf64")
        )

    async def action_run_analysis(self) -> None:
        if self._analysis_running:
            return

        status = self.query_one("#analysis-status", Static)
        recommendation_tile = self.query_one("#recommendation-tile", Static)
        report_tile = self.query_one("#report-tile", Static)
        evidence_tile = self.query_one("#evidence-tile", Static)
        report = self.query_one("#analysis-report", Markdown)
        listing_input = self.query_one("#listing-url", Input)
        buyer_input = self.query_one("#buyer-profile-id", Select)

        listing_url = listing_input.value.strip()
        buyer_value = buyer_input.value
        buyer_profile_id = "" if buyer_value == Select.NULL else str(buyer_value).strip()
        if not listing_url:
            status.update(Text("listing url is required", style="bold #ff6b6b"))
            return
        if not buyer_profile_id:
            status.update(Text("buyer profile id is required", style="bold #ff6b6b"))
            return

        self._analysis_running = True
        status.update(Text("running analyzer/apartment-url", style="bold #ffd166"))
        recommendation_tile.update("[b]--[/b]\nRECOMMENDATION")
        report_tile.update("[b]Working[/b]\nREPORT")
        evidence_tile.update("[b]Parsing[/b]\nEVIDENCE")
        await report.update("# Report preview\n\nAnalyzer is running.")

        try:
            result = await asyncio.to_thread(
                self.service.analyze,
                AnalyzeApartmentRequest(
                    listing_url=listing_url,
                    buyer_profile_id=buyer_profile_id,
                ),
            )
        except Exception as exc:
            status.update(Text(f"analysis error: {exc}", style="bold #ff6b6b"))
            report_tile.update("[b]Failed[/b]\nREPORT")
            evidence_tile.update("[b]Review[/b]\nEVIDENCE")
            return
        finally:
            self._analysis_running = False

        recommendation = result.report.recommendation.value
        finding_count = len(result.report.findings)
        open_questions = len(result.report.unresolved_questions)
        status.update(Text("analysis complete", style="bold #7ddf64"))
        recommendation_tile.update(f"[b]{recommendation}[/b]\nRECOMMENDATION")
        report_tile.update(f"[b]{result.report_path.name}[/b]\nREPORT")
        evidence_tile.update(f"[b]{finding_count} findings[/b]\n{open_questions} open questions")
        await report.update(result.report_markdown)


class ProfileScreen(Screen[None]):
    BINDINGS = [
        Binding("s", "save_profile", "Save"),
    ]

    def __init__(self, service: AnalyzeApartmentService) -> None:
        super().__init__()
        self.service = service

    def compose(self) -> ComposeResult:
        yield Vertical(
            _top_bar("workspace/buyer-profiles", self.service),
            Horizontal(
                VerticalScroll(
                    Static("PROFILE", classes="pane-title"),
                    Static("PROFILE ID", classes="field-label"),
                    Input(placeholder="first_time_buyer", id="profile-id"),
                    Static("ADULTS", classes="field-label"),
                    Input(value="1", id="profile-adults"),
                    Static("CHILDREN", classes="field-label"),
                    Input(value="0", id="profile-children"),
                    Static("MONTHLY CHILDCARE COST DKK", classes="field-label"),
                    Input(value="0", id="profile-childcare"),
                    Static("VEHICLES", classes="field-label"),
                    Input(value="0", id="profile-vehicles"),
                    Static("NET MONTHLY INCOME DKK", classes="field-label"),
                    Input(placeholder="47000", id="profile-net-income"),
                    Static("GROSS ANNUAL INCOME DKK", classes="field-label"),
                    Input(placeholder="960000", id="profile-gross-income"),
                    Static("SAVINGS DKK", classes="field-label"),
                    Input(placeholder="550000", id="profile-savings"),
                    Static("EXISTING DEBT DKK", classes="field-label"),
                    Input(value="0", id="profile-existing-debt"),
                    Static("MONTHLY DEBT PAYMENTS DKK", classes="field-label"),
                    Input(value="0", id="profile-monthly-debt"),
                    Static("DESIRED DOWN PAYMENT DKK", classes="field-label"),
                    Input(placeholder="300000", id="profile-down-payment"),
                    Static("RISK TOLERANCE", classes="field-label"),
                    Input(value="balanced", id="profile-risk"),
                    Static("EMPLOYMENT NOTES", classes="field-label"),
                    Input(placeholder="Permanent employment", id="profile-notes"),
                    CommandTable(
                        id="profile-command-table",
                        cursor_type="row",
                        show_header=False,
                        show_row_labels=False,
                    ),
                    Static("", id="profile-status", classes="status-line"),
                    classes="form-pane",
                ),
                Vertical(
                    Static("SAVED PROFILES", classes="pane-title"),
                    DataTable(
                        id="profile-list",
                        cursor_type="row",
                        show_row_labels=False,
                        zebra_stripes=True,
                    ),
                    Static("", id="profile-detail", classes="describe-body"),
                    classes="output-pane",
                ),
                classes="main-split",
            ),
            _key_bar(
                ("up/down", "Move"),
                ("enter", "Run command"),
                ("s", "Save profile"),
                ("esc", "Back"),
                ("q", "Quit"),
            ),
            classes="screen-frame",
        )

    def on_mount(self) -> None:
        commands = self.query_one("#profile-command-table", DataTable)
        commands.add_column("KEY", width=5)
        commands.add_column("ACTION", width=24)
        commands.add_row("s", "save-profile", key="save")

        profiles = self.query_one("#profile-list", DataTable)
        profiles.add_column("PROFILE", width=20)
        profiles.add_column("NET/MO", width=14)
        profiles.add_column("SAVINGS", width=14)
        profiles.add_column("RISK", width=12)
        self._refresh_profile_table()
        self.set_timer(0.05, self.query_one("#profile-id", Input).focus)

    @on(DataTable.RowSelected, "#profile-command-table")
    async def profile_command_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value == "save":
            await self.action_save_profile()

    @on(DataTable.RowHighlighted, "#profile-list")
    def profile_highlighted(self, event: DataTable.RowHighlighted) -> None:
        profile_id = event.row_key.value
        if profile_id is not None:
            self._show_profile_detail(str(profile_id))

    async def action_save_profile(self) -> None:
        status = self.query_one("#profile-status", Static)
        try:
            profile = self._profile_from_form()
            self.service.save_buyer_profile(profile)
        except Exception as exc:
            status.update(Text(f"profile error: {exc}", style="bold #ff6b6b"))
            return

        self._refresh_profile_table()
        self._show_profile_detail(profile.buyer_id)
        status.update(Text(f"saved profile {profile.buyer_id}", style="bold #7ddf64"))

    def _profile_from_form(self) -> BuyerProfile:
        profile_id = self._input_value("profile-id")
        if not profile_id:
            raise ValueError("profile id is required")
        return BuyerProfile(
            buyer_id=profile_id,
            household=HouseholdProfile(
                adults=self._required_int("profile-adults"),
                children=self._required_int("profile-children"),
                monthly_childcare_cost_dkk=self._required_int("profile-childcare"),
                vehicles=self._required_int("profile-vehicles"),
            ),
            gross_annual_income_dkk=self._required_int("profile-gross-income"),
            net_monthly_income_dkk=self._required_int("profile-net-income"),
            savings_dkk=self._required_int("profile-savings"),
            existing_debt_dkk=self._required_int("profile-existing-debt"),
            monthly_debt_payments_dkk=self._required_int("profile-monthly-debt"),
            desired_down_payment_dkk=self._optional_int("profile-down-payment"),
            employment_notes=self._input_value("profile-notes") or None,
            risk_tolerance=self._input_value("profile-risk") or "balanced",
        )

    def _refresh_profile_table(self) -> None:
        table = self.query_one("#profile-list", DataTable)
        table.clear()
        for profile in self.service.available_buyer_profiles():
            table.add_row(
                profile.buyer_id,
                _format_dkk(profile.net_monthly_income_dkk),
                _format_dkk(profile.savings_dkk),
                profile.risk_tolerance,
                key=profile.buyer_id,
            )

    def _show_profile_detail(self, profile_id: str) -> None:
        profile = next(
            (
                candidate
                for candidate in self.service.available_buyer_profiles()
                if candidate.buyer_id == profile_id
            ),
            None,
        )
        if profile is None:
            return
        self.query_one("#profile-detail", Static).update(
            "\n".join(
                [
                    f"[b]{profile.buyer_id}[/b]",
                    f"Adults: {profile.household.adults}",
                    f"Children: {profile.household.children}",
                    f"Monthly childcare: {_format_dkk(profile.household.monthly_childcare_cost_dkk)}",
                    f"Vehicles: {profile.household.vehicles}",
                    f"Net monthly income: {_format_dkk(profile.net_monthly_income_dkk)}",
                    f"Gross annual income: {_format_dkk(profile.gross_annual_income_dkk)}",
                    f"Savings: {_format_dkk(profile.savings_dkk)}",
                    f"Existing debt: {_format_dkk(profile.existing_debt_dkk)}",
                    f"Monthly debt payments: {_format_dkk(profile.monthly_debt_payments_dkk)}",
                    f"Risk: {profile.risk_tolerance}",
                    f"Notes: {profile.employment_notes or '-'}",
                ]
            )
        )

    def _input_value(self, widget_id: str) -> str:
        return self.query_one(f"#{widget_id}", Input).value.strip()

    def _required_int(self, widget_id: str) -> int:
        value = self._input_value(widget_id)
        if not value:
            raise ValueError(f"{widget_id.replace('-', ' ')} is required")
        return int(value)

    def _optional_int(self, widget_id: str) -> int | None:
        value = self._input_value(widget_id)
        if not value:
            return None
        return int(value)


class BoligmesterApp(App[None]):
    TITLE = "Boligmester"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "back", "Back"),
    ]
    CSS = """
    Screen {
        background: #070b0f;
        color: #d8dee9;
    }

    .screen-frame {
        height: 1fr;
        background: #070b0f;
    }

    .top-bar {
        height: 1;
        padding: 0 1;
        background: #17313a;
        color: #dff6ff;
        text-style: bold;
    }

    .key-bar {
        height: 1;
        padding: 0 1;
        background: #111820;
        color: #aeb7c1;
        dock: bottom;
    }

    .main-split {
        height: 1fr;
    }

    .resource-pane {
        width: 58%;
        height: 1fr;
        border: solid #20343c;
        background: #080e13;
    }

    .describe-pane {
        width: 1fr;
        height: 1fr;
        border: solid #20343c;
        background: #0b1117;
    }

    .single-pane {
        height: 1fr;
        margin: 1 2;
        border: solid #20343c;
        background: #0b1117;
    }

    .form-pane {
        width: 43%;
        min-width: 42;
        height: 1fr;
        padding: 0 1;
        border: solid #20343c;
        background: #080e13;
    }

    .output-pane {
        width: 1fr;
        height: 1fr;
        border: solid #20343c;
        background: #0b1117;
    }

    .pane-title {
        height: 1;
        padding: 0 1;
        background: #0f2229;
        color: #00d7ff;
        text-style: bold;
    }

    .describe-body {
        height: 1fr;
        padding: 1 2;
        color: #d8dee9;
    }

    DataTable {
        height: 1fr;
        background: #080e13;
        color: #cbd5df;
    }

    DataTable > .datatable--header {
        background: #0f2229;
        color: #00d7ff;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #00d7ff;
        color: #001017;
        text-style: bold;
    }

    DataTable > .datatable--odd-row {
        background: #0a1117;
    }

    #command-table, #search-command-table, #profile-command-table {
        height: 5;
        margin-top: 1;
    }

    Input, Select {
        margin: 1 0;
        border: none;
        background: #020609;
        color: #e5edf5;
    }

    Input:focus, Select:focus {
        border: solid #00d7ff;
    }

    .field-label {
        margin-top: 1;
        color: #7ddf64;
        text-style: bold;
    }

    .profile-table {
        height: auto;
        min-height: 5;
        color: #aeb7c1;
        background: #0b1117;
        padding: 1 1;
    }

    .status-line {
        height: 2;
        margin-top: 1;
        padding: 0 1;
        background: #0b1117;
        color: #d8dee9;
    }

    .tile-row {
        height: auto;
    }

    .tile {
        width: 1fr;
        min-height: 4;
        padding: 1 2;
        border-right: solid #20343c;
        background: #080e13;
        color: #d8dee9;
        text-align: center;
    }

    .report-pane {
        height: 1fr;
        padding: 1 2;
        background: #0b1117;
        color: #d8dee9;
    }

    Markdown {
        color: #d8dee9;
    }
    """

    def __init__(self, service: AnalyzeApartmentService) -> None:
        super().__init__()
        self.service = service

    def on_mount(self) -> None:
        self.push_screen(MenuScreen())

    def action_back(self) -> None:
        if len(self.screen_stack) > 2:
            self.pop_screen()

    def action_focus_next_control(self) -> None:
        self.screen.focus_next("DataTable, Input, Select")

    def action_focus_previous_control(self) -> None:
        self.screen.focus_previous("DataTable, Input, Select")


def _entry_by_key(key: str) -> MenuEntry:
    return next(entry for entry in MENU_ENTRIES if entry.key == key)


def run_textual_app(service: AnalyzeApartmentService) -> None:
    BoligmesterApp(service).run()
