# Watchlist Workflow

Watchlist tracking is a first-class workflow over saved apartments. It records
the latest observed listing signals and surfaces structured changes when a saved
candidate changes between refreshes.

## Inputs

The watchlist workflow accepts saved apartments from the local workspace. A
refresh can run for all saved apartments or for a specific saved id set.

## Tracked Signals

Each watchlist snapshot stores:

* title and URL
* asking price
* area
* room count
* owner cost
* price per m2
* observation timestamp

On the first refresh, Boligmester creates a baseline snapshot. Later refreshes
compare the current saved-apartment fields with the last snapshot and emit
field-level changes with the old value, new value, saved apartment id, and
detection timestamp.

## Persistence

Watchlist state lives in the local workspace:

* latest snapshots in `watchlist/snapshots/*.json`
* refresh runs in `watchlist/runs/*.json`

The saved apartment remains the local source of truth for the current candidate
fields. Watchlist snapshots are the observation history used for change
detection.

## TUI

Open the Textual TUI and press `6` from the main menu. Press `r` to refresh
tracking. The watchlist view shows each saved apartment as `new` or `tracked`
and displays the structured changes from the latest refresh.

## Current Limits

The first watchlist workflow detects changes from saved apartment field updates.
It does not yet fetch live listing pages on a schedule, track listing status, or
send notifications.
