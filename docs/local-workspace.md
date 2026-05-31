# Local Workspace

Boligmester keeps user-created state in a local filesystem workspace. The
default workspace path is `output/workspace`, so local state survives app
restarts but remains outside git.

Set `BOLIGMESTER_WORKSPACE_DIR` to place the workspace somewhere else:

```bash
export BOLIGMESTER_WORKSPACE_DIR="$HOME/.boligmester"
```

## Stored Data

The first workspace version stores:

* buyer profiles in `buyer_profiles/*.json`
* apartment search runs in `search_runs/*.json`
* saved apartments in `saved_apartments/*.json`
* analysis run metadata in `analysis_runs/*.json`

Generated Markdown reports still live under `REPORT_OUTPUT_DIR` and analysis run
metadata points back to the report path.

## Buyer Profiles

Open the Textual TUI and press `p` from the resource menu to create a buyer
profile. Saved profiles are loaded alongside the bundled example profiles and
can be selected in the URL analyzer.

Profile ids may contain letters, numbers, underscores, and dashes.

## Search Runs

Open the Textual TUI and press `2` to search for apartments. Search runs are
saved with their input criteria and structured result rows. Those rows are the
local persistence boundary for later comparison, ranking, and watchlist
features.

## Saved Apartments

From the Textual TUI search screen, press `s` to save the selected apartment.
Press `6` from the main resource menu to revisit saved apartments and open one in
the URL analyzer.

## Current Limits

The workspace does not yet store watchlist change tracking, report annotations,
or dashboard state. Those are the next product workflow layers on top of this
persistence boundary.
