# TradeAgent-HK

Hong Kong equity and options research using four independent TradingAgents analysts, dated public news and fail-closed option rules. Research output is not an instruction to place trades.

## Daily operation

- Prepare at 04:17 Hong Kong time using the DeepSeek API; the automatic run uses `deepseek-chat` for both model tiers.
- Research up to two dynamically selected stocks, retaining technical, sentiment, news and fundamental analysts, investment debate and risk review.
- Attempt one concise Telegram text report immediately after scheduled research finishes, with independent 06:47, 07:17, 07:37 and 07:47 HKT backup runs. A durable claim and confirmed receipt prevent repeat sends.
- Each date permits one scheduled paid morning session (not an intraday API quota): at most 300 calls, a 1,000,000-token accounting budget and 1,600 output tokens per call. Record DeepSeek-reported input/output/cache-hit usage in the Actions ledger.
- Stop automatic research by 07:15 and refuse automatic delivery after the 08:00 deadline. Missed sends fail visibly. GitHub schedules can be delayed or dropped, so this cannot guarantee arrival before 08:00.
- Explicit Telegram stock requests are supported through the existing bridge: `hk-daily.yml` accepts `ticker`, `request_source` and `scope`, and routes a supplied ticker to the stock PDF workflow. Automatic polling remains disabled.
- For a missed daily message, explicitly run `HK Daily Report` with `recover_daily=true` and no ticker. This sends today's saved report (or a transparent incomplete-research notice), labelled as a manual catch-up, with a confirmed receipt. It does not restart paid morning research.

Trading-hour testing, manual research and review may use DeepSeek API calls independently of the morning-only cutoff and budget; maintain token accounting, cost monitoring and option-entry safeguards. The morning limits are relaxed, and controlled test code can disable numeric call/token caps via `Budget(max_calls=0, max_tokens=0)`. This does not alter provider billing or authorize trading.

Read [DAILY_TOKEN_POLICY.md](DAILY_TOKEN_POLICY.md) for reservation accounting, deadline checks, deduplication and failure behavior. Read [REPORT_FORMAT.md](REPORT_FORMAT.md) for the decision-first reporting format. Detailed research remains in Actions artifacts; same-day cloud research remains available to the Mac Futu option workflow.

## Options research discipline

Stock ratings and option entries are assessed separately. Missing quotes, incomplete analysis or unknown account risk prevent an unconditional entry recommendation. Current numerical screening uses 21–45 DTE, |Delta| ≤0.10, spread ≤30%, OI ≥100, volume ≥1, margin/premium ≤10x and quotes no older than 30 minutes. Numerical eligibility does not replace event, technical or account review. New entries are assessed after 10:00 HKT.

Take-profit handling starts at 50–70% of original premium captured. Losses greater than 100% of original premium require closing, reducing or a qualifying roll. Short puts require support and assignment capacity; short calls require resistance and verified coverage/risk capacity. No workflow here authorizes automatic trading.

## Reviewed book context

The reviewed Psychology of Money risk skill is loaded into four-analyst research. Project option rules take precedence. Conversion, provenance and runtime audit details are in [BOOK_TO_SKILL.md](BOOK_TO_SKILL.md).

## FinRL strategy research

The optional [FinRL integration](FINRL_INTEGRATION.md) adds HK stock reinforcement-learning training and held-out backtesting, with A2C/PPO and optional DDPG/SAC/TD3, cost assumptions and benchmark comparisons. Run it through **Actions → FinRL Research → Run workflow** or the local CLI. Saved results can feed the daily strategy-backtest section through the existing explicit research-input setting. Training runs separately; outputs are historical stock simulations and cannot authorize option entries.

## Kronos forecasts

The [Kronos Skill](skills/kronos/SKILL.md) guides candlestick forecasting and separate option risk checks. The independent **Kronos Forecast** workflow downloads reviewed Kronos-small/base-tokenizer weights and forecasts five HKEX sessions for Tencent (0700) and Alibaba (9988), using 400 adjusted completed daily bars from Yahoo Finance. It runs at 03:17 HKT, on relevant code pushes, or manually; each run records weight revisions, inputs, sampling parameters and generated candles in an artifact.

The morning report downloads the latest successful artifact and includes a concise model scenario in its existing single Telegram message. Missing, invalid or older-than-26-hour forecasts produce an explicit unavailable notice. Inference runs separately with a 20-minute job limit, uses no DeepSeek calls and cannot delay the existing morning research job. These are uncalibrated five-path mean research scenarios, not backtested strategy returns, analyst consensus or option-entry approval. Review Actions artifacts and actual delivery receipts to verify live operation.

## Fincept Terminal research

The [Fincept Skill](skills/fincept-terminal/SKILL.md) now has a bounded headless adapter: `fincept_research.py` downloads and verifies the reviewed upstream time-series module, and actually calls its `forecast_arima` function. It uses fixed ARIMA(1,1,1) on 400 log adjusted daily closes to forecast five HKEX sessions for every member of the GitHub watchlist's `bluechip` group (including 2800 ETF). This is a statistical module integration, not a running desktop terminal or an autonomous Fincept agent team.

**Fincept Research** runs independently at 03:07 HKT with pinned dependencies and no LLM calls. Manual/code-push runs also perform 24 chronological five-session validation windows per stock. The existing daily research job reads the latest successful artifact and includes a short, dated Fincept line in its single Telegram report. Missing, invalid, unknown-source or older-than-26-hour artifacts produce an unavailable notice; inference never runs inside the paid research/delivery process. Convergence failures and missing exchange dates are disclosed, never filled with synthetic successful forecasts.

[Initial real-data validation](research/fincept-bluechips-2026-10-25/REPORT.md) includes per-stock forecasts, input hashes, failures, baseline comparisons and limitations. Yahoo Finance remains the underlying provider and is not independently certified. Forecast metrics are not trading or option-profit validation; project option gates and delivery receipts remain independent.

## Ponytail development efficiency

The [Ponytail Skill](skills/ponytail/SKILL.md), adapted from [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail), guides the smallest complete code change, reuse of existing helpers, targeted reads and concise explanations while preserving necessary tests and validation. It is discoverable through `.agents/skills/ponytail`. This is a development Skill, not a runtime token compressor: registration does not change DeepSeek prompts, budgets, the four analysts, option gates or Telegram delivery. Actual provider usage remains measured through the existing token ledger; no savings percentage is claimed from installation alone.

## Validation

Run `python -m unittest discover -s tests`. Chinese PDF tests need an available CJK font (set `TAHK_CJK_FONT` when needed). Local tests do not prove live API savings or confirmed Telegram delivery; check the next production run's token ledger and delivery receipt.

