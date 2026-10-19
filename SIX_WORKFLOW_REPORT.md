# Six workflows in the automatic report

The existing scheduled path is unchanged:
`daily_runner.py -> scripts/run-report.sh -> linked_stock_analysis.py -> market_recommendations.py -> final_summary.txt -> daily_delivery.py`.

The four-analyst graph now receives a bounded six-workflow routing policy from
`skills/analyze-hk-trading-workflows/references/daily-runtime.md`. Its SHA-256 is
recorded per stock as `workflow_skill`. Existing book context and option gates remain.
The recommendation writer evaluates all six modules and includes their results or
blocked reasons in the one daily message. Complete excerpts and aggregate calculations
are saved in `trading_workflows.json`, `trading_workflows.md` and `recommendations.md`.
Fallback messages also name all six modules and explicitly mark incomplete research.

## What runs

| Module | Daily processing | Missing-data behavior |
| --- | --- | --- |
| Ideas | Rank same-day complete four-analyst research; preserve stock and option separation | No candidates when research incomplete; no fabricated entries/targets |
| Technical | Instruct market analyst to cover daily/weekly levels, trends and momentum; retain sourced excerpts | Disclose missing histories/indicator evidence; no invented levels |
| News | Instruct news analyst to explain dated catalysts, horizons, priced-in assumptions and invalidation | No unsupported move range or new entry from sentiment alone |
| Backtest | Compute win rate, profit factor, maximum marked-to-market drawdown, count and mean net return from a supplied historical simulation | N/A without trades, equity, methodology and cost treatment |
| Portfolio | Reconcile a current full snapshot; stock-only concentration/gross exposure and explicit parallel -20% stock shock | Missing/stale snapshots block; option stress stays N/A pending full repricing inputs |
| Journal | Review latest 20 completed records (or fewer), aggregate documented violations and produce three measurable rules | No invented trades or diagnoses; rules without violation evidence are provisional |

This adds **zero model calls** but a small bounded instruction block to existing calls.
Token limits, two-stock daily shortlist, research deadline, pre-08:00 HKT delivery,
one-message claim and no-order behavior are unchanged. Five ideas is a maximum, not
an obligation. The backtest module summarizes an existing run; it does not execute
or independently validate a new historical strategy. Stock-only shock output is not
a forecast of a market-index fall. Arbitrary option repricing and inferred behavioral
biases are intentionally not fabricated.

## Optional private manual inputs

For GitHub daily runs, use repository Actions secret `TAHK_RESEARCH_INPUT_JSON`.
For a local run, set `TAHK_RESEARCH_INPUT_PATH` to a private JSON file; the JSON environment
variable takes precedence. No Futu CSV is required. The secret is scoped to the daily
research step. Missing configuration leaves the other modules working.

Monetary values must be finite, at most 1e15 in magnitude, and either zero or at least 1e-12 in magnitude.
Input must be a JSON object with `"schema_version": 1`; optional keys are `backtest`,
`portfolio`, and `journal`. Maximum UTF-8 size is 40,000 bytes. Timestamps must include
a timezone and must not be in the future. Portfolio and journal snapshots must be dated
today in Hong Kong time. This intentionally requires refreshing manually entered data.
Never commit raw holdings, personal trade IDs or this secret to the public repository.
Raw inputs do not enter model context or output artifacts; aggregate findings do appear
in the report and its existing GitHub artifacts. Treat those aggregate outputs according
to the repository's access policy.

### Common closed-trade record

```json
{
  "id": "example-001",
  "status": "closed",
  "entry_at": "2026-10-01T10:10:00+08:00",
  "exit_at": "2026-10-02T11:00:00+08:00",
  "net_pnl": 100,
  "capital_at_risk": 1000,
  "rule_violations": []
}
```

This is a synthetic schema example, not user holdings. Use consistent account currency
within a trade set. `net_pnl` includes all fees/slippage. `capital_at_risk` is a positive,
consistently defined denominator: mean return is the arithmetic mean of net_pnl divided
by that denominator, not an annualized portfolio return. Breakevens count in the win-rate
denominator. Profit factor is N/A if there are no losses. IDs must be unique; dates must
be ordered. Only completed trades belong in this input.

### Backtest object

Required nonempty strings: `strategy`, `universe`, `period`, `cost_model`,
`execution_model`, `data_source`, `out_of_sample`, `benchmark`, `instrument_type`
(`stock` or `option`). Provide exact rules, point-in-time data provenance, execution
lag and chronological validation methodology in those fields. Also provide:

- `costs_included: true`, `equity_marked_to_market: true`.
- `trades`: completed simulation trades in the format above.
- `equity`: at least two chronological objects with `at` (timestamp) and `value`.
  Include initial positive equity before entries and a final mark after exits;
  include open-position marks throughout, not only realized balance.
- For options also require `historical_option_quotes: true` and
  `contract_terms_checked: true`. These are supplied declarations, not independent
  verification; retain the underlying historical data and reproducible simulation.

### Portfolio object

Required: `as_of`, `complete: true`, `nav_hkd`, `cash_hkd`, and `holdings`.
Each holding has `underlying` (e.g. HK.00700), `asset_type` (`stock` or `option`),
and signed `market_value_hkd` (negative for short liabilities).
Cash plus all holding values must reconcile to NAV within max(HK$1, 0.1% NAV).
Options require a separate validated repricing model and account margin data for an
accurate large-move stress test; the module never substitutes market value for Greeks.
Risk tolerance, aligned return histories and account limits remain necessary before
personalized rebalancing/hedging recommendations; unavailable correlations are not guessed.

### Journal object

Required: today's `as_of`, `costs_included: true`, and `trades` in the common format.
Document actual violations using `late_exit`, `oversize`, or `unplanned_entry`.
An empty list means no documented violation, not proof of perfect execution.
No missed-opportunity or psychological diagnosis is made from P/L alone.

## Validation and rollout

Automated offline tests cover routing into the graph, all six output sections, private
input validation, stale snapshots, accounting metrics, equity drawdown, option stress
limitations, the last-20-trade window, omission of raw IDs, and the 1,200-character limit.
Existing summary, recommendation, token and delivery tests cover regression behavior.
No live paid research or Telegram message is required to validate this change. Next
scheduled research uses the updated code; an already-saved same-day report is not
replaced and no second daily message is sent.
