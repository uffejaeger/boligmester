# Finance Boundary

The `src/apartment_agents/finance/` package is the deterministic financial core.

## Boundary Rules

Code outside the finance package may:

* create or receive `FinanceInputs`
* call the service-facing `FinanceBoundary`
* consume `FinanceResult`

Code outside the finance package must not:

* perform affordability calculations itself
* derive final approval numbers inside ADK agents or TUI code
* mix LLM reasoning with financial computation

## Internal Structure

* `models.py`
  Structured input and output types for deterministic calculations.
* `engine.py`
  Pure calculation logic and calibrated affordability policy.
* `service.py`
  The service-facing boundary used by the application layer.

## Intended Use

The application service should ask the finance boundary to evaluate a listing for a buyer.

That keeps:

* TUI code free of financial logic
* ADK code free of invented finance numbers
* report generation dependent on structured outputs instead of calculation internals

## Policy Calibration

See [Finance policy calibration](finance-policy.md) for the current Danish
screening assumptions, source review, and remaining approximation.
