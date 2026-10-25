# TradeAgent-HK — SPIDER Command Center V3: license and deployment plan

Status: **design / deployment plan only**, not a deployed SPIDER implementation.
Date: 2026-10-25 HKT.

## 1. Reference and legal boundary

Reference: https://github.com/cyberdaddyleo/agent-display
Reference version examined: README v6.0 (2026-10-24).
Original copyright/license: https://github.com/cyberdaddyleo/agent-display/blob/main/LICENSE — PolyForm Noncommercial License 1.0.0, Required Notice: Copyright (c) 2026 赛博老爸.

- SPIDER is **a visualization and simulator**. Its simulated task state and token ledger are not an API for real TradingAgents.
- This implementation will be a **clean-room-inspired, independently authored** visual design, based on high-level functional ideas (agent desks, task handoffs, checks, output flow). Do not copy source code, CSS, graphic assets, character artwork, text, logos, exact scene composition, or watermark; do not vendor or use a submodule of the original repository.
- Any proposed reuse of protected source or modified derivatives must undergo separate license review; noncommercial usage must comply with original license/notice requirements. Commercial uses of original code require additional authorization from rightsholder.
- A publicly viewable Space or possible showcase does not itself establish whether the use qualifies as noncommercial; clarify actual usage before any source-reuse route.

## 2. Existing verified deployment

- GitHub repository: https://github.com/nunufung/TradeAgent-HK
- Current public Space: https://huggingface.co/spaces/lewisf/tradeagent-hk-dashboard
- Existing workflow: .github/workflows/hf-dashboard.yml, scheduled 00:25 UTC / 08:25 HKT, manual and selected push events.
- Existing builder: dashboard/build_data.py; public allowlisted output: dashboard/space/data/dashboard.json.
- Publisher: dashboard/publish_space.py accepts exactly README.md, index.html, assets/app.js, assets/style.css, data/dashboard.json. The workflow uses HF_TOKEN secret; no token in published files.
- Current sections (to preserve): Command, Overview, Daily Ideas, Models, Watchlist.
- Mac Futu OpenD stays on trusted runner. Browser is read-only: no order placement, credentials, holdings, account data or brokerage sessions.

## 3. Implementation architecture — no synthetic operational claims

Pipeline:
GitHub jobs/TradingAgents/Kronos/Fincept/recommendations and Mac-derived *safe status only*
  -> explicit validated public event adapter (schema v1) in GitHub Actions
  -> approved sanitized static dashboard.json containing **observed** event timestamps and statuses
  -> static Hugging Face Space rendering SPIDER-inspired command center.

Proposed public events (each contains id, job_type, run_id, agent_role, state, event_time_hkt, evidence_url, source_age_seconds):
- queued / started / completed / failed / unavailable as documented by GitHub jobs or explicit structured artifacts.
- No role-specific start/finish event -> UNKNOWN, not inferred ACTIVE.
- Daily metrics (token counts, counts, costs) only when explicitly sourced and measured; never use the original simulator's fake rates or values.
- Stock and option decisions remain separate. Date-gated recommendations only; no option contract/entry order without validated Futu data and complete HKEX gates.
- Missing source, previous-day event, or invalid structure: label UNVERIFIED / STALE, do not animate as proof of work.
- Animation depicts topology only; actual state colors and event sequences must correspond to observed events.

## 4. SPIDER-inspired visual layout (independent code)

- Top ribbon: local HKT time, latest snapshot timestamp, report status and provenance.
- Center: chief orchestrator + the four confirmed analyst roles Market / Fundamentals / News / Sentiment; auxiliary cards for Rule Engine, Kronos, Fincept, delivery.
- Sidebars: real workflow event timeline, error/health cards, last verified model run, GitHub link per run.
- Bottom: public daily stock ideas, option decision (WAIT/NO TRADE only until evidence passes), research completeness, measured token usage if available.
- CSS/SVG task paths and reduced motion support; optional 16:9 full screen. Do not copy original actor graphics or 14-role roster unless each actual role maps to a real system.
- Preserve accessible traditional-Chinese descriptions and responsive non-3D fallback.

## 5. Release sequence and gates

Phase A (current): license review and written architecture. **No original repository code imported; no production frontend replaced.**

Phase B (next PR): introduce explicit public event schema/adapter and tests. Verify main-branch origin, timestamps, no account/secret leakage, no invented per-agent usage. Use the actual GitHub jobs APIs or author-emitted structured event artifacts.

Phase C (next PR): build independently authored SPIDER-inspired interface behind a switch, keeping existing 5 views intact. Validate mobile/fullscreen/reduced-motion, graceful missing data, cross-browser and JavaScript syntax.

Phase D (after test): Stage preview via GitHub Actions artifact on PR. Production publishing remains main-only and whitelist-only. If files change, update dashboard/publish_space.py allowlist deliberately and add tests. Do not enable third-party remote scripts or broker connections by default.

Phase E (post-merge): monitor GitHub Actions success, verify HF Space reflects current revision, source timestamp and privacy; retain rollback to previous working commit or UI flag. Keep 08:25 HKT snapshot schedule. Intraday events would require a separate intentionally authorized backend/polling pipeline, not currently provided by static hosting.

Acceptance:
- Same-day option/stock decisions originate in sanctioned pipeline only.
- All displayed agent states have dated source; unknown means unknown.
- Zero leaks of accounts, holdings, quote secrets, private report text, recipient IDs.
- Dashboard works without any animated/WebGL capability.
- No third-party protected source copied.
- Successful testing/deployment independently verified.
