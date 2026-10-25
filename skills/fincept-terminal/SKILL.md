---
name: fincept-terminal
description: Use Fincept-Corporation/FinceptTerminal for source-backed equity research, portfolio risk, analytics discovery, backtest review and integration readiness in TradeAgent-HK. Trigger when the user names Fincept, FinceptTerminal or Fincept Terminal, requests its Skill or checks whether it is installed or connected to daily reports. Separate Skill registration, desktop installation, provider access and working runtime integration.
---

# Fincept Terminal research for TradeAgent-HK

Read [references/upstream.md](references/upstream.md) for the reviewed upstream, actual source routes and setup. Read [references/project-status.json](references/project-status.json) for the dated inspection baseline; recheck current code before claiming runtime status.

## Check readiness first

1. Resolve the current TradeAgent-HK revision and repository instructions. Inspect skills, discovery links, .gitmodules, dependencies, caller code and relevant Actions workflows. Search both Fincept and FinceptTerminal. Do not infer a working integration from a prior conversation, README link or Skill alone.
2. Report these separately: Skill registered; desktop/source available; dependencies usable; provider/account access verified; adapter implemented; actual research execution verified; report inclusion verified; Telegram receipt confirmed. Mark unchecked stages NOT_VERIFIED, not working or broken.
3. Inspect the actual installed Fincept revision. The reviewed application is a C++20/Qt6 desktop terminal with embedded Python analytics, not a single interchangeable Python package or a default headless service.
4. Verify source interfaces and dependency manifests before invoking a module. Some upstream documentation names paths absent from the reviewed tree; prefer actual files and definitions. Never invent a pip package, import, CLI, MCP server address or HTTP endpoint.

## Choose bounded research

- Equity: use current fundamentals, financial statements, announcements and documented assumptions for valuation. Establish currency, period, corporate actions and the relationship to the existing four analysts.
- Portfolio: require timestamped positions, signed quantities, cash, currency, contract multipliers and account capacity. Treat stale journals as historical records. Separate allocation, concentration, Greeks, margin and nonlinear stress.
- Options: locate the relevant analytics source, verify its contract assumptions and required inputs. Keep theoretical prices, sampled forecasts and executable quotes distinct. Apply the existing option-volatility Skill and current project gates independently.
- Backtests: fix universe, horizon, signal/entry timing and assumptions before testing. Use chronological evaluation, costs, slippage and like-for-like benchmarks. Disclose pretraining overlap, corporate-action and survivorship issues. A stock forecast evaluation does not validate option profitability.
- Data/news: identify the underlying provider, instrument coverage, publication/quote time, timezone, cache age, adjustment convention and units. Fincept is an application/aggregation layer; its presence does not certify the provider or establish HKEX option-chain coverage.

## Execute only verified interfaces

Keep Fincept source/builds and optional analytics dependencies isolated from TradeAgent-HK's daily environment. For setup use the pinned upstream getting-started guide, actual toolchain manifests and a separate directory; do not run remote setup scripts blindly or globally replace project dependencies.

For a selected analytics module, read the source and its imports, find an existing entry point or documented interface, inspect required credentials, then run a bounded smoke calculation. Distinguish arithmetic/API smoke tests from actual provider responses and investment-performance tests. Use already authorized accounts/providers; adding this Skill alone does not subscribe to services, spend LLM credits or configure brokerage execution.

For data-bearing outputs retain provider, observed/retrieved times in Asia/Hong_Kong, ticker/exchange, currency, adjustment convention, input hash or source link, method and module revision. Check missing/nonfinite data, OHLC order, units, date alignment and event coverage. For independent price verification use a genuinely independent underlying source: Fincept reading Yahoo does not independently corroborate a yfinance download.

## Preserve TradeAgent-HK decisions

- Retain independent technical, sentiment, news and fundamental analysts, investment debate and risk review. Use Fincept as supporting evidence, not a replacement analyst or proof that all advertised agents ran.
- Use the current GitHub watchlist and verified current holdings. Accept sufficient timestamped manual option-chain inputs; do not require Futu CSV.
- Apply current option rules: research stock direction separately, require valid IV/Greeks, stable executable bid/ask, liquidity, events and account/assignment/coverage capacity. Unknown conditions mean WAIT. Never invent a strike, expiry, premium, margin or probability of profit to complete a recommendation.
- Keep the existing token budget, once-daily delivery, deadline, deduplication and confirmed receipts. Registering this Skill does not add Fincept to Python prompts or reports. A production adapter must have explicit input/output validation, bounded runtime, stale-data handling, failure isolation and an observed report path before it can be described as connected.
- Do not place orders or activate live trading. Keep private holdings, credentials, journals and user attachments out of the public repository and logs.

## Return an honest status or research result

Use concise Traditional Chinese/Cantonese unless requested otherwise. For status requests return the checked revision, evidence and each readiness stage. For research return data cutoff/provider, method, result, missing inputs, option eligibility and next verification. Say NOT_RUN when execution was not performed. Do not present a newly registered Skill as a running desktop terminal, live market-data connection, independent data certification or confirmed Telegram delivery.
