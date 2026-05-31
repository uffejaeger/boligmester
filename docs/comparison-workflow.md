# Apartment Comparison Workflow

Apartment comparison is a first-class workflow over saved apartments. It turns
candidate listings into a persisted comparison report with deterministic finance
outputs, tradeoffs, and missing evidence.

## Inputs

The comparison workflow accepts:

* a buyer profile id
* at least two saved apartment ids

When started from the Textual TUI, the workflow compares all saved apartments in
the local workspace for the selected buyer profile.

## Runtime Behavior

Each comparison item includes:

* address, URL, asking price, area, rooms, owner cost, and price per m2 when known
* deterministic finance output for the selected buyer profile
* explicit tradeoffs against the other candidates
* missing evidence fields that should be checked before making a decision

Finance fields are only produced when the saved apartment has an asking price.
Missing structured fields remain visible in the output instead of being filled
with guessed values.

Comparison JSON is saved under `comparisons/*.json` in the local workspace.
Markdown output is written to `REPORT_OUTPUT_DIR`.

## TUI

Open the Textual TUI and press `5` from the main menu. Pick a buyer profile and
press `c` to compare the saved apartments.

## Current Limits

The first comparison workflow uses saved listing fields and deterministic
finance output. It does not yet merge full analysis findings from prior reports,
rank by subjective preferences, or render charts.
