# Finance Policy Calibration

Research date:

* 2026-05-31

Purpose:

* keep affordability calculations deterministic and outside agent reasoning
* replace placeholder thresholds with a documented Danish screening heuristic
* make the remaining uncertainty explicit

This model is not a lender approval engine. It is a conservative first-pass screen
that helps the rest of the application avoid inventing finance numbers.

## Sources Reviewed

Primary sources:

* Finanstilsynet and Forbrugerombudsmanden, `VEJ nr 10137 af 24/11/2025`,
  `Vejledning om kreditværdighedsvurdering`:
  https://www.retsinformation.dk/eli/retsinfo/2025/10137/pdf
* Finanstilsynet, `VEJ nr 9299 af 20/04/2023`,
  `Vejledning om forsigtighed i kreditvurderingen ved belåning af boliger i
  vækstområder mv.`:
  https://www.retsinformation.dk/eli/retsinfo/2023/9299/pdf
* Justitsministeriet, `BEK nr 1431 af 24/11/2025`, 2026 changes to the debt
  restructuring allowance rates:
  https://www.retsinformation.dk/eli/lta/2025/1431/pdf
* Danmarks Nationalbank, analysis of Danish housing finance access:
  https://www.nationalbanken.dk/media/eqydcs2l/adgang-til-boligmarkedet-for-yngre-med-maalrettede-lempelser-i-finansieringen.pdf

Supporting lender-facing sources:

* Danske Bank, down payment and 80/15/5 financing explanation:
  https://danskebank.dk/privat/mit-liv/bolig/koebe-bolig/saa-meget-skal-du-selv-laegge-i-udbetaling-til-dit-boligkoeb
* Jyske Bank, realkredit and owner-occupied financing split:
  https://www.jyskebank.dk/bolig/boliglaan/hvad-er-et-realkreditlaan

## Implemented Assumptions

### Financing Split

Owner-occupied purchase financing is modelled as:

* 80% mortgage/realkredit
* 15% bank loan/after-financing
* minimum 5% buyer down payment before transaction costs

The engine rejects inputs that finance more than 95% of the purchase price or
put more than 80% into the mortgage share.

### Disposable-Income Buffer

The model now derives the minimum monthly buffer from the 2026 debt
restructuring allowance rates:

* 7,900 DKK for the first adult
* 5,500 DKK for each additional adult
* 3,970 DKK per child

The child amount deliberately uses the highest 2026 child bracket because the
buyer profile does not model child ages. This is conservative and should be
revisited if child ages are added.

### Stress Rate

The stress-rate floor is based on the growth-area guidance:

* use at least the nominal fixed rate plus 1 percentage point
* never use less than 4.0%

Callers can pass a higher explicit stress rate. Lower explicit rates are lifted
to the policy stress rate, so they cannot bypass the 4.0% floor or the
nominal-plus-1-point rule.

### Debt Factor

Debt factor is still total debt divided by gross annual household income.

The deterministic policy treats:

* up to 4.0 as `standard`
* above 4.0 and up to 5.0 as `elevated`
* above 5.0 as `high`

Debt factors above 4.0 no longer fail solely because they cross a hard
threshold. Instead, the model applies the growth-area price-shock heuristic:

* debt factor above 4.0 requires positive net wealth after a 10% home-price fall
* debt factor above 5.0 requires positive net wealth after a 25% home-price fall

Even when the shock test passes, approval is capped at `medium` because the
debt level is still elevated.

### Approval Ladder

The approval label is intentionally coarse:

* `low`: down payment is insufficient, stressed net wealth is negative for an
  elevated debt factor, or stressed disposable income turns negative
* `medium`: stressed disposable income is positive but below the buffer, or debt
  factor is elevated/high but shock resilience is positive
* `high`: down payment, debt factor, stress cost, and buffer checks all pass

## Remaining Approximation

The model does not yet include:

* transaction costs, moving costs, or post-purchase emergency reserve
* exact bank-specific living-cost models
* child ages, shared custody, transport mode, insurance, utilities, or
  maintenance budgets beyond listing owner costs
* future income, job security, wealth outside declared savings, or pension
  assets
* actual loan products, bid/offer spreads, contribution rates, tax effects, or
  amortization choices
* separate handling for cooperative housing, summer houses, bridge financing, or
  owning two homes at once

Those limitations are why results must remain framed as screening output rather
than lending advice.
