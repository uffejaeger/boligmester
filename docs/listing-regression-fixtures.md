# Listing Regression Fixtures

The listing regression set lives in `examples/listing_regressions/`. It is
separate from the primary happy-path examples so parser coverage can include
layout drift and known failure shapes without changing the default demo inputs.

## Manifest

`manifest.json` records one entry per fixture:

* `case_id`: stable test identifier
* `source`: parser source name, for example `boligsiden` or `estate_agent`
* `url`: the real listing URL shape the fixture represents
* `document`: HTML fixture file
* `expected`: parsed values, field coverage, missing fields, or failure class

Successful visible-HTML Boligsiden cases assert:

* `field_coverage_ratio`
* `missing_fields`
* core parsed fields: asking price, area, and rooms when present

Failure cases assert a named failure class and the ingestion error text. Current
failure classes include:

* `blocked_page`
* `missing_listing_markup`

## Covered Shapes

The current set covers:

* full visible Boligsiden listing card
* partial visible HTML with only address, price, and area
* label drift for price, area, rooms, owner costs, build year, and yes/no fields
* decimal area values
* blocked page shell
* JavaScript or cookie shell without listing details
* Estate embedded structured payload

Run the regression coverage through the normal listing tests:

```bash
PYTHONPATH=src python3 -m unittest tests.test_listings -q
```
