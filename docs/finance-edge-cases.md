# Finance Edge Cases - MVP Validation

Validation date:

* 2026-05-31

Purpose:

* record obvious finance edge cases for the current deterministic engine
* make approval behavior explicit before policy calibration work
* turn edge-case findings into follow-up GitHub Issues

## Cases Covered

1. Insufficient savings for the minimum 5% down payment
2. Debt factor above the current `4.0` policy threshold
3. Tight monthly stress buffer for a household with children
4. Zero-interest regression path in maximum-purchase calculations

## Current Expected Behavior

### Insufficient savings

If savings do not cover the minimum down payment, approval should be `low` even when income is otherwise strong.

### Debt factor breach

If total debt divided by gross annual income exceeds `4.0`, approval should be `low`.

### Tight stress buffer

If the household clears the down payment and debt-factor gates but fails the stress-buffer threshold, approval should drop to `medium`.

### Zero-interest path

The engine should still compute a finite maximum purchase price if nominal or stress interest is `0.0%`.

## Findings

* The core approval ladder is now covered by deterministic tests for `high`, `medium`, and `low` outcomes.
* A real regression was found and fixed: `maximum_purchase_price_dkk` could divide by zero when the interest rate was `0.0%`.
* The current thresholds are still placeholder policy settings. They are useful for workflow development, but they are not yet calibrated to live Danish lender policy.

## Follow-Up Work

1. Compare current debt-factor and buffer thresholds against documented Danish bank heuristics
2. Add explicit validation rules for impossible finance inputs such as zero or negative income
3. Add scenario fixtures for couples, children, and high-owner-cost apartments
