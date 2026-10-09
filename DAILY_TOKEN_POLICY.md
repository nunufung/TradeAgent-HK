# Daily DeepSeek research and delivery policy

Automatic morning research uses `daily_runner.py`; the daily workflow no longer runs paid research on pushes or sends PDFs plus a separate summary. Automatic Telegram ticker polling and its extra research are disabled. Explicitly manually dispatched stock research remains an additional, separate expense and does not share the morning budget.

## Automatic daily budget

- Only `deepseek-chat`, through the official DeepSeek API; both graph model tiers use the local budget gateway. No daily reasoner, streaming or hidden SDK retries.
- One paid research session per Hong Kong calendar date. A durable Actions research claim is uploaded before API work. A same-day rerun skips paid research, including after a crash that lost its final ledger.
- One news-selection request over at most 24 bounded RSS candidates, selecting at most four stories. Up to two dynamically selected stocks; keep the four actual independent analyst agents and one investment/risk discussion round.
- Up to 48 forwarded API calls, 100,000 input-plus-output token accounting budget, 800 output tokens per call, two tool rounds per analyst, 60,000 input bytes per request.
- Before each call, reserve a conservative bound based on complete serialized request bytes plus output allowance and overhead. After success, reconcile with DeepSeek's reported prompt/completion usage. Failed or unconfirmed calls keep their full reserved allowance. Truncated outputs are rejected rather than labeled complete research.
- Save actual input, output and cache-hit tokens in `daily_token_usage.json`; never save keys or prompts in that ledger. Cache hits are measured, not assumed as savings. The budget controls this project's automatic session, not account-wide billing or manually invoked workflows.
- Research runs for at most 45 minutes and starts no new API calls after 08:00 HKT. Unknown inputs or failed research produce a current-day waiting summary without invented trade recommendations.

## One compact delivery

Prepare at 06:00 HKT. Attempt delivery at 08:15; the 08:35 schedule is a backup only if no daily send claim exists. The message uses the professional decision-first format, at most 1,200 characters, with stock conclusions, option status and execution conditions. Raw evidence stays in Actions artifacts for audit and Mac option research.

Delivery uploads a day-specific claim before exactly one Telegram `sendMessage` call. It never retries an ambiguous network result, because Telegram has no idempotency key for this call. A claim without a confirmed receipt needs investigation; it is not proof of delivery. This deliberately prefers at-most-one report over possible duplicates. Missing/stale/oversized research is replaced with a transparent current-day waiting summary. No old research is relabeled current.

No send starts at or after 08:59:30 HKT (workflow locator/claim checks stop at 08:59), leaving time for the 20-second network timeout. There is no 09:00 or later catch-up report. Actions concurrency serializes primary and backup delivery runs.

## Timing limitation and validation

GitHub scheduled workflows can be delayed or dropped; these buffers improve punctuality but cannot guarantee that every report arrives before 09:00. An always-on scheduler with external delivery monitoring is required for a contractual delivery guarantee. A Telegram transport timeout can also leave delivery unconfirmed. Do not claim the deadline is guaranteed solely from these cron settings.

Unit/integration tests exercise reservation concurrency, persisted usage, uncertain/truncated responses, model/request rejection, current-day validation, timeout fallback, send-claim enforcement and the one-message transport. No live API bill reduction or live Telegram delivery is claimed by local tests. First scheduled production run must be checked through its usage ledger and delivery receipt.
