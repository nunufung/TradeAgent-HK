# HK research procedure

## Validate inputs

1. Resolve exchange/ticker without losing leading zeros. Record provider, currency, share-volume and turnover units, interval and corporate-action adjustment convention.
2. Require unique, strictly increasing timestamps matching row count and numeric finite features. Require positive OHLC, high >= max(open, close), low <= min(open, close), high >= low and nonnegative volume/amount when present. Reject NaN or infinite values.
3. Use one consistent interval/adjustment convention. Check splits, dividends and suspensions; document gaps. Do not insert artificial traded bars across holidays, suspensions or lunch breaks.
4. Use Asia/Hong_Kong session labels and actual future exchange sessions, not generic weekdays. Respect lunch breaks, half-days, special closures and instrument-specific sessions. Stop before inference if required calendar coverage is unavailable.
5. Use completed bars available at the cutoff. Keep future prices out of model input, normalization and parameter selection; provide future timestamps only. Stay within the selected context limit and record exact lookback.
6. Keep private holdings, account details, journals and user attachments out of the public repository.

## Validate outputs

Require exactly pred_len rows, requested timestamps and expected columns. Reject nonfinite/nonpositive prices, invalid OHLC ordering and negative volume/amount. Return INVALID_OUTPUT and the reason; do not silently clamp a negative prediction. Label accepted rows as generated scenarios, with generation time, input cutoff, source/weight revisions, seed and parameters.

Compute endpoint scenario return as forecast_final_close / last_observed_close - 1 only after a valid run. State the horizon. Define bullish/neutral/bearish thresholds before outcomes, with documented costs or materiality threshold. Generated extrema are not established support/resistance.

## Evaluate chronologically

- Specify universe, timeframe, cutoff, rolling lookback, horizon, refit policy, preprocessing and parameters before evaluation. Use chronological train/validation/test splits or walk-forward analysis. Keep final test untouched during selection.
- Disclose potential foundation-model pretraining overlap. A historical walk-forward split does not prove weights never saw the test period. Mark unknown training cutoffs; prefer forward paper tracking after the reviewed checkpoint for uncontaminated evidence.
- Compare endpoint forecasts with last-close/no-change and any predefined historical-mean/simple-trend baseline. Report target MAE/RMSE and directional accuracy with exact denominator and zero-return handling. Normalize cross-stock errors with a documented method.
- Disclose dependence from overlapping forecast horizons. Daily five-session predictions do not constitute independent observations.
- For a strategy test, define executable entry/exit timing, capital, sizing, constraints, fees, HK charges, slippage and liquidity. Execute after signal inputs became available. Report net performance, drawdown, turnover, exposure, sample size, dates and comparable benchmark. A forecast alone is not a strategy/backtest.
- Keep FinRL strategy metrics separate from Kronos forecasting metrics. Require historical chains and contract terms for option tests. Stock histories cannot establish option profitability or eligibility.

## Compact reporting checklist

This is a reporting checklist, not an implemented data adapter.

| Field | Requirement |
| --- | --- |
| Status | NOT_RUN / INVALID_INPUT / INVALID_OUTPUT / FORECAST_ONLY / EVALUATED |
| Context | ticker, exchange, currency, interval, generation time, HKT data cutoff |
| Provenance | provider, adjustment convention, source commit, weight revisions |
| Parameters | device, seed, lookback, horizon, T, top-p, top-k, sample_count |
| Scenario | last observed close and generated endpoint/return; N/A without inference |
| Evaluation | baseline, test dates, sample size, metrics or not evaluated |
| Analysts | agreement/disagreement and independent evidence |
| Options | separate eligibility; WAIT when required inputs are missing |
| Limits | data gaps/staleness, pretraining overlap, uncalibrated dispersion, events |

Respect existing token/delivery policy. Never describe Skill registration as automatic Telegram/report integration. For an installation-only request, distinguish registration/validation from model readiness and live inference.
