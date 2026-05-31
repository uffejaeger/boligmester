# Apartment Search Workflow

Boligmester exposes apartment search as a reusable workflow boundary before
comparison, ranking, and watchlists.

## Inputs

The search workflow accepts:

* city, for example `Aarhus C`
* source, currently `boligsiden`
* property type, currently `ejerlejlighed`
* optional query text
* optional max price, minimum area, and minimum rooms filters
* optional source search URL for live scraping experiments

## Runtime Behavior

With the default local configuration, search reads deterministic fixtures from
`examples/searches/`. When `ENABLE_LIVE_LISTING_FETCH=true`, the workflow fetches
the source search page and parses visible listing links from the returned HTML.
The browser fallback configuration used by listing URL analysis also applies to
search fetches.

Every search run is saved in the local workspace under
`search_runs/*.json`. Saved search results contain source URL, address, price,
area, room count, and parser metadata so saved-apartment, comparison, and
watchlist features can reuse the same rows.

## TUI

Open the Textual TUI and press `2` to search. The default city is `Aarhus C`.
After results load, select a row and press `a` to open the URL analyzer with that
listing URL prefilled, or press `s` to save it for comparison.
