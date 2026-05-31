# Contributing

## Contribution Expectations

Contributions should be narrow, test-backed, and explicit about tradeoffs.

Expected baseline:

* add or update tests with new behavior
* keep deterministic finance logic outside LLM-driven code
* preserve typed service boundaries
* document new environment variables, scripts, or workflows
* record meaningful follow-up work in GitHub Issues

## Pull Requests

A pull request should include:

* the problem being solved
* the implementation approach
* risks, limitations, or follow-up work
* test coverage notes

If a change affects live listing ingestion, ADK orchestration, or finance policy, call that out explicitly.

## CI Expectations

The repository CI should stay fast enough for routine pull requests, but strict enough to gate merges.

Current baseline:

* Ruff format check
* Ruff lint
* unit tests
* package build verification

Dependabot is enabled for both Python dependencies and GitHub Actions.

## Scope Discipline

Do not hide weak evidence behind confident language.

If a source is blocked, partial, or stale:

* surface that limitation in code and reporting
* add regression coverage where practical
* capture remaining work in GitHub Issues
