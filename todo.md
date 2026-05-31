# ApartmentBuyingAgents DK - Execution Backlog

This file turns the roadmap in `plan.md` into actionable work.

Status key:

* `[ ]` not started
* `[-]` in progress
* `[x]` done

---

# Overall Delivery Phases

## Phase 0 - Foundation & Contracts

Objective:

Create a runnable skeleton with stable interfaces, fixtures, and tests.

Exit criteria:

* One mocked apartment analysis runs locally from the TUI

## Phase 1 - MVP Single Apartment Analysis

Objective:

Analyze one apartment listing in Aarhus and produce a usable recommendation report.

Exit criteria:

* A user can provide a listing URL and buyer profile and receive a recommendation

## Phase 2 - Due Diligence Depth

Objective:

Support property documents and deeper risk assessment.

## Phase 3 - Discovery, Comparison & Watchlists

Objective:

Support search, saved apartments, comparison, and watchlists.

## Phase 4 - Multi-City Intelligence

Objective:

Expand beyond Aarhus and improve location and market context.

## Phase 5 - Productization & Community Ecosystem

Objective:

Add web product layers, hosting, and contributor workflows.

---

# Recommended Execution Order

1. Repository skeleton
2. Shared models and contracts
3. Application service layer
4. ADK runtime adapter
5. TUI shell
6. Listing ingestion
7. Deterministic credit engine
8. Buyer Committee orchestration
9. MVP agent implementations
10. Report generation
11. Fixtures and smoke tests
12. Validation on real sample listings

---

# Architecture Decisions

These are implementation constraints, not optional preferences.

## A0. Quality Bar

Test coverage is a first-class requirement.

Expectations:

* New behavior should normally ship with tests in the same slice
* Core finance logic should have deterministic numeric tests
* Parsers should have regression fixtures and parsing tests
* Application services should have end-to-end smoke coverage
* ADK integration boundaries should have contract tests and fallback-path tests
* Critical user workflows should keep growing integration coverage over time

## A1. Layering

The system should be built in this order:

```text
TUI
  -> application services
    -> ADK runtime adapter
      -> agent implementations
        -> tools / finance / storage / report rendering
```

Rules:

* The TUI must not contain business logic
* The TUI must not talk directly to provider SDKs
* ADK is the intended primary agent runtime
* ADK graph workflows should be the target orchestration model for top-level analysis flows
* Deterministic finance code must not depend on LLM output
* Report rendering should operate on structured report objects

## A2. First Vertical Slice

The first end-to-end slice is:

* [x] `AnalyzeApartmentService`
* [x] `AdkAnalysisRunner`
* [x] mocked MVP agent outputs behind the ADK boundary
* [x] a TUI flow for entering URL and buyer profile
* [x] Markdown report output

Done when:

* The user can enter a URL and buyer profile in the terminal and receive a saved report from a mocked multi-agent run

## A3. Depth Guardrails

To avoid building a shallow demo, each layer must be detailed enough to survive later replacement.

Requirements:

* [x] Every service input and output should be typed
* [x] Every recommendation should be traceable to findings
* [x] Every finding should support citations and warnings
* [x] Partial failures should be represented explicitly, not hidden
* [x] Mocked integrations should already match intended production interfaces
* [x] TUI flows should exercise the same service APIs the future web app will use

---

# Current Delivery Focus

The current build focus is the first detailed vertical slice:

1. config and startup validation
2. fixture-backed repositories
3. listing ingestion boundary
4. finance engine boundary and v1 calculations
5. ADK runner abstraction with mocked implementation
6. application service orchestration
7. report rendering
8. TUI analyze flow
9. end-to-end smoke test

The next build focus after that is:

1. explicit ADK-first integration
2. startup validation and failure modes
3. parser-backed listing ingestion
4. structured live ADK output rather than one aggregate response
5. separate ADK sub-agent execution rather than one committee prompt
6. live verification of ADK delegation with the installed runtime
7. migrate top-level apartment analysis orchestration to an ADK graph workflow

---

# Phase 0 Backlog

## P0.1 Repository Bootstrap

Goal:

Create the base package layout and local developer entrypoints.

Tasks:

* [x] Create `src/apartment_agents/`
* [x] Create `src/apartment_agents/agents/`
* [x] Create `src/apartment_agents/tools/`
* [x] Create `src/apartment_agents/finance/`
* [x] Create `src/apartment_agents/city_adapters/`
* [x] Create `src/apartment_agents/reports/`
* [x] Create `src/apartment_agents/storage/`
* [x] Create `src/apartment_agents/tui/`
* [x] Create `tests/`
* [x] Create `examples/`
* [x] Create `docs/`
* [x] Add `pyproject.toml`
* [x] Add `README.md`
* [x] Add `.env.example`

Done when:

* The project installs locally and exposes one runnable entrypoint

## P0.2 Core Domain Models

Goal:

Define the shared data structures before agent code spreads assumptions.

Tasks:

* [x] Define `Listing`
* [x] Define `BuyerProfile`
* [x] Define `HouseholdProfile`
* [x] Define `DocumentBundle`
* [x] Define `MarketSnapshot`
* [x] Define `AgentFinding`
* [x] Define `AnalysisReport`
* [x] Define `Recommendation` enum: `BUY`, `MAYBE`, `AVOID`
* [x] Define source citation shape
* [x] Define confidence score shape

Done when:

* All core workflows can pass typed data without ad hoc dictionaries

## P0.3 Agent Contracts

Goal:

Standardize how agents receive input and return findings.

Tasks:

* [x] Define a base agent request schema
* [x] Define a base agent response schema
* [x] Define citation requirements for every conclusion
* [x] Define error and warning fields for partial analysis
* [x] Define how agents report uncertainty
* [x] Define aggregation rules for the Buyer Committee
* [x] Define a minimal tool interface for external data fetches

Done when:

* Every MVP agent can implement the same interface shape

## P0.4 Deterministic Finance Boundary

Goal:

Keep financial logic isolated from LLM behavior from day one.

Tasks:

* [x] Define `finance/` package boundaries
* [x] Define which values are calculated versus explained
* [x] Define inputs required for affordability calculations
* [x] Define outputs required for approval likelihood and max price
* [x] Define stress test scenarios to support in v1
* [x] Add typed finance result models
* [x] Add deterministic affordability policy assumptions
* [x] Document non-LLM calculation rule in code comments or docs

Done when:

* No LLM-facing interface owns final financial numbers

## P0.5 Local Config & Secrets

Goal:

Make local development predictable without leaking secrets into code.

Tasks:

* [x] Define required environment variables
* [x] Add config loader
* [x] Add development defaults where safe
* [x] Add validation for missing config at startup
* [x] Add output directory bootstrap
* [x] Document local setup steps

Done when:

* A new developer can start the app with a documented setup flow

## P0.6 Fixtures & Test Harness

Goal:

Make it possible to build against stable sample inputs.

Tasks:

* [x] Add one sample Boligsiden listing fixture
* [x] Add one sample estate agent listing fixture
* [x] Add two buyer profile fixtures
* [x] Add one property document bundle fixture
* [x] Add a mocked market data fixture
* [x] Add fixture loading helpers
* [x] Add unit test structure
* [x] Add one end-to-end smoke test with mocked dependencies

Done when:

* The project has repeatable sample data for local testing

---

# Phase 1 Backlog

## P1.1 Textual TUI Shell

Goal:

Create the first usable terminal interface.

Tasks:

* [x] Implement startup screen
* [x] Implement main menu
* [x] Add "Analyze Apartment URL" flow
* [x] Add buyer profile selection or entry
* [x] Add placeholder screens for future flows
* [x] Add progress and error display
* [x] Add output path or report preview behavior
* [x] Make the TUI call application services only

Done when:

* A user can start the app and begin an analysis flow without raw CLI arguments

## P1.2 Listing Ingestion

Goal:

Turn one apartment URL into normalized listing data.

Tasks:

* [x] Add URL validation
* [x] Add parser selection by domain
* [x] Add Boligsiden parser
* [x] Add estate agent parser
* [x] Normalize price, address, rooms, area, monthly costs, and build year
* [x] Normalize optional fields such as balcony, floor, elevator, and energy label
* [x] Preserve source links and raw extracted content
* [x] Add fixture-backed ingestion path before live scraping
* [x] Add tests for parsing and normalization
* [x] Add HTTP page fetcher abstraction for live listing ingestion
* [x] Detect Cloudflare or JavaScript challenge pages explicitly
* [x] Add Boligsiden visible-HTML extraction fallback when fixture JSON is unavailable
* [-] Add live fetch and extraction for arbitrary Boligsiden listing pages
* [x] Add browser-capable fetch path for challenge-gated listing pages
* [x] Add a reference browser runtime script for the configured browser fetch command
* [x] Install and verify the bundled Playwright runtime locally
* [x] Add support for imported captured listing HTML when live automation is blocked
* [x] Add a captured-listing manifest format that maps user-provided HTML files to listing URLs
* [x] Prefer imported captured HTML before live browser automation when a matching capture exists
* [x] Add a CLI helper to ingest captured listing HTML into regression fixtures
* [ ] Evaluate a user-provided browser storage-state path for permitted session-backed fetches
* [x] Add field-level extraction confidence and missing-field reporting for live HTML parsing
* [ ] Add regression fixtures from at least five real listing layouts
* [ ] Expand regression fixtures to cover blocked pages, partial HTML, and layout drift

Done when:

* One supported URL produces a valid `Listing`

## P1.3 Danish Credit Engine v1

Goal:

Produce reliable affordability and approval calculations.

Tasks:

* [x] Define finance input object
* [x] Define finance output object
* [x] Implement debt factor calculation
* [x] Implement disposable income calculation
* [x] Implement housing cost calculation
* [x] Implement loan-to-value calculation
* [x] Implement mortgage and bank loan split assumptions
* [x] Implement interest stress test logic
* [x] Implement maximum purchase price calculation
* [x] Implement maximum safe purchase price calculation
* [x] Add tests with fixed numeric expectations

Done when:

* Finance outputs are deterministic and covered by tests

## P1.4 Buyer Committee Orchestration

Goal:

Coordinate analysis steps and assemble a final recommendation.

Tasks:

* [x] Define orchestration sequence for MVP agents
* [x] Add application service entrypoint for analysis requests
* [x] Add ADK runner interface between service and agent runtime
* [x] Implement request fan-out to each agent
* [x] Implement result collection and normalization
* [x] Implement recommendation synthesis rules
* [x] Implement disagreement handling between agents
* [x] Implement partial-failure behavior when one agent cannot complete
* [x] Add a mocked orchestration test

Done when:

* The committee can combine agent findings into one report object

## P1.5 MVP Agent Implementations

Goal:

Ship the first narrow agent set needed for useful output.

Tasks:

* [x] Implement Listing Agent
* [x] Implement Market Comps Agent with mocked or manually seeded comparable data
* [x] Implement Danish Credit Agent using finance package outputs
* [x] Implement Negotiation Agent with simple bid framing rules
* [x] Implement Red Team Agent with structured risk prompts
* [x] Define score normalization across these agents
* [x] Add mocked ADK-backed runtime path for these agents
* [x] Add live Google ADK runtime path for these agents
* [x] Define explicit live ADK sub-agent architecture and responsibilities
* [ ] Verify live ADK sub-agent delegation in a real installed runtime
* [ ] Build the top-level `Analyze Apartment URL` workflow as an ADK graph
* [ ] Route deterministic validation, ingestion, finance, and report assembly through graph nodes
* [ ] Use ADK agent nodes only for reasoning-heavy steps within that graph

Done when:

* The committee receives stable outputs from each required MVP agent

## P1.6 Report Generation

Goal:

Generate a readable buyer report from structured outputs.

Tasks:

* [x] Define Markdown report template
* [x] Add report filename strategy
* [x] Add summary recommendation section
* [x] Add affordability section
* [x] Add pricing and comps section
* [x] Add negotiation section
* [x] Add red-team risks section
* [x] Add assumptions and missing-data section
* [x] Add citations and evidence appendix

Done when:

* A complete analysis produces a Markdown file a buyer can review

## P1.7 Logging, Errors & Validation

Goal:

Harden the MVP enough that failures are explainable.

Tasks:

* [x] Add structured logging
* [x] Add startup config validation
* [x] Add parse failure messages for unsupported or broken listings
* [x] Add agent timeout or fallback behavior
* [x] Add warnings for low-confidence outputs
* [x] Add user-facing messaging for missing buyer inputs
* [x] Add explicit service-layer exceptions for expected failure modes

Done when:

* Failures surface as actionable messages instead of opaque exceptions

## P1.8 MVP Validation

Goal:

Test the MVP on a small real-world sample before expanding scope.

Tasks:

* [x] Collect 5 to 10 Aarhus listing URLs
* [-] Run the MVP workflow against each listing
* [x] Build a batch validation harness for URL-set runs
* [x] Persist validation harness output to timestamped JSON reports
* [x] Add validation summary counts by status: fixture, live_html, blocked, ingestion_error, analysis_error
* [ ] Add a validation mode that uses imported captured HTML instead of live fetch
* [ ] Rerun the Aarhus validation set with the captured-HTML path once imports exist
* [x] Record missing fields and parser gaps
* [x] Record obvious finance edge cases
* [x] Record false confidence or weak recommendation patterns
* [ ] Record blocked-vs-parseable outcomes for each validation URL
* [ ] Record coverage ratios for each live or imported listing extraction
* [x] Update backlog based on findings

Done when:

* The first validation round has produced concrete follow-up work

---

# Later Phase Epics

## Phase 2 Epics

* [ ] Document ingestion pipeline
* [ ] Ejerforening analysis
* [ ] Legal analysis
* [ ] Building analysis
* [ ] Evidence-driven reporting
* [ ] Report formats for bank and lawyer workflows

## Phase 3 Epics

* [ ] Apartment search
* [ ] Saved apartments
* [ ] Comparison workflow
* [ ] Watchlist tracking
* [ ] Ranking and explainability

## Phase 4 Epics

* [ ] City adapter interface
* [ ] Copenhagen support
* [ ] Additional municipalities
* [ ] Location intelligence
* [ ] Neighborhood and market data pipelines
* [ ] What-if scenario inputs

## Phase 5 Epics

* [ ] Web application
* [ ] Hosted sessions and reports
* [ ] Plugin or extension model
* [ ] Operational safeguards
* [ ] Community benchmarks and contribution guides
* [-] Public GitHub repository setup for `uffejaeger/boligmester`
* [ ] GitHub branch protection requiring pull requests and approval on `main`
* [ ] OSS metadata: description, topics, social preview, and pinned docs
* [ ] Contributor governance: issue templates, PR template, review policy, and maintainer standards
* [ ] Initial public release checklist and first tagged version

---

# Next Suggested Build Slice

If work continues immediately, the highest-leverage slice is:

1. `P5 Productization & Community`
   - create the public `uffejaeger/boligmester` repository
   - apply branch protection and PR review requirements on `main`
   - publish OSS metadata and contributor workflow files
2. `P1.8 MVP Validation`
   - add imported-capture validation mode
   - rerun the Aarhus URL set through the validation harness
   - record blocked vs parseable outcomes and extraction coverage
3. `P1.5 MVP Agent Implementations`
   - verify live ADK delegation in a real installed runtime
   - move the top-level flow into an ADK graph

That slice closes the biggest gap between the current architecture and a truthful real-world MVP.
