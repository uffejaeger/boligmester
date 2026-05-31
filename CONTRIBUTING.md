# Contributing to Boligmester

## Working Agreement

This repository uses a review-first workflow.

Rules:

1. Do not merge directly to `main`.
2. Open a pull request for every change.
3. Wait for review and approval before merge.
4. Resolve review comments instead of bypassing them.

The intended branch protection for `main` is:

* require pull requests before merging
* require at least one approving review
* dismiss stale approvals when new commits are pushed
* require all review conversations to be resolved

## What Good Contributions Look Like

Contributions should be narrow, test-backed, and explicit about tradeoffs.

Expectations:

* add or update tests with new behavior
* keep deterministic finance logic outside LLM-driven code
* preserve typed service boundaries
* document new environment variables, scripts, or workflows
* record meaningful follow-up work in `todo.md`

## Development Setup

1. Create a virtual environment with Python 3.11 or newer.
2. Install the project in editable mode:

```bash
pip install -e .
```

3. For browser-backed listing fetches, install the optional browser dependency and Chromium:

```bash
pip install -e '.[browser]'
python -m playwright install chromium
```

4. Run the test suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

## Pull Request Expectations

A pull request should include:

* the problem being solved
* the implementation approach
* risks, limitations, or follow-up work
* test coverage notes

If a change affects live listing ingestion, ADK orchestration, or finance policy, call that out explicitly in the PR description.

## Scope Discipline

Do not hide weak evidence behind confident language.

If a source is blocked, partial, or stale:

* surface that limitation in code and reporting
* add regression coverage where practical
* capture remaining work in `todo.md`
