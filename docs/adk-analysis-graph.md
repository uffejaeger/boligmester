# ADK Analysis Graph

The single-apartment analysis flow is driven by `ApartmentAnalysisWorkflowGraph`.
The graph keeps deterministic application work separate from the ADK-owned
reasoning boundary.

| Node | Kind | Responsibility |
| --- | --- | --- |
| `validate_request` | deterministic | Normalize and validate the listing URL and buyer profile id. |
| `ingest_listing` | deterministic | Load a fixture, imported capture, or permitted live listing fetch. |
| `load_buyer_profile` | deterministic | Load the buyer profile fixture. |
| `load_market_snapshot` | deterministic | Load city-level market context when available. |
| `evaluate_finance` | deterministic | Run affordability calculations outside agent reasoning. |
| `run_adk_agents` | agent | Invoke the configured ADK analysis runner with structured context and finance output. |
| `assemble_report` | deterministic | Synthesize agent findings, fallback findings, assumptions, unresolved questions, and recommendation. |
| `write_report` | deterministic | Render and persist the Markdown report. |

## Failure Behavior

Validation, ingestion, buyer-profile, finance, and report-write failures stop the
graph at the failing deterministic node.

Agent-runner failures are contained at `run_adk_agents`: the graph logs the
failure, continues to `assemble_report`, and emits the existing finance-led
fallback recommendation path. This preserves a usable report when the ADK
runtime or live agent response is unavailable.
