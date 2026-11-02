# Tactical Option Review Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; one whole-change review before publication.

**Goal:** Produce independent short-term option proposals after real four-analyst review and distinguish research failures from no trade decisions.

**Architecture:** Enrich existing graph context and parse its final risk-manager response. Keep the stock rating and strict scanner; render tactical proposals first in both reports. Share a 07:50 research deadline between runner and gateway.

**Tech Stack:** Python standard library, existing GitHub Actions.

**Spec:** docs/superpowers/specs/2026-11-02-tactical-option-review-design.md

## Global Constraints

- All four same-day reports must exist; no additional model calls or auto orders.
- Conditional proposals are not executable prices or personalized position sizes.
- Preserve one-message pre-08:00 HKT delivery and ledger/receipt controls.

## Review Focus

- Hold versus short-horizon bearish review must preserve the stock rating.
- Missing, stale or malformed review must not fabricate consensus.
- Public settlement/unknown protection leg must never establish maximum loss.
- Late starts must remain bounded and use all four analysts for one stock.
- Tactical information and principal risks must survive the 1,200-character summary.

### Task 1: Integrate tactical judgment and reports

- [x] Add failing tests for Hold plus bearish tactical review, dissent, malformed/stale/incomplete evidence, NO_EDGE and historical contract references.
- [x] Implement option_review.py; attach context in linked_stock_analysis.py; expose structured reviews in market_recommendations.py; prioritize them in final_summary.py.
- [x] Run tactical and existing recommendation/summary/option-screen tests.

### Task 2: Restore bounded morning research

- [x] Add failing late-start test and update cutoff tests to 07:50.
- [x] Share the cutoff, use a one-stock shortlist in the last 20 minutes, and disclose fallback reasons. Add two premarket research slots.
- [x] Update existing stale 800-token assertions to the already deployed 1,600-token limit; run morning regression tests.
- [x] Wire tactical tests into the same push regression; the published commit passed all 48 configured checks in GitHub Actions.

## Execution record

- Baseline final-summary tests: 10 passed. Existing morning tests already fail because they still assert an 800-token limit, while production uses 1,600.
- Scope choice: implement the user's already specified policy within the existing system without an additional approval round; no trade or extra Telegram message is authorized by this change.
- Final fresh review found two Important issues: fallback delivery could consume the only send before the extended research cutoff, and dated text alone could falsely mark research complete. Both have RED-to-GREEN regression coverage. Delivery now defers absent-report fallback to 07:52 with a 07:53 slot; the runner requires saved four-report evidence and a valid tactical review.
- The full report now shares the summary's public contract audit, and rendered stock summaries omit the internal JSON. Both regressions were reproduced before their fixes.
- Local validation: 98 relevant transport, tactical, summary, stock/option-screen, spread, overnight, public-data and workflow tests passed; 4 book-context tests passed. Python compilation and both workflow YAML checks passed. The book-context fixture was updated for the already deployed traced graph seam; it also confirms the new tactical instruction reaches the graph.
- The pinned upstream graph dynamically injects instrument_context; its PortfolioDecision renderer preserves investment_thesis verbatim. Review verified that path. Model compliance, investment merit, live account/quote verification, scheduler punctuality and new Telegram delivery remain outside this local validation; no live run is claimed.
- Broader downloaded-suite PDF checks require a Chinese font unavailable in this environment; no PDF code was changed.
- Post-publication full CI exposed a removed legacy decision heading; restored it and passed the three text-format compatibility tests locally. The existing broad CI environment also lacked pytest and dashboard dependencies, so it now installs pytest plus the project's existing dashboard requirements before discovery. Cloud PDF verification follows in that workflow, where Chinese fonts are installed.
