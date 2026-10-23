# FinRL research integration

TradeAgent-HK integrates the requested [AI4Finance FinRL](https://github.com/AI4Finance-Foundation/FinRL) framework for historical **stock** policy training and evaluation. This is an optional research workflow, separate from the four TradingAgents analysts and the daily DeepSeek/Telegram pipeline.

## What is connected

- `external/finrl`: upstream Git submodule pinned to `c0018c25de864157dc8470f0047b0d10ec721715`.
- `integrations/finrl-lock.json`: upstream commit and reviewed environment SHA-256. Changed upstream code is rejected until reviewed.
- `finrl_research.py`: numeric HK symbol normalization; complete, validated stock OHLCV; lagged features; FinRL StockTradingEnv; Stable Baselines 3 A2C/PPO/DDPG/SAC/TD3; chronological 60% training, 20% validation, 20% test.
- Validation net return selects the model; only that selected model is evaluated on the held-out test period. Equal-weight buy-and-hold and cash use the same dates and initial capital. Transaction friction is deducted; the default **assumption** is 20 basis points per side, including a slippage allowance, not verified brokerage charges.
- JSON metrics, Markdown report, equity history and saved models. `finrl_research_input.json` can feed the existing daily strategy-backtest section without training or extra LLM calls.
- **FinRL Research** GitHub Actions workflow: automatic synthetic integration tests on relevant changes; public-history training only through manual **Run workflow**.

## Local setup

Use a separate virtual environment; the morning report does not install Torch or FinRL.

```bash
git submodule update --init external/finrl
python3.11 -m venv .venv-finrl
source .venv-finrl/bin/activate
# Linux CPU installation; on macOS use pip install -r requirements-finrl.txt directly.
python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-finrl.txt
python -m unittest discover -s tests -p test_finrl_research.py -v
```

Only the hash-checked upstream environment is imported by file location. FinRL's package initializer eagerly imports unrelated training/broker integrations; this adapter avoids that initializer without changing upstream code. The environment and actual SB3 algorithms run normally. A Gymnasium TimeLimit ends each episode on its last genuine transition, avoiding the pinned environment's extra terminal call repeating the prior reward.

## Run historical stock research

```bash
python finrl_research.py --tickers 0700,1810,9988 --start 2020-01-01 --timesteps 10000 --output finrl-output
```

Yahoo stock histories use adjusted daily OHLCV and an exclusive end date. All symbols must have complete aligned histories. For recently listed or suspended names, select a common valid date range or supply a vetted panel; the adapter refuses missing rows and does not fabricate prices.

An existing historical **stock** table is also supported:

```bash
python finrl_research.py --data historical_stock_prices.csv --data-source 'provider, adjustment method and retrieval date' --timesteps 10000 --output finrl-output
```

Required columns: `date,tic,open,high,low,close,volume`. Tickers may be `700`, `HK.00700` or `0700.HK`; quote/currency units must be HKD. Apply any corporate-action adjustments consistently across OHLC. The table is unrelated to Futu option CSV ingestion. Option-chain inputs remain manual as requested.

Defaults train A2C and PPO. Select a subset with `--algorithms a2c,ppo,sac,td3,ddpg`; each receives the requested training steps (on-policy rollouts may round up). `--cost-bps`, `--initial-cash` and `--seed` are explicit experiment settings. These are research settings, not the user's actual account balance or fee schedule.

On GitHub, open **Actions → FinRL Research → Run workflow** and enter symbols, start date and training steps. Download the `finrl-research-<run-id>` artifact afterwards. The workflow has read-only repository permission and no broker, DeepSeek or Telegram secrets.

## Existing daily-report handoff

For a local report run, point the existing optional-input setting at the exported bundle:

```bash
export TAHK_RESEARCH_INPUT_PATH="$PWD/finrl-output/finrl_research_input.json"
```

For the cloud report, merge the bundle's `finrl` field into the existing `TAHK_RESEARCH_INPUT_JSON` secret (`schema_version: 1`). Keep any existing `portfolio` and `journal` fields. Never commit account inputs. An explicit existing `backtest` input takes priority over FinRL.

The strategy-backtest section labels the result **FinRL正股歷史模擬**, reports historical test return and maximum drawdown, and says it is not an option backtest or entry signal. Invalid, overlapping or future-dated evidence is blocked. No result is auto-published to the report without this explicit handoff, and no daily training or extra API/token budget is introduced. The daily and on-demand report checkouts initialize only their existing submodules, excluding FinRL.

## Interpretation and limits

This first integration proves a working research path; it does not establish a profitable trading strategy. Synthetic smoke tests verify plumbing only. Historical stock data cannot produce valid option IV, Greeks, margin, exercise, liquidity or option P/L simulations.

Current simulations use long-only synthetic single-share units, a 100-unit maximum action per symbol per step, prior-session return/moving-average/volatility features and idealized fills at the next observed open. Equity is marked at session opens; both policies start with a pre-trade cash mark and end with unliquidated holdings. No final liquidation cost is assumed. Board lots, minimum fees, market impact and separately paid cash dividends are not modeled. Adjusted historical prices are unsuitable for treating quantities as actual executable holdings. The fixed supplied universe has selection/survivorship bias. Rolling retraining, historical constituents, richer features, paper trading and production fee/execution modeling remain future work.

Never infer win rate or profit factor from the equity curve; closed-trade attribution is not provided. Short test periods make Sharpe noisy. Repeatedly tuning settings after inspecting a test period consumes that hold-out; use a new hold-out for subsequent evaluation.

FinRL outputs always have `execution_eligible: false` and `allowed_option_types: []`. Existing project option gates, four-analyst evidence, quote verification and account checks still apply. Numerical project gates remain 21–45 DTE, absolute Delta ≤0.10, spread ≤30%, OI ≥100, volume ≥1, margin/premium ≤10x and quote age ≤30 minutes; assess new entries after 10:00 HKT. Take-profit handling at 50–70% premium captured, loss handling beyond 100% of original premium and DTE management are unchanged. There is no order execution in this integration.

## Upstream licensing and updates

FinRL's MIT license remains with the upstream submodule. This integration does not copy or relicense its source. Repository pinning and the source hash must be updated together only after source review and integration tests. Upstream also discusses FinRL-X/FinRL-Trading; this change integrates the classic repository requested by the user.
