# Saved Apartments

Saved apartments are the local workflow boundary for revisiting candidate
listings before comparison, ranking, and watchlist tracking.

## Stored Data

Saved apartments live in the local workspace under `saved_apartments/*.json`.
Each saved row stores:

* stable saved id
* source listing id and URL
* title and address
* asking price, area, rooms, and owner cost when available
* notes, tags, saved timestamp, and parser metadata

## TUI

Open the Textual TUI and press `2` to search. After selecting a result, press
`s` to save it. Press `6` from the main resource menu to list saved apartments,
then press `a` or `enter` to reopen a saved apartment in URL analysis.

Press `5` from the main menu to compare saved apartments for a buyer profile.

## Current Limits

Saved apartments do not yet track price changes, listing status changes, or
notifications. Those belong to the later watchlist workflow.
