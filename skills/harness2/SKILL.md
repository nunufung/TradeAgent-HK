---
name: harness2
description: Use when reviewing TradeAgent-HK reports, investigating recurring WAIT or Telegram delivery issues, or evaluating changes to prompts, tools, report formatting or analyst orchestration.
---

# Harness2 for TradeAgent-HK

Use the Propose–Probe–Compose and reflection methods from [Google Research Harness2](https://github.com/google-research/harness2/tree/6868817518876de8fd170c6a8354daca273b6191). This repository skill guides development and report reviews. Run comparisons outside the live reporting pipeline.

## Review and improve

1. **Baseline.** Read [retained lessons](references/lessons.md) and apply any matching cue. Record the Hong Kong date, commit, model/config and one observable problem. For reports, inspect the same-date research status, summary, production-health audit and usage ledger. For missing Telegram delivery, inspect the send claim and the confirmed receipt separately. Treat a claim without a receipt as an ambiguous send and stop automatic retries. Mark unavailable evidence.
2. **Propose.** State one falsifiable improvement and its pass criteria before testing. Change one prompt, tool, formatter or orchestration behavior in an isolated checkout. For repeated WAIT, distinguish a genuine no-edge result from unavailable inputs or failed research. Test whether the next verification step can be clearer.
3. **Probe.** Replay baseline and candidate on identical frozen, sanitized inputs and the same model settings when applicable. Start with existing offline fixtures. For WAIT reviews, cover no edge, stale or missing quotes, and incomplete research. Include a failure case and a held-out case, or mark the result provisional. Stub DeepSeek and Telegram for offline tests. Compare decision and blocker clarity, evidence traceability, handling of missing data, the 1,200-character report limit and duplicate-send behavior. Compare calls, tokens and elapsed time when measured. Label mocked and live evidence separately.
4. **Compose.** Adopt only the smallest change with a demonstrated gain and passing regressions. Require a budgeted, held-out model comparison before adopting prompt or model changes. Stub-only or provisional results leave the baseline in place. Re-run the same checks on the final diff. Preserve four independent analysts, stock versus option conclusions, current option risk gates, post-open timing, budget and at-most-once delivery. Use the existing change review process for any production change. Keep experiments clear of live sends and trading actions.
5. **Reflect.** Append a dated, sanitized entry to the lessons file with the trigger, baseline and candidate revisions, test or artifact reference, observed result, adopted or rejected change, confidence and reuse condition. Include a rollback revision for production changes. Store only evidence summaries in this public repository. Keep credentials, holdings, chat identifiers and raw prompts in their approved locations. Revalidate a lesson when its source behavior changes.

Use [Production Health](../../PRODUCTION_HEALTH.md) for delivery evidence. For replay, run the relevant tests under `tests/` with `python -m unittest discover -s tests -p '<test_file>.py'`. Focus on `test_daily_transport.py`, `test_final_summary.py` and `test_tactical_options.py` for daily reporting. A mock replay establishes behavior on the tested inputs. Use the confirmed same-date receipt and usage ledger for live delivery and cost checks.
