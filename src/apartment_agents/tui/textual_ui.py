from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rich.text import Text

from apartment_agents.app.services import AnalyzeApartmentRequest, AnalyzeApartmentService
from apartment_agents.models import BuyerProfile

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
        ready="0/1",
        status="Planned",
        kind="Workflow",
        summary="Saved searches and filters.",
        detail="Search workflow is not implemented yet. Next build step is saved search support.",
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
        name="watchlist",
        ready="0/1",
        status="Planned",
        kind="Store",
        summary="Saved apartments and change tracking.",
        detail=(
            "Watchlist support is not implemented yet. Next build step is local "
            "saved-apartment storage and change tracking."
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


class MenuScreen(Screen[None]):
    BINDINGS = [
        Binding("1", "open_analyzer", "Analyze"),
        Binding("2", "open_search", "Search"),
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


class AnalyzeScreen(Screen[None]):
    BINDINGS = [
        Binding("r", "run_analysis", "Run"),
        Binding("s", "load_sample", "Sample"),
    ]

    def __init__(self, service: AnalyzeApartmentService) -> None:
        super().__init__()
        self.service = service
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
                        value=SAMPLE_LISTING_URL,
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

    #command-table {
        height: 4;
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
