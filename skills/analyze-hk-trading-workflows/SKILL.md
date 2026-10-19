---
name: analyze-hk-trading-workflows
description: Apply six evidence-based workflows to TradeAgent-HK stock and option research. Use for trading ideas, daily and weekly technical analysis, news-to-trade scenarios, strategy backtests, portfolio concentration and downside stress tests, or reviews of the latest 20 trades. Supports Cantonese and Traditional Chinese requests.
---

# HK trading research workflows

Use only the requested modules. For a broad review, prioritize current holdings and risk before new opportunities. Read [references/source-and-rules.md](references/source-and-rules.md) for screenshot provenance and project policy. These are research procedures, not six new autonomous agents or permission to place orders.

## Evidence and operating rules

- Establish the as-of date in Asia/Hong_Kong, tickers, instruments, horizon and available inputs. Use current cited market sources for current analysis; record quote timestamps and delays. Treat manual entries as timestamped user inputs; do not require Futu CSV.
- Keep verified facts, estimates, scenarios and missing data distinct. Never invent prices, chart levels, Greeks, correlations, holdings, probabilities or backtest results. A screenshot prompt is not market evidence.
- Retain the four existing analysts' independent evidence. Apply the existing option-volatility skill to option research, then independently enforce current project eligibility gates. A stock BUY does not mean an option is executable.
- For new short-option candidates apply 21–45 DTE, absolute Delta <=0.10 and initial margin/premium <=10. Require stable two-sided quotes after 10:00 HKT, adequate liquidity, event checks, account buffer and assignment capacity. Unknown or failed inputs imply WAIT/no eligible trade. Do not weaken gates to satisfy an idea count.
- Prioritize close/reduce/qualifying roll below 21 DTE. At 50–70% premium captured prioritize taking profit; losses exceeding 100% of initial premium require handling. Recheck all new-leg gates for a roll; report the realized loss separately.
- Verify contract multiplier, exercise terms, cash currency and signed position quantity. Do not assume one option contract equals 100 shares. Never treat low Delta, high IV or stop orders as a guarantee of limited loss.
- Respect the existing report length, token budget and delivery schedule. A premarket report is conditional research; refresh quotes at the permitted entry time. The daily Python pipeline uses the bounded routing instructions in references/daily-runtime.md and deterministic trading_workflows.py aggregation. It adds no model calls and preserves scheduling and budget limits.

## 1. Trading ideas / 交易點子產生器

Input: universe (stocks/index/sector), horizon, current holdings and timestamped price, volume, fundamentals and news.
Return up to five supported research candidates; return fewer or none when evidence is insufficient. Rank by evidence quality, portfolio fit and downside, not an unsupported claim of high probability.
For each provide ticker, direction, catalyst, technical and fundamental support, reference entry, target, stop/invalidation, reward-to-risk and key contrary evidence. For a long stock use (target-entry)/(entry-stop), only if target > entry > stop; reverse signs appropriately for short stock. Explain costs and gap risk. For options use the structure's payoff and risk rather than the stock formula; distinguish underlying price levels from option premium levels. Daily option output selects at most one primary contract, with up to three conditional alternatives when useful.

## 2. Technical analysis / 自動化技術分析師

Input: sufficient dated daily and weekly OHLCV, adjustment convention and indicator settings.
Analyze support/resistance zones, major trendlines, key moving averages and momentum changes. State indicator windows and level derivation; do not manufacture a chart from a ticker alone. Separate completed weekly bars from a partial week. Explain daily/weekly disagreement.
Return BUY / WAIT / SELL for the underlying with concise evidence, trigger and invalidation. State whether SELL means reducing an existing holding or a separately evaluated short thesis. Mark option eligibility separately.

## 3. News to strategy / 新聞轉交易策略

Input: company/sector, dated primary announcements and reliable reporting, current price response and event calendar.
Cite publication and event dates; separate confirmed events from rumors. Explain short- and long-term effects, transmission mechanism, beneficiaries and losers, and factors potentially priced in versus unresolved. Treat priced-in judgments as inferences.
Provide price-move scenarios only with a stated horizon and method (such as historical event moves or a documented volatility model); otherwise omit numeric ranges. Include positioning direction, thesis invalidation, event gaps and IV-crush risk. News sentiment alone never establishes an entry.

## 4. Strategy backtest / 交易策略回測分析師

Input: precise entry/exit rules, universe, dates, capital, sizing, historical data, fees, slippage and benchmark. If missing, return a specification and missing-input list, not results.
Use point-in-time data, chronological train/validation/test separation or walk-forward evaluation, and signals available before execution. Account for corporate actions, survivorship bias, transaction costs and parameter-search bias. For option tests require historical contracts/quotes and contract terms; label any model-derived proxy and never present a stock-only test as option validation.
Report closed-trade count, win rate (positive net-P/L trades / all closed trades, disclose breakevens), profit factor (positive net P/L / absolute negative net P/L), maximum drawdown from marked-to-market equity peaks, and mean net trade return with its denominator. Report undefined values as N/A, not zero. Include dates, exposure, costs, benchmark and out-of-sample results. Offer testable improvements without tuning to the held-out test or claiming future profit.

## 5. Portfolio risk / 投資組合風險管理

Input: holdings, signed quantities, costs, current marks, cash, currency, net asset value, options terms/Greeks, margin and risk tolerance. Verify weights and reconcile net and gross exposure, including leverage; premiums are not option exposure weights.
Identify concentration by issuer, sector and common risk factors. Compute correlations only from aligned return histories with disclosed window and sample size; otherwise describe qualitative shared drivers. Aggregate position Greeks using signed quantity and verified multiplier.
Evaluate a market -20% scenario with stated horizon, individual-underlying assumptions, IV increase, time decay, liquidity and margin stress. Fully reprice nonlinear option exposures where data/model permit; label a Delta-only estimate as unreliable for a large move. If inputs are absent, provide qualitative vulnerabilities, not invented stress P/L.
Propose rebalancing and hedge alternatives conditional on risk tolerance, cash and costs. State protection limits, basis risk, upside sacrifice and assignment/margin effects. Do not claim a hedge guarantees protection in every -20% market move.

## 6. Trade journal / 交易日誌分析師

Input: latest 20 completed trades, or all available if fewer; include entries, exits, position sizes, fees, results, original thesis and contemporaneous plans. Keep open positions separate and disclose sample size.
Link repeated mistakes to specific trade IDs and counts. Assess missed opportunities only against documented contemporaneous rules and signals, avoiding hindsight selection. Treat possible behavioral biases as hypotheses supported by records, not personality diagnoses; distinguish sound processes with bad outcomes from rule violations with good outcomes.
Finish with three measurable personalized rules: trigger -> action -> review metric. If evidence cannot support three personalized rules, explicitly label provisional suggestions and request the missing records. Do not fabricate trades to fill the sample.

## Output

Use concise Traditional Chinese/Cantonese unless asked otherwise:
1. As-of time, data sources and missing inputs.
2. Relevant module findings, with facts separated from assumptions.
3. Decision and conditions: 做 / 不做 / 等待 / 平倉 / Roll.
4. Principal risk, invalidation and next verification step.

For option decisions specify underlying, strategy, strike, expiry/DTE, executable premium basis, spread, Delta, margin/premium, maximum loss or unbounded exposure, profit/exit conditions and eligibility status. Use N/A for unavailable fields and withhold unconditional entry.

