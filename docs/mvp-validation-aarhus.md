# MVP Validation - Aarhus Listing Set

Validation date:

* 2026-05-31

Purpose:

* create a first real-world listing set for MVP validation
* record what the current implementation can and cannot handle
* turn validation findings into GitHub Issue follow-up work
* support repeatable reruns through the validation harness in `scripts/run_validation_set.py`

## Validation Set

The following Aarhus-area listing URLs were collected as candidate validation inputs:

1. `https://www.boligsiden.dk/adresse/odensegade-21-3-th-8000-aarhus-c-07510157___21___3____th`
2. `https://www.boligsiden.dk/adresse/aaparken-6-2-4-8000-aarhus-c-07510157___6___2____4`
3. `https://www.boligsiden.dk/adresse/frederiks-plads-8-5-5-8000-aarhus-c-07510157___8___5____5`
4. `https://www.boligsiden.dk/adresse/aaboulevarden-51c-st-8000-aarhus-c-07510157__51c____st_`
5. `https://www.boligsiden.dk/adresse/daugbjergvej-24-2-7-8000-aarhus-c-07510157___24___2____7`
6. `https://www.boligsiden.dk/adresse/vester-alle-24a-1-th-8000-aarhus-c-07510157__24a___1____th`

The same set is now stored in:

* `examples/validation/aarhus_urls.txt`

## Imported-Capture Validation Rerun

The repository now supports an explicit `imported_capture_preferred` validation mode through
`scripts/run_validation_set.py`.

The Aarhus set was rerun on 2026-05-31 with:

```bash
PYTHONPATH=src ./.venv/bin/python scripts/run_validation_set.py \
  examples/validation/aarhus_urls.txt \
  --buyer-profile-id solo_engineer \
  --listing-source-mode imported_capture_preferred \
  --output-json examples/validation/aarhus_imported_capture_report.json
```

Persisted report:

* `examples/validation/aarhus_imported_capture_report.json`

Rerun summary:

* total URLs: 6
* imported captures: 1
* ingestion errors: 5
* blocked outcomes: 0
* average extraction coverage for parseable outcomes: 1.0

The one imported capture that completed was:

* `odensegade-21-3-th-8000-aarhus-c-07510157___21___3____th`

Its result details were:

* status: `imported_capture`
* recommendation: `BUY`
* extraction method: `visible_html_regex`
* field coverage ratio: `1.0`

The remaining five URLs still failed deterministically because no captured HTML or listing fixture
exists for them and live fetches were intentionally not used in this mode.

## Current Live Validation Result

The current repository still cannot run the full Aarhus set end to end against the live site.

Reason:

* the repository has a live-fetch code path, a Boligsiden visible-HTML parser fallback, a browser-command fallback adapter, and a bundled Playwright reference script
* but a live Playwright fetch against Boligsiden still returns the Cloudflare challenge page rather than rendered listing content
* that means arbitrary listing URLs still cannot complete end to end here without a permitted first-party data source, imported captures, or a site workflow that explicitly allows automation

## Current Gaps Confirmed By Validation

### Parser Gap

The MVP still lacks:

* imported captures for most of the Aarhus validation URLs
* a permitted content path when live browser automation still lands on the Cloudflare challenge page
* normalization coverage testing against more than two fixture pages

### Workflow Gap

The current analysis path still depends on:

* one city-level market snapshot fixture
* mocked or simplified agent outputs
* no real document due diligence
* no live ADK runtime verification in this environment

### Confidence Gap

The current report can still look more complete than the underlying evidence base.

The main reasons are:

* market comps are not live
* negotiation logic is simplified
* due diligence agents are not yet powered by real source documents

## Follow-Up Work

Priority follow-ups from this validation set:

1. Add imported captures or fixture coverage for the five remaining Aarhus URLs
2. Add regression fixtures from at least five real listing layouts
3. Compare current recommendation strength against actual data coverage before labeling a result `BUY`
4. Verify the live ADK runtime separately from fixture-backed validation outcomes
