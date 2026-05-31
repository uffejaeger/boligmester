# Contributing

## Workflow

This repository uses a review-first workflow.

Rules:

1. Do not merge directly to `main`.
2. Open a pull request for every change.
3. Wait for review and approval before merge.
4. Resolve review comments instead of bypassing them.

Current `main` branch protection requires:

* pull requests before merge
* at least one approving review
* code owner review
* stale approvals dismissed on new commits
* resolved review conversations
* CI checks before merge

## Contribution Expectations

Contributions should be narrow, test-backed, and explicit about tradeoffs.

Expected baseline:

* add or update tests with new behavior
* keep deterministic finance logic outside LLM-driven code
* preserve typed service boundaries
* document new environment variables, scripts, or workflows
* record meaningful follow-up work in `todo.md`

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
* capture remaining work in `todo.md`
