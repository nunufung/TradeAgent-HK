# Source map and policy reconciliation

## User-provided screenshots (19 October 2026)

These descriptions are faithful summaries, not market research or independently validated strategies.

| File | Requested workflow | Requested deliverables |
| --- | --- | --- |
| IMG_0863.jpeg | 1. Trading ideas | Five opportunities; entry, target, stop, risk/reward; technical and fundamental rationale |
| IMG_0864.jpeg | 2. Technical analysis | Daily/weekly support, resistance, trendlines, moving averages, momentum; buy/wait/sell decision |
| IMG_0865.jpeg | 3. News to strategy | Short/long-term impact, price range, priced-in factors, positioning, invalidation |
| IMG_0866.jpeg | 4. Backtest | Win rate, profit factor, maximum drawdown, trade count, mean return, improvement ideas |
| IMG_0867.jpeg | 5. Portfolio risk | Weaknesses, overexposure, hidden correlations, risk-based rebalance, market -20% hedge scenario |
| IMG_0868.jpeg | 6. Trade journal | Latest 20 trades; recurring mistakes, missed opportunities, behavioral biases; three actionable rules |

## Project context inspected

- Repository: nunufung/TradeAgent-HK; base commit d0f65d298a0b8d262c8e6084e6dba8982ab70004.
- Existing book_skill_context.py POLICY: 21–45 DTE, absolute Delta <=0.10, margin/premium <=10, stable quotes after 10:00 HKT, 50–70% profit-taking and handling losses above 100% of original premium.
- Existing skills/analyze-hk-option-volatility/SKILL.md: separate stock thesis, volatility value, position Greeks and eligibility.
- User-supplied HKEX Options Trading Rules.docx: risk-first; one daily primary option; liquidity, DTE, margin, events and exit discipline.

Apply the current explicit user instructions and current deterministic project gates before generic screenshot prompts or legacy examples. The supplied rules document discusses discretionary short-DTE exceptions; do not use those to bypass the stricter runtime eligibility gate. The legacy skills/tradeagent-hk/SKILL_Option.md suggests 2–3 weeks and 0.25 Delta in an example; do not use those values under the current policy. Prefer manual timestamped option input per the user's subsequent data-ingestion instruction, despite the document's older CSV section.

The screenshot count of five is a research maximum, not an obligation to fabricate five trades; the project's daily primary-option count remains one. Evidence requirements, missing-data behavior, accounting definitions and validation methods in this skill are implementation safeguards added during adaptation, not claims contained in the screenshots. No historical trade records or personal portfolio spreadsheet contents are included in this public repository skill.

## Invocation and integration boundary

Invoke `$analyze-hk-trading-workflows` in Codex inside this repository. The `.agents/skills/analyze-hk-trading-workflows` symlink follows the repository's existing discovery convention and resolves to this skill directory.

The daily pipeline now injects references/daily-runtime.md into the existing four-analyst graph and records its fingerprint. market_recommendations.write_recommendations runs all six module evaluators, writes trading_workflows.json/.md, and includes six concise findings/statuses in final_summary.txt. Private optional data is processed locally, never sent to the model. Missing, malformed or stale data blocks the affected module without fabricated results. The backtest evaluator summarizes supplied historical runs; it does not execute a new strategy simulation. The existing budget, schedule, one-message delivery and option gates remain unchanged. See SIX_WORKFLOW_REPORT.md at repository root for input contracts and limitations.
