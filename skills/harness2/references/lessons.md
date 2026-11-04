# TradeAgent-HK review lessons

Keep entries short and add one only when evidence can guide a future review.

## 2026-11-04 | Daily schedule documentation

- **Cue** — A missed report, schedule change or conflicting report time.
- **Baseline** — At `f50f4fb81bf0868dcf9bece7c7db715bcea88b47`, the README still listed the pre-market schedule. The checked-in workflow and `DAILY_TOKEN_POLICY.md` showed analysis starting at 10:00 HKT, a 10:50 research cutoff and an 11:00 delivery target.
- **Probe** — Compared the README before and after the wording change against `.github/workflows/hk-daily.yml` and the timing behavior covered by `tests/test_daily_transport.py`. The baseline failed the schedule comparison. The README diff in this entry’s introducing commit passed the schedule comparison and all 20 offline tests in `test_daily_transport.py`.
- **Adopted** — Use the workflow and runtime boundaries as the source for published schedules. Corrected the README. When diagnosing live delivery, use the production audit and same-date receipt.
- **Confidence and reuse** — High for the checked-in timing configuration at the reviewed revision. Revalidate against the workflow after schedule edits. Live Telegram delivery requires independent evidence.
