# Browser Fetch Contract

Purpose:

* define the integration contract for challenge-gated listing fetches
* keep browser automation outside the core ingestion package

## When It Is Used

The browser fetch command is only used when:

1. live listing fetch is enabled
2. browser listing fetch is enabled
3. plain HTTP fetch returns a blocked-page signal such as a Cloudflare challenge

## Required Environment

* `ENABLE_LIVE_LISTING_FETCH=true`
* `ENABLE_BROWSER_LISTING_FETCH=true`
* `BROWSER_LISTING_FETCH_COMMAND=...{url}...`

Optional session-backed fetch support:

* `BROWSER_STORAGE_STATE_PATH=/absolute/path/to/storage-state.json`

## Command Contract

The configured command must:

* include a `{url}` placeholder
* fetch the fully rendered listing page for that URL
* print the final HTML document to stdout
* return exit code `0` on success
* return a non-zero exit code on failure

If session-backed fetches are needed, the command may also:

* read `BROWSER_STORAGE_STATE_PATH` from the environment
* accept a `{storage_state_path}` placeholder if it needs the path as an argv value

The command should not:

* print logs to stdout before the HTML
* require interactive input
* depend on TUI prompts or local manual steps

## Storage-State Decision

This repository supports an optional user-provided Playwright storage-state JSON file for
session-backed listing fetches.

Support is intentionally narrow:

* the configured path must point to an existing local file
* the storage-state file is only forwarded to the browser-fetch command path
* the bundled Playwright runtime consumes it through `browser.new_context(storage_state=...)`
* plain HTTP fetches never read or use the file

## Security And Operational Constraints

Treat the storage-state file as a local secret because it may contain active cookies or other
authenticated browser state.

Operational limits:

* do not commit storage-state files to the repository
* prefer short-lived session captures over long-lived personal browser profiles
* expect session expiry, MFA prompts, and challenge rotation to break reuse
* only use storage state for sites and accounts where you are permitted to automate access

## Current Limitation

This repository now bundles a reference Playwright script at `scripts/fetch_rendered_listing.py`.
It still depends on local installation of the Playwright Python package and browser binaries.
When live browser automation is still blocked, captured HTML can be imported with
`scripts/import_captured_listing.py` and used ahead of live fetches.
