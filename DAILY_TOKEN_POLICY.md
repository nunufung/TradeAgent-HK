# Daily DeepSeek research and delivery policy

Automatic morning research uses `daily_runner.py`; the daily workflow no longer runs paid research on pushes or sends PDFs plus a separate summary. Automatic Telegram ticker polling is disabled. Explicit stock requests through the existing Telegram bridge are supported as separately requested work. Explicitly manually dispatched stock research remains an additional, separate expense and does not share the morning budget.

## Trading-hours access and flexible testing

The automatic daily analysis starts at 10:00 HKT, after market opening, with its own budget and 10:50 HKT cutoff. This supersedes the former premarket preparation and pre-08:00 delivery schedule. Explicit manual stock requests, intraday market research, review, model evaluation and backtesting remain permitted through separately invoked workflows using the configured DeepSeek API credentials; the automatic gateway's window does not restrict those separate workflows. Retain usage logging, source/freshness checks, cost visibility and option risk gates; do not auto-execute trades. The daily report remains a single concise message, independently of discretionary intraday research.

The `Budget` class supports `max_calls=0` or `max_tokens=0` to disable that particular numeric cap for controlled testing, while retaining per-request bounds and accounting. The automatic morning defaults have been relaxed; they are not provider quotas or billing caps.

## Automatic daily budget

- Only `deepseek-chat`, through the official DeepSeek API; both graph model tiers use the local budget gateway. No daily reasoner, streaming or hidden SDK retries.
- One paid research session per Hong Kong calendar date. A durable Actions research claim is uploaded before API work. A same-day rerun skips paid research, including after a crash that lost its final ledger.
- One news-selection request over at most 24 bounded RSS candidates, selecting at most four stories. Up to two dynamically selected stocks; keep the four actual independent analyst agents and one investment/risk discussion round.
- Up to 48 forwarded API calls, 1,000,000 input-plus-output token accounting budget, 1,600 output tokens per call, two tool rounds per analyst, 120,000 input bytes per request.
- Before each call, reserve a conservative bound based on complete serialized request bytes plus output allowance and overhead. After success, reconcile with DeepSeek's reported prompt/completion usage. Failed or unconfirmed calls keep their full reserved allowance. Truncated outputs are rejected rather than labeled complete research.
- Save actual input, output and cache-hit tokens in `daily_token_usage.json`; never save keys or prompts in that ledger. Cache hits are measured, not assumed as savings. The budget controls this project's automatic session, not account-wide billing or manually invoked workflows.
- Research runs for at most 45 minutes, only from 10:00 through 10:50 HKT. Before 10:00 the runner does not fetch data or analyze options, the gateway forwards no model calls, and the workflow does not create a research claim. Failed research is identified explicitly rather than presented as an expert Hold.

## One compact delivery

Start analysis at 10:00 HKT (02:00 UTC), with research backups at 10:10 and 10:20. Attempt delivery when research completes; 10:47 and 10:53 runs provide delivery backups if no daily delivery claim exists. The message uses the professional decision-first format, at most 1,200 characters, with stock conclusions, option status and execution conditions. Raw evidence stays in Actions artifacts for audit and option research.

When a delayed research run has not yet saved its artifact, backup delivery defers until 10:52 HKT so it cannot consume the only send while research is still running. The 10:53 slot can deliver a transparent failure summary if research never finishes. Neither the workflow nor the sender permits an automatic report before 10:00.

Delivery uploads a day-specific claim before exactly one Telegram `sendMessage` call. It never retries an ambiguous network result, because Telegram has no idempotency key for this call. A claim without a confirmed receipt needs investigation; it is not proof of delivery. This deliberately prefers at-most-one report over possible duplicates. Missing/stale/oversized research is replaced with a transparent current-day waiting summary. No old research is relabeled current.

No send starts at or after 10:59:30 HKT (the workflow locator stops at 10:59), leaving time for the 20-second network timeout before the 11:00 target. There is no automatic late catch-up. A user-requested `recover_daily=true` dispatch can send a clearly labelled manual catch-up outside that window; it retains current-day validation, send claims and confirmed receipts. Actions concurrency serializes primary and backup delivery runs.

## Timing limitation and validation

GitHub scheduled workflows can be delayed or dropped; these buffers cannot guarantee an exact 10:00 start or delivery before 11:00. A Telegram transport timeout can also leave delivery unconfirmed. Do not claim an exact-time guarantee solely from these cron settings.

Unit/integration tests exercise reservation concurrency, persisted usage, uncertain/truncated responses, model/request rejection, current-day validation, timeout fallback, send-claim enforcement and the one-message transport. No live API bill reduction or live Telegram delivery is claimed by local tests. First scheduled production run must be checked through its usage ledger and delivery receipt.

A missed deadline or an earlier send claim without a receipt fails the workflow visibly. A green run alone is never proof of delivery: check `hk-daily-delivery-receipt-YYYY-MM-DD`.

