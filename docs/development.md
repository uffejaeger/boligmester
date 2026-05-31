# Development Setup

## Requirements

* Python 3.11 or newer
* a virtual environment
* Google ADK credentials if you want the live ADK path

## Install

```bash
pip install -e .
```

For contributor and CI-equivalent tooling:

```bash
pip install -e '.[dev]'
```

For browser-backed listing fetches:

```bash
pip install -e '.[browser]'
python -m playwright install chromium
```

For the Textual TUI:

```bash
pip install -e '.[tui]'
```

## Runtime Configuration

Basic live configuration:

```bash
export ADK_BACKEND=google_adk
export GOOGLE_API_KEY=your_key_here
export ENABLE_LIVE_LISTING_FETCH=true
```

Use `ADK_BACKEND=mock` for fixture-backed local development without the live ADK runtime.

If Boligsiden blocks plain HTTP fetches in your environment, enable the browser fallback and point it at a command that writes rendered HTML to stdout:

```bash
export ENABLE_BROWSER_LISTING_FETCH=true
export BROWSER_LISTING_FETCH_COMMAND='python3 scripts/fetch_rendered_listing.py {url}'
```

The command must contain `{url}` and print the final page HTML to stdout.

If you need a session-backed browser context, point the runtime at a Playwright storage-state file:

```bash
export BROWSER_STORAGE_STATE_PATH=/absolute/path/to/storage-state.json
```

The bundled script also accepts `--storage-state`, so custom commands may pass
`{storage_state_path}` explicitly if they prefer argv over environment variables.
Treat the storage-state file like a secret and keep it out of git.

## Run

Start the terminal app:

```bash
boligmester
```

If you are running from a fresh venv, make sure the `tui` extra is installed first.

The legacy entrypoint still works:

```bash
apartment-agents
```

## Tests

Run the test suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

Run the local quality checks that match CI:

```bash
python -m ruff format --check .
python -m ruff check .
PYTHONPATH=src python3 -m unittest discover -s tests -q
python -m build --no-isolation
```

## Validation Harness

Run a batch URL validation set:

```bash
PYTHONPATH=src python3 scripts/run_validation_set.py examples/validation/aarhus_urls.txt --buyer-profile-id solo_engineer
```

That writes a timestamped JSON report under `output/validation/`.

Use `--stdout-json` to print the full JSON report as well.

## Live ADK Delegation Check

To verify that the installed Google ADK runtime delegates to the configured
sub-agents, run:

```bash
PYTHONPATH=src python3 scripts/verify_live_adk_delegation.py --stdout-json
```

See `docs/live-adk-delegation.md` for the evidence format and current local
runtime findings.

To prefer imported captured HTML deliberately before fixtures during validation:

```bash
PYTHONPATH=src python3 scripts/run_validation_set.py \
  examples/validation/aarhus_urls.txt \
  --buyer-profile-id solo_engineer \
  --listing-source-mode imported_capture_preferred
```

## Imported Listing Captures

Import a saved listing HTML capture into the regression set:

```bash
PYTHONPATH=src python3 scripts/import_captured_listing.py \
  'https://www.boligsiden.dk/adresse/your-listing' \
  /path/to/captured.html
```
