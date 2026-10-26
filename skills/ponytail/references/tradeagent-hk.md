# TradeAgent-HK efficiency boundaries

Use this Skill for development and bounded code review. Read the current DAILY_TOKEN_POLICY.md, daily_budget.py and actual callers before changing runtime token behavior; historical limits or schedules may have changed.

At installation, the inspected main revision was 24391d0920f63253497d8452dc3da5f723024832. The policy describes one paid DeepSeek morning session, bounded calls/tokens and provider-reported usage/cache accounting. Preserve its reservation and reconciliation logic, uncertain-call accounting, truncation rejection, independent four analysts, option eligibility gates, once-daily delivery, deadlines and confirmed receipts.

Prefer reuse of existing helpers, current artifacts and validated deterministic work over adding another LLM request. Load only task-relevant Skill references. Keep required provenance, quote times, missing data, contrary evidence and independent option checks; do not shorten a financial report by removing them.

Do not add the full Ponytail coding prompt to skills/runtime.json or each analyst call just to register this development Skill. That would add input tokens and has no demonstrated benefit for investment research. Registration adds no DeepSeek calls and does not change API budgets, credentials, model routing, schedules, recommendation rules or Telegram transport.

For an explicitly requested optimization experiment, compare equivalent scopes using provider-reported input/output/cache-hit counts, completed calls, failures, latency and output completeness. Include any added instruction tokens in the comparison. Label synthetic character/token estimates separately from actual billed usage. Preserve output quality and risk controls; do not promise a savings percentage from upstream benchmarks.
