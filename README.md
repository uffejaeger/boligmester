# Boligmester

`boligmester` is an open-source, terminal-first property buying assistant for the Danish housing market.

The intended agent runtime is Google ADK. The mock runner exists only to support fixture-backed local development and tests while the live ADK path is being hardened.

## Project Status

This is still an early build.

What exists today:

* delivery planning in `plan.md`
* execution backlog in `todo.md`
* a typed application service layer under `src/`
* deterministic finance calculations
* parser-backed listing ingestion with fixture, live-fetch, browser-fallback, and imported-capture paths
* a validation harness for real-world URL sets
* a terminal UI for the first analysis flow

What is still in progress:

* real ADK runtime verification with sub-agent delegation
* ADK graph orchestration for the top-level analysis workflow
* broader real-world listing coverage and regression fixtures
* web productization and hosted workflows

## Local Setup

1. Use Python 3.11 or newer.
2. Create a virtual environment.
3. Install the package in editable mode:

```bash
pip install -e .
```

4. Set runtime configuration:

```bash
export ADK_BACKEND=google_adk
export GOOGLE_API_KEY=your_key_here
export ENABLE_LIVE_LISTING_FETCH=true
```

Use `ADK_BACKEND=mock` only for fixture-backed local development without the live ADK runtime.

If Boligsiden blocks plain HTTP fetches in your environment, enable the browser fallback and point it at a command that writes rendered HTML to stdout:

```bash
pip install -e '.[browser]'
python -m playwright install chromium
export ENABLE_BROWSER_LISTING_FETCH=true
export BROWSER_LISTING_FETCH_COMMAND='python3 scripts/fetch_rendered_listing.py {url}'
```

The command must contain `{url}` and print the final page HTML to stdout.
The bundled reference command uses Playwright and a local Chromium install.

To run a batch URL validation set:

```bash
PYTHONPATH=src python3 scripts/run_validation_set.py examples/validation/aarhus_urls.txt --buyer-profile-id solo_engineer
```

That command writes a timestamped JSON batch report under `output/validation/`.
Use `--stdout-json` if you want the full JSON batch report printed to stdout as well.

To import a saved listing HTML capture into the regression set:

```bash
PYTHONPATH=src python3 scripts/import_captured_listing.py \
  'https://www.boligsiden.dk/adresse/your-listing' \
  /path/to/captured.html
```

5. Run the scaffold entrypoint:

```bash
apartment-agents
```

## How We Work

This project is intended to be developed in the open with review-driven changes.

Expected contribution flow:

1. Create a branch.
2. Open a pull request.
3. Wait for review and approval before merge.

The target GitHub repository setup for `main` is:

* pull requests required before merge
* at least one approving review required
* stale approvals dismissed on new commits
* resolved conversations required before merge

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution expectations.

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

## Current Implementation Focus

The codebase currently has:

* an application service layer
* a deterministic finance engine
* an explicit finance service boundary
* parser-backed listing ingestion from HTML fixtures
* a browser-fallback listing fetch adapter for challenge-gated pages
* an ADK integration boundary with explicit Google ADK runner types
* a TUI that exercises the service layer

## Open Source Scope

The aim is to make the core analysis stack reusable and inspectable:

* typed domain models
* deterministic finance logic
* listing ingestion and extraction quality reporting
* ADK-based agent orchestration
* reproducible validation runs

The project should stay honest about confidence, source quality, and missing data. It should not present shallow or weakly evidenced outputs as strong recommendations.
