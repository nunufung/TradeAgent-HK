# TradeAgent-HK v5 rebuild notes

This bundle is an **overlay rebuild** for the existing `nunufung/TradeAgent-HK` repository. Copy it over the current checkout so unrelated assets and the existing `tradingagents` gitlink/submodule are preserved.

## Replaced / repaired

- `main.py`: two-mode daily report engine (07:00 pre-market / 10:00 actionable).
- `hk_screener.py`: repaired invalid/incomplete Python and routed it through the canonical rule engine.
- `calc_delta.py`: fixes negative Put Delta ranking by ranking on `abs(delta)`.
- `data_agent.py`: removes synthetic option-chain generation from production paths.
- `hk_adapter.py`: makes TradingAgents commentary optional and non-authoritative.
- `.github/workflows/hk-daily.yml`: 07:00 and 10:00 HKT schedules, recursive submodule checkout, tests, artifacts, and latest-report publishing.
- `index.html` + `dashboard/index.html`: removes duplicated/broken EPUB UI and replaces it with the report dashboard.
- `requirements.txt`: adds missing runtime/test dependencies.

## Added

- `config/rules.yaml`: single source of truth for trading/risk thresholds.
- `config/watchlist.yaml`: configurable HK watchlist.
- `tradeagent/`: market data, verified option loader, rule engine, position manager, optional TradingAgents adapter, reporting.
- `tests/`: deterministic risk-rule tests.
- `data/options.csv.example`: verified-option input schema.

## Safety / data integrity behavior

- No synthetic fallback contract is emitted when market data fails.
- 10:00 option selection requires verified contract data.
- Missing Delta or liquidity rejects a contract.
- Missing broker margin produces WAIT rather than DO.
- Margin/Premium above 10x rejects a contract.
- Preferred new Short Option DTE is 21–45 days; <7 DTE rejects a new naked short.
- Take-profit and stop/repair rules are encoded in the position manager.

## Automated option data

Set GitHub secret `OPTIONS_CSV_URL` to a trusted CSV endpoint with the schema documented in README. Without a verified feed, the stock report still runs but the option section reports NO TRADE.

## Validation completed

- `pytest`: 8/8 passing.
- Python bytecode compilation: passing.
- YAML parse validation: passing.
- End-to-end deterministic fixture: selected a valid low-delta Short Put and produced the expected 10:00 report sections.
