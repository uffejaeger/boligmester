# Contributing

## Contribution Expectations

Contributions should be narrow, test-backed, and explicit about tradeoffs.

Expected baseline:

* add or update tests with new behavior
* keep deterministic finance logic outside LLM-driven code
* preserve typed service boundaries
* document new environment variables, scripts, or workflows
* record meaningful follow-up work in GitHub Issues

## Writing Issues For AI-Assisted Execution

Issues should be concrete enough that an AI agent or another contributor can execute them without guessing the success condition.

Good issues should usually include:

* the goal
* what is in scope
* what is explicitly out of scope
* acceptance criteria stated as observable behavior
* validation steps or evidence expected
* a short `Done means` section

`Done means` should describe the completion bar in direct terms, for example:

* code path exists and is wired into the service
* tests cover the new behavior
* CI passes
* docs or issue follow-ups are updated if needed

Avoid issue bodies that only describe an idea without saying how completion will be judged.

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
