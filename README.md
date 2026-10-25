# TradeAgent-HK

Hong Kong equity and options research using four independent TradingAgents analysts, dated public news and fail-closed option rules. Research output is not an instruction to place trades.

## Daily operation

- Prepare at 04:17 Hong Kong time using the DeepSeek API; the automatic run uses `deepseek-chat` for both model tiers.
- Research up to two dynamically selected stocks, retaining technical, sentiment, news and fundamental analysts, investment debate and risk review.
- Attempt one concise Telegram text report immediately after scheduled research finishes, with independent 06:47, 07:17 and 07:37 HKT backup runs. A durable claim and confirmed receipt prevent repeat sends.
- Each date permits one paid morning session: at most 48 calls, a 100,000-token accounting budget and 800 output tokens per call. Record DeepSeek-reported input/output/cache-hit usage in the Actions ledger.
- Stop automatic research by 06:30 and refuse automatic delivery after the 08:00 deadline. Missed sends fail visibly. GitHub schedules can be delayed or dropped, so this cannot guarantee arrival before 08:00.
- Explicit Telegram stock requests are supported through the existing bridge: `hk-daily.yml` accepts `ticker`, `request_source` and `scope`, and routes a supplied ticker to the stock PDF workflow. Automatic polling remains disabled.
- For a missed daily message, explicitly run `HK Daily Report` with `recover_daily=true` and no ticker. This sends today's saved report (or a transparent incomplete-research notice), labelled as a manual catch-up, with a confirmed receipt. It does not restart paid morning research.

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

## Validation

Run `python -m unittest discover -s tests`. Chinese PDF tests need an available CJK font (set `TAHK_CJK_FONT` when needed). Local tests do not prove live API savings or confirmed Telegram delivery; check the next production run's token ledger and delivery receipt.

