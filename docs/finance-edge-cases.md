# Finance Edge Cases - MVP Validation

Validation date:

* 2026-05-31

Purpose:

* record finance edge cases for the deterministic engine
* make approval behavior explicit after policy calibration work
* keep regression scenarios tied to documented Danish screening assumptions

## Cases Covered

1. Insufficient savings for the minimum 5% down payment
2. Debt factor above the standard `4.0` policy threshold
3. Tight monthly stress buffer for a household with children
4. Zero-interest regression path in maximum-purchase calculations
5. Impossible finance inputs such as zero income, invalid household size, and
   over-95% purchase financing
6. Elevated debt factor with and without price-shock resilience

## Current Expected Behavior

### Insufficient savings

If savings do not cover the minimum down payment, approval should be `low` even when income is otherwise strong.

### Debt factor breach

If total debt divided by gross annual income exceeds `4.0`, approval should be
capped at `medium` when net wealth remains positive after the relevant
price-fall shock. It should be `low` when the shock leaves negative net wealth.

### Tight stress buffer

If the household clears the down payment and debt-factor gates but fails the stress-buffer threshold, approval should drop to `medium`.

### Zero-interest path

The engine should still compute a finite maximum purchase price if nominal or stress interest is `0.0%`.

### Impossible inputs

Inputs that cannot represent a valid screening case should raise `ValueError`
before calculations begin. Covered examples include zero or negative income,
zero asking price, no adults in the household, negative costs, and financing
shares that exceed the 80/15/5 owner-occupied split.

## Findings

* The core approval ladder is now covered by deterministic tests for `high`, `medium`, and `low` outcomes.
* A real regression was found and fixed: `maximum_purchase_price_dkk` could divide by zero when the interest rate was `0.0%`.
* Scenario fixtures now cover a single buyer, a couple with one child, a
  high-owner-cost apartment, and elevated debt-factor resilience checks.
* Finance assumptions are now documented in `docs/finance-policy.md`. They are
  still a screening heuristic, not a bank approval model.

## Follow-Up Work

1. Add transaction-cost and emergency-reserve handling
2. Model child ages instead of using the highest child allowance for every child
3. Add product-specific realkredit contribution rates and tax effects
