# Futu-first live lookup implementation plan

> **For agentic workers:** Use superpowers:executing-plans task by task.

**Goal:** Return Futu quotes and four-analyst research from stock lookup, using public data when Futu is unavailable.

**Architecture:** Serve the existing dashboard and a small API in a Python Hugging Face Space. A paired Mac worker polls outbound HTTPS for quote jobs; no runner or inbound Mac listener. Anonymous lookups use public data and technical calculations; the owner signs in for private Futu results and paid DeepSeek research.

**Tech Stack:** Python 3.11, FastAPI, Hugging Face OAuth, yfinance, futu-api, existing pinned TradingAgents/DeepSeek; vanilla JavaScript.

**Spec:** docs/superpowers/specs/2026-10-30-futu-live-lookup-design.md, amended by the user's approval to fall back to public market data.

## Global constraints
- No GitHub self-hosted runner or raw OpenD port exposure.
- No orders, account balances or holdings.
- Timestamps and actual provider on every lookup; never invent realtime status.
- Existing public snapshots stay available; authenticated Futu data is never cached publicly.
- No new paid hosting tier or public endpoint able to spend DeepSeek credits.

## Review focus
- Mac disconnected or slow: bounded wait and explicit public fallback.
- Yahoo unavailable or old data: error/stale label, no invented quotes.
- Anonymous/other-user access: cannot read Futu jobs or start paid research.
- Different ticker submitted before completion: no old result overwrites new lookup.
- Space restart: device pairing expires visibly; snapshots/public fallback keep working.

### Task 1: Provider resolution and API
Files: dashboard/space/live_data.py, server.py, requirements.txt, README.md; tests/test_live_lookup.py.
Interfaces: normalize_code(raw)->str, public_quote(code)->dict, resolve_quote(code, broker, private=False)->dict, create_app()->FastAPI.
- [ ] Write and run failing normalization, source-selection, stale-data, sanitization and private-route tests.
- [ ] Add public quote retrieval, safe technical metrics, owner OAuth, bounded device queue/pairing and research job routes.
- [ ] Run pytest tests/test_live_lookup.py and syntax checks; expected pass.

### Task 2: Research and Mac connector
Files: dashboard/space/research_runner.py; scripts/futu_lookup_connector.py; scripts/install-futu-connector.sh; tests/test_futu_connector.py.
Interfaces: collect_quote(code)->dict; research subprocess accepts a quote packet on stdin and returns bounded analyst reports as JSON.
- [ ] Write/run failing allowlist and OpenD-failure tests.
- [ ] Reuse pinned TradingAgents with a verified quote packet and bounded tool/debate calls; keep secrets server-side.
- [ ] Implement outbound polling and one-time owner pairing, local config mode 0600; provide Mac installer.
- [ ] Run provider/connector tests and shell syntax check; expected pass.

### Task 3: UI, publisher and deployment
Files: dashboard/space/index.html, assets/app.js; dashboard/publish_space.py; .github/workflows/hf-dashboard.yml; HUGGINGFACE_DASHBOARD.md.
Interfaces: POST /api/lookup {code}, POST /api/research {packet_id}, GET /api/research/{job_id}, owner pairing endpoint.
- [ ] Add lookup regression checks for source/status rendering and stale request suppression.
- [ ] Connect stock submit to API; show current quote, provider, timestamps, technical commentary and owner four-agent progress. Keep option identity checks and snapshot views separate.
- [ ] Expand publish allowlist only for runtime source files; securely provision the existing DeepSeek credential through the authorized deployment path; enable OAuth profile-only login.
- [ ] Run relevant Python/JS regression checks, privacy tests and publisher tests, then review changes.
- [ ] Publish approved change and verify a real public-data lookup in the live UI. Report Mac pairing as pending until a genuine Futu round trip succeeds.
