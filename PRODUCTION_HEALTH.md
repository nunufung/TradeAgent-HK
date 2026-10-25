# TradeAgent-HK Production Reliability Runbook

## Scope

This release **keeps GitHub Actions as the scheduled research runner, DeepSeek as the bounded
daily model provider, Telegram as the report transport, and the Mac-only Futu OpenD
workflow as an independent option-data path**. It does not move trading to a new host,
activate automated orders, or claim that Hugging Face is a 24/7 server.

## Production health audit (08:05 HKT)

The new **Production Health Audit** workflow runs daily at 08:05 HKT, or manually using
Actions -> Production Health Audit -> Run workflow. It makes **no model calls, trades,
Futu quote requests, or Telegram sends**.

It downloads GitHub Actions artifacts for the Hong Kong date and verifies:
- The official Telegram `hk-daily-delivery-receipt-YYYY-MM-DD` exists and contains a
  same-day `message_id` and Hong Kong-local `sent_at`. The receipt means Telegram's
  API accepted the send, not that a device showed or read a notification.
- The morning artifact's `daily_research_status.txt` says `complete`. A delivered
  waiting/fallback message is not mistaken for completed research.
- The DeepSeek budget artifact's `daily_token_usage.json` matches the current day.
  It reports actual calls/tokens/cache-hit/uncertain calls when available. The
  budget gateway records provider/model per new call; it does **not** infer which
  individual analyst made each call.
- The latest **Futu OpenD Connectivity Smoke Test** job and whether it passed
  within the past seven days. A past success is *not* evidence of today's live
  quote subscription or an always-on Mac runner.

Results appear in the workflow's summary and in 30-day retained
`production-health-<run_id>` artifacts (`production_health.json`,
`production_health.md`).

**PASS**: Telegram receipt and completed research verified, no warnings.
**WARNING**: delivery and research verified, but e.g. Futu is unverified/stale.
**FAILED**: missing/malformed Telegram receipt or incomplete research; Action turns red.
An unconfirmed send with an existing delivery claim is **never blindly retried**.

This health audit runs after 08:00 and detects outages; it is **not** a guarantee
that GitHub's scheduler or Telegram delivers every message before 08:00. For
stronger SLA, introduce a separately hosted watchdog with its own notification
channel and an always-on queue/worker.

## Manual Futu acceptance test

On the Mac with Futu OpenD signed in and GitHub self-hosted `macOS` runner online,
run **Actions -> Futu OpenD Connectivity Smoke Test -> Run workflow** (e.g. 700).
Confirm market snapshot, timestamp, and option expiry endpoint in that job.
Then manually run **Futu HK Option Screen**. The smoke test reads market data
and does not unlock accounts or submit trades.

Do not use the default GitHub Ubuntu runner as if it could access your Mac's
`127.0.0.1:11111`; do not expose OpenD on the public internet.

## Rollout and remaining milestones

1. Check 08:05 audit on the next HK date; verify health summary, receipts, ledger.
2. Manually validate Futu OpenD and self-hosted runner before assuming real data.
3. Introduce an independent always-on Telegram worker/watchdog only after
   delivery/health metrics justify that infrastructure.
4. Add an optional Hugging Face display dashboard backed by **sanitized, read-only**
   status data, never secrets, private position records, or a public trading API.
5. Keep rule-driven HKEX option gates, quote freshness, margin, assignment capacity
   and human trade authorization separate from model-generated stock opinions.

Daily morning research and its at-most-once Telegram delivery semantics are
unchanged by the health workflow. For missed sends, use the existing explicit
`recover_daily=true` manual catch-up only after checking the delivery claim
and receipt.
