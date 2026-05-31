# Boligmester

`boligmester` is an open-source, terminal-first property buying assistant for the Danish housing market.

It is being built around Google ADK, deterministic finance logic, and evidence-aware property analysis.

## Status

This is still an early build focused on the first usable apartment analysis workflow.

Current implementation includes:

* delivery planning in `plan.md`
* mission, vision, and goals in `plan.md`
* a typed application service layer under `src/`
* deterministic finance calculations
* calibrated Danish finance screening assumptions
* listing ingestion with fixture, live-fetch, browser-fallback, and imported-capture paths
* manifest-backed listing regression fixtures
* apartment search workflow with fixture/live-fetch parsing and local persistence
* saved-apartment workflow for revisiting candidate listings from the TUI
* a validation harness for real-world URL sets
* an explicit top-level analysis workflow graph with deterministic nodes and an ADK agent boundary
* a terminal UI for URL analysis, apartment search, and buyer profiles
* local workspace persistence for buyer profiles, search runs, saved apartments, and analysis run metadata

Still in progress:

* web productization and hosted workflows
* graph views and watchlist change tracking

## Read Next

* [Development setup](docs/development.md)
* [Contribution guide](docs/contributing.md)
* [Vision, mission, and goals](plan.md)
* [ADK analysis graph](docs/adk-analysis-graph.md)
* [Browser fetch contract](docs/browser-fetch-contract.md)
* [Finance boundary](docs/finance-boundary.md)
* [Finance policy calibration](docs/finance-policy.md)
* [MVP validation notes](docs/mvp-validation-aarhus.md)
* [Local workspace](docs/local-workspace.md)
* [Apartment search workflow](docs/search-workflow.md)
* [Saved apartments](docs/saved-apartments.md)

## Repository Layout

```text
src/apartment_agents/
  agents/
  city_adapters/
  finance/
  reports/
  storage/
  tools/
  tui/
tests/
examples/
docs/
```

## Principles

The project should stay honest about confidence, source quality, and missing data. It should not present shallow or weakly evidenced outputs as strong recommendations.

Active work tracking belongs in GitHub Issues, not local markdown backlog files.
