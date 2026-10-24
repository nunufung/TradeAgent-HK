---
name: kronos
description: Use shiyu-coder/Kronos for OHLCV candlestick forecasting and chronological evaluation of Hong Kong stocks in TradeAgent-HK. Use when the user names Kronos, requests model-based K-line price scenarios, compares forecasts with the four analysts or FinRL, or asks to prepare or validate Kronos inference. Keep stock forecasts separate from option eligibility.
---

# Kronos for TradeAgent-HK

Use Kronos as an optional quantitative research tool alongside the existing technical, sentiment, news and fundamental analysts. Read [references/upstream.md](references/upstream.md) for the reviewed revision, setup, model pairs and API. Read [references/hk-workflow.md](references/hk-workflow.md) for data validation, evaluation and report fields.

## Establish readiness

1. Inspect the current TradeAgent-HK checkout and repository instructions. Confirm ticker, bar frequency, horizon, data source and as-of time in Asia/Hong_Kong. Prioritize holdings and the existing watchlist for a broad review.
2. Distinguish Skill availability, dependencies installed, weights available, inference completed and out-of-sample evaluation completed. A saved Skill does not establish any later state. Verify actual outputs before claiming a run.
3. Use completed historical OHLCV bars and explicit future HKEX sessions. Accept sufficient timestamped manual inputs; do not reintroduce Futu CSV ingestion. Holdings and option-chain sheets alone are not stock-price histories.
4. If historical data, packages, weights or exchange-calendar coverage are missing, return NOT_RUN with missing inputs. Never substitute invented model predictions or imply a live connection exists.

## Run bounded research

- Use the reviewed upstream in an isolated environment. Start with Kronos-small and its base tokenizer; use mini only with its 2k tokenizer. Set device/context explicitly. Record source commit, weight revisions, seed, lookback, horizon, sampling parameters and elapsed time.
- Validate data before inference and validate predicted candles afterwards. Reject invalid values rather than silently repairing them. Record exclusions and reasons.
- When sufficient data exist, start with 400 completed daily bars and five future sessions. These workflow defaults are not validated optimal settings. Never pad history to meet them.
- Treat generated prices as model scenarios. The API averages sample_count paths internally; this is not an ensemble distribution or calibrated confidence interval. For dispersion retain separate single-path calls; label quantiles as uncalibrated model dispersion.
- Keep downloads, training and inference outside scheduled morning delivery. Registering this Skill adds no daily model calls, new analyst, Telegram command, execution or schedule change. Automatic Python report consumption requires a separately implemented and tested adapter; do not claim this Skill already supplies one.

## Combine evidence

- Give the technical analyst the scenario direction, horizon, data cutoff and contrary evidence. Preserve independent sentiment, news and fundamental findings, debate and risk review. Do not count Kronos as a fifth independent analyst or override evidence solely because the forecast differs.
- Compare with FinRL only on matching assets, periods, inputs, execution assumptions, costs and benchmarks. Distinguish forecast evaluation from reinforcement-learning strategy backtesting.
- Apply current repository option rules and the option-volatility Skill independently. A bullish forecast does not authorize a short put; a bearish forecast does not authorize a short call. Require timestamped manual option-chain inputs, IV/Greeks, liquidity, event review, account risk and assignment/coverage capacity. Missing required inputs imply WAIT.
- Never convert sampled price dispersion into implied volatility, Greek exposure, exercise probability or probability of profit. Do not use generated prices as executable quotes or replace support/resistance evidence with generated candles.

## Return concise evidence

Use Traditional Chinese/Cantonese unless requested otherwise. Report ticker, HKT as-of time, data cutoff/source, interval, horizon, actual run status, model/tokenizer revisions and scenario. Separate observed prices from generated values. Include evaluation status, analyst disagreement, missing inputs and independent option eligibility. Use N/A without an actual valid run.

For a backtest, require the chronological evaluation in references/hk-workflow.md before reporting performance. Do not promise profits, attach a win rate to untested forecasts or present stock-only tests as option validation.
