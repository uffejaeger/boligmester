# Boligmester Vision, Mission, and Goals

Status: guiding document

This file is not a delivery backlog.

Execution tracking should happen in GitHub Issues and pull requests.

## Mission

Help Danish home buyers make better property decisions with transparent, evidence-aware software.

Boligmester should make it easier to answer:

* can I afford this property?
* would a Danish bank likely approve this purchase?
* is the price defensible relative to the market?
* what are the main risks and missing facts?
* what should I investigate, negotiate, or reject before moving forward?

## Vision

Boligmester becomes the best open-source property buying intelligence stack for Denmark.

It should combine:

* deterministic finance calculations
* explainable property analysis
* structured due diligence
* multi-agent reasoning where reasoning actually helps
* source-aware reporting that shows confidence, evidence, and missing data honestly

The long-term product may extend beyond the terminal, but the core value is the analysis engine, not the interface shell.

## Guiding Star

If Boligmester makes a strong recommendation, that recommendation should be understandable, reviewable, and grounded in evidence.

The project should prefer:

* explicit uncertainty over fake certainty
* reproducible calculations over hand-wavy scoring
* typed interfaces over ad hoc glue
* real source provenance over polished-looking summaries
* narrow, test-backed improvements over shallow feature sprawl

## Product Principles

### Decision Support, Not Authority

Boligmester supports the buyer.

It does not replace:

* banks
* lawyers
* surveyors
* building experts

### Denmark First

The project is optimized for Danish property buying workflows, Danish data sources, and Danish credit logic.

### Deterministic Finance

Financial outputs must come from deterministic code.

Models may explain, summarize, or stress-test assumptions, but they must not own final finance numbers.

### Source Transparency

Every important conclusion should be traceable to:

* listings
* documents
* public data
* calculations
* explicit assumptions

### Honest Confidence

Weak or partial evidence should reduce confidence, not disappear behind a polished report.

## Near-Term Goals

The current product goals are:

1. analyze one Danish apartment listing well
2. support a buyer profile and deterministic affordability analysis
3. produce a report that clearly shows recommendation, evidence, risks, and gaps
4. validate the workflow against real-world Aarhus listings
5. migrate top-level orchestration to real ADK graph workflows

## Longer-Term Goals

After the first reliable apartment-analysis workflow, the next expansion paths are:

* deeper due diligence from property documents
* search, comparison, and watchlist workflows
* broader Danish city support
* a web product on top of the same service boundaries
* community contribution paths around data quality, validation, and agent behaviors

## Operating Model

Repository mechanics should enforce workflow rules.

The planning model is:

* `plan.md` defines direction
* GitHub Issues define work
* pull requests define implementation
* tests and CI define merge quality
