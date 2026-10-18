# Fincept analytics in TradeAgent-HK

TradeAgent-HK uses selected Python analytics from FinceptTerminal v4.5.1 to add numerical evidence to the existing four analysts and option research. The desktop application, broker execution features and additional AI agents are not installed.

## What runs

| Capability | Input | Result |
| --- | --- | --- |
| Technical indicators | 80–300 completed daily OHLCV bars | RSI14, SMA20, MACD, ATR14, plus 20-return realized volatility annualized with sqrt(252) |
| Quoted volatility skew | Same underlying and expiry, with put/call IV across strikes | Approximate 5% OTM put IV minus call IV; not a delta-matched risk reversal |
| Expiry payoff | Verified quote time, bid, strike, option type and actual multiplier | Hypothetical one-contract short payoff before costs; sampled minimum is not maximum loss |
| Model Greeks and stress scenarios | Above inputs plus explicit decimal rate and dividend yield | European Black-Scholes-Merton diagnostics, signed short-contract Greeks and full repricing scenarios |

Daily cloud research, the Mac option workflow and manually requested Telegram stock research enable `TAHK_FINCEPT_ENABLED=1`. For direct Python invocations, set that environment variable to enable public-history enrichment. Set it to `0` to disable optional enrichment. No new account, Fincept subscription or Fincept API key is required by this integration.

Each selected stock gets one public daily-history request through yfinance, with a 12-second process limit, followed by at most 10 seconds of local analytics. Public history uses adjusted daily OHLCV and excludes the current incomplete session. A last observation older than seven calendar days is rejected; this is a freshness bound, not a Hong Kong exchange-calendar check. Failed fetches produce an explicit unavailable result. Existing four-analyst research continues within its original daily deadline and token budget.

The Mac option scan reuses its existing quote observations on both sides of the chain. It selects at most seven observations around ATM and roughly 5% OTM for the main candidate's underlying and expiry. This adds no broker requests. Research observations are separate from numerically eligible trade candidates. Missing paired quotes leave skew unavailable.

The existing broker scan supplies IV units but does not supply a verified risk-free rate or dividend yield. Consequently, automatic payoff and quoted-IV analysis can be available while model Greeks remain unavailable. Manual JSON can supply those model inputs explicitly; decimal `.03` means 3%. IV requires a separate `iv_unit` of `percent` or `decimal`. Missing values are never replaced with zero or inferred from magnitude.

## Reports and limits

`stock_signals.json` retains each stock's numeric evidence and upstream version. Existing analysts receive less than 700 bytes of bounded numeric context with no extra LLM calls. Additional prompt bytes still count toward the existing token budget. The short daily report adds a compact historical-volatility/RSI sentence when space permits. The daily 1,200-character cap, one-message delivery policy and preparation/send schedules remain unchanged.

`fincept_analytics.json` contains detailed stock and option diagnostics and is retained in research artifacts. The model assumes European exercise and a continuous dividend yield; it omits early exercise, discrete dividends, jumps and transaction costs. These estimates do not replace broker Greeks, current executable quotes, margin, assignment capacity or event review. Short Call loss remains potentially unlimited.

All existing option gates remain authoritative: 21–45 DTE, absolute Delta ≤0.10, liquidity and actual margin checks, entries after 10:00 HKT and the existing exit rules. No orders are sent. Historical trades in the uploaded 2025 workbook are not imported as current holdings, and no uploaded workbook or personal trade records are committed.

## Manual snapshots

Install `requirements.txt`, then run:

```bash
python scripts/run-fincept.py --input my_snapshot.json --output fincept_analytics.json
```

Use [examples/fincept_manual_snapshot.json](examples/fincept_manual_snapshot.json) as an **illustrative fixture**, not market data. Its quote is historical. For an explicitly labeled research replay:

```bash
python scripts/run-fincept.py --input examples/fincept_manual_snapshot.json --now 2026-10-14T10:30:00+08:00
```

The input has one `ticker`, optional `source`, optional `bars`, and optional `options` (at most 12). Every bar has ISO `date` and numeric `open`, `high`, `low`, `close`, `volume`. Bars must be increasing, complete and recent. Every option specifies `option_type` (`PUT` or `CALL`), ISO `expiry`, `spot`, `strike`, `bid`, `ask`, `lot_size`, `quote_time`, `iv`, `iv_unit`; a provided `underlying` must match the snapshot ticker. Naive option quote times follow the existing OpenD HKT convention. Dates/times with an explicit offset are preferred. Quotes must be from the analysis day and no older than 30 minutes. Expiry payoffs assume one hypothetical short contract, not an actual account position. `--now` marks the output as historical replay and does not alter the production entry gates.

## Source and maintenance

Unmodified source lives under `third_party/fincept`. The manifest pins commit `0aa46db2a06b8d8d9f91f07090aa214ac02db5c2` and every source file's Git blob hash; all are verified before execution. Calls use a local isolated subprocess, bounded JSON and a timeout. The vendor worker receives no API credentials. No upstream code is downloaded at runtime.

The upstream [LICENSE](third_party/fincept/LICENSE) and [commercial licensing notice](third_party/fincept/docs/COMMERCIAL_LICENSE.md) are preserved verbatim. They include AGPL and additional commercial-use terms; review both when deciding on distribution or business use. This integration does not relicense upstream code or provide a Fincept commercial licence. Desktop branding is not reused.

To update, inspect a new immutable upstream commit, replace the selected files without edits, update their Git blob hashes and the pinned commit together, then rerun the complete tests. There is no automatic update from upstream main.

Validation: `python -m unittest discover -s tests -v`. PDF tests require a CJK font as documented in the README. The `Fincept Analytics Check` workflow runs the full suite without paid APIs or market network calls. Offline numerical tests do not prove live Yahoo/Futu coverage, Telegram receipt or future report punctuality.
