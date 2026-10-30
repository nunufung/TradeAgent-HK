# Futu OpenD stock lookup connection

Status: proposed design; not implemented or connected.

## Goal and agreed constraints
Entering a Hong Kong stock code in the Hugging Face UI should request current Futu market data and return the existing four-analyst research. Use the user's macOS OpenD installation. Do not use a GitHub self-hosted runner. Keep the existing public snapshot dashboard available.

## Evidence
- The current lookup only reads dashboard.json and explicitly does not execute TradingAgents.
- The existing futu-opend-smoke.yml connects to 127.0.0.1:11111 on a self-hosted macOS runner. That path does not satisfy the user's constraints.
- Prior context records a screenshot of local OpenD and HK stock/options LV1 permissions, but provides no verified remote bridge. Current OpenD availability and entitlements remain untested.
- main.py already has quote retrieval and option screening; hk_adapter.py already invokes Market, Fundamental, News and Sentiment analysts using DeepSeek.

## Approaches
Selected data source: Futu OpenD.
Recommended transport: a Mac connector that makes outbound authenticated HTTPS requests to an owner-only lookup backend. It polls for validated stock requests, reads local OpenD, then returns allowlisted market data. No incoming Mac port or GitHub runner is required.
Alternative: an authenticated inbound HTTPS bridge to the Mac. No such bridge was found; provisioning and exposing an additional inbound service is unnecessary for this use case.
Directly exposing OpenD's TCP port is excluded.

## Proposed behavior
1. The owner signs into the live lookup; anonymous visitors retain the public snapshot view.
2. A validated code such as 700 becomes HK.00700 and creates one bounded job.
3. The Mac connector, while the Mac is awake and OpenD is logged in, picks up that job. It uses OpenQuoteContext only, retrieves a quote, market state and available historical candles, and returns sanitized fields with provider timestamps and retrieval time.
4. The backend runs the existing four analysts with the Futu quote/candles explicitly supplied as the price evidence. News and fundamentals retain their separate source dates. Missing evidence is reported rather than invented.
5. The UI displays connection/job status, price timestamp, analysis time, per-analyst results and the final summary. Closed-market, delayed, stale, disconnected and permission-denied states are distinct. A received quote is not automatically labelled real-time.

## Boundaries and setup
Authenticated jobs and results are private to the owner. The backend does not publish the Futu feed in the public snapshot. Device credentials and DeepSeek credentials stay outside browser code, repository contents and logs. Job expiry, duplicate suppression, bounded payloads, API quotas and one active analysis per owner limit load. No portfolio/account access or order execution is included.

A Mac connector must be installed and paired once. Secure backend hosting and credential provisioning must be verified before deployment; no paid resource is assumed. The current environment cannot operate the user's Mac, so the local installation and first OpenD connectivity test need a user-side step. No successful connection is claimed until a real HK.00700 request crosses the complete route.

## Acceptance checks
Validate stock formats; reject arbitrary commands/URLs and unauthenticated jobs; exercise offline and stale-quote states; verify no secrets/private account fields enter responses; test request timeout/retry; then observe one real lookup returning Futu timestamps and all four source-backed analyst results. Preserve public dashboard and Refresh regression checks.
