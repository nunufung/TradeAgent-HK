# Hugging Face: TradeAgent-HK Dashboard and Live Lookup

## Live stock lookup (Futu first, public fallback)

The existing snapshot views remain public and date-bound. The stock lookup now
requests fresh available data from a Python backend in the same Space:

1. The signed-in owner (`lewisf`) uses a paired Mac connector for Futu OpenD.
2. The connector polls outbound HTTPS, reads 127.0.0.1:11111 locally and returns
   only quote/history fields. No GitHub self-hosted runner is required.
3. Offline, slow, unauthorized or stale Futu quotes fall back to public Yahoo
   Finance data. Anonymous visitors use only public data. Provider, quote time,
   retrieval time and fallback reason are displayed. Quotes can be delayed or
   reflect a closed market; a successful fetch is not proof of real-time access.
4. Immediate technical commentary is calculated from retrieved daily candles.
   It is explicitly separate from the four-analyst DeepSeek research.
5. Owner-only research runs the pinned existing TradingAgents team and shows
   completion, missing reports or failure. It permits one concurrent job, six
   new jobs per process/day and ten-minute reuse of completed same-stock jobs.

### One-time Mac connection

Open the deployed Space, choose the owner login / standalone analysis page link,
and sign in as `lewisf`. Keep that standalone page open to avoid third-party
cookie restrictions inside the Hugging Face iframe.

On the Mac with OpenD signed in and Python 3.9 or newer installed:

```bash
git clone https://github.com/nunufung/TradeAgent-HK.git
cd TradeAgent-HK
bash scripts/install-futu-connector.sh
```

Choose **配對 Mac connector** on the signed-in dashboard. Enter the five-minute
code at the installer's hidden prompt. Never post it in chat or GitHub. Keep the
terminal and OpenD running and the Mac awake. If this repository is already
cloned on the Mac, update that clone first instead of creating a second clone.

Pairing survives routine restarts. After 30 days or publisher-credential rotation,
renew with:

```bash
bash scripts/install-futu-connector.sh --pair
```

The connector does not collect an OpenD login or password. It never opens a
trading context or queries holdings, account IDs, balances or order APIs.
Device tokens are purpose-bound signatures valid for 30 days. Re-pairing does not
revoke an older unexpired token. Rotating the publisher credential and republishing
rotates the dedicated derived signing key and invalidates all device tokens.

### Live backend deployment

The existing Dashboard Sync workflow publishes only allowlisted snapshot and
runtime source files. Its existing HF_TOKEN writes the intended Space. The
approved deployment provisions the existing DEEPSEEK_API_KEY as a server-side
Space secret; its value never enters HTML, JavaScript, snapshots or logs. OAuth
uses only openid/profile; only lewisf can pair a Mac or start paid research.
The Gradio Python SDK runs server.py (FastAPI/uvicorn) on port 7860 without
requesting a higher hardware tier or exposing a public model-call endpoint.

Run the live lookup Python tests, the two JavaScript test files and the existing
public snapshot privacy tests. A simulated connector test does not establish
that the user's Mac is paired. Claim Futu connection only after a genuine owner
lookup returns an OpenD timestamp.

The remainder describes the original daily snapshot export. Its static-source
and no-live-quotes statements apply to those snapshot files; the live lookup
uses the separate authenticated backend described above.

## Purpose

This dashboard exposes **public research, models and system health only**. It is
not a trading terminal, portfolio tracker or Futu OpenD gateway.

Architecture:

1. GitHub Actions runs the existing daily research, health checks, Fincept/Kronos.
2. At **08:25 HKT** the new \`Hugging Face Research Dashboard Sync\` workflow
   downloads the latest allowlisted **main-branch** model and health artifacts.
3. \`dashboard/build_data.py\` constructs a fresh snapshot with only permitted fields:
   public watchlist, model dates, five-session forecast paths, historical validation
   metrics, and date-bound delivery/AI call states.
4. The workflow validates the JavaScript, runs privacy tests, and saves a static
   preview ZIP in GitHub Actions artifacts.
5. If a GitHub Actions secret named \`HF_TOKEN\` has write access, the workflow
   creates or updates a **free static HTML Space** at
   \`lewisf/tradeagent-hk-dashboard\`.

Space deployment files are exclusively under \`dashboard/space/\`. The publisher
rejects any unexpected files before upload.

## One-time publishing credential (required)

The currently connected Hugging Face OAuth integration has **read-only repository
scopes**, so GitHub cannot publish with that credential.

1. Create a user access token at **https://huggingface.co/settings/tokens**
   with permission to create/update the intended Space. A properly scoped
   fine-grained token is preferred; do not grant unrelated write access.
2. Open **https://github.com/nunufung/TradeAgent-HK/settings/secrets/actions**
   and add a **repository secret** named \`HF_TOKEN\` containing that token.
   **Never paste it into ChatGPT, code, README files, issues or Actions logs.**
3. Go to **Actions → Hugging Face Research Dashboard Sync → Run workflow** on
   \`main\`. The workflow creates the free static Space if missing and uploads
   only the approved files. Check its publish step and the Space's actual
   browser page before claiming it is live.
4. Future syncs run automatically every day at **08:25 HKT**, subject to GitHub
   scheduler delays. Every run also stores a 14-day static preview artifact.
5. Revoke/rotate the token in Hugging Face account settings if compromised,
   then update the GitHub secret.

## Interpretation and safety

- Dates are explicit. The timestamp when the dashboard was **built** is not a
  claim that underlying research or market quotes are current.
- On the absence of a current-day health audit, operational state is
  **UNVERIFIED**, not PASS.
- The Fincept fallback is a **historical** dated public-repo snapshot; the model
  never receives invented current prices. Forecast models are research, not
  validated stock or option return signals.
- A verified Telegram receipt means API acceptance, not that a phone displayed
  a push or that the report was read.
- Futu OpenD is **not called by or exposed to the Space**. Historical smoke-test
  status is not proof of live real-time access.
- No Telegram tokens, DeepSeek tokens, account IDs, broker credentials, order
  access, margin/balance, positions, personal trade logs or full research prompts
  are deployed. This is deliberate even if the Space is publicly readable.
- Secrets are injected only into the GitHub deployment step and are not placed
  inside the HTML/JavaScript or generated JSON.

If the goal changes to a **private holdings dashboard**, build a separately
authenticated backend, private database and permission controls; do not add
private portfolio exports to this public static Space.

## Files

- \`dashboard/build_data.py\`: public data export, dated fallbacks and allowlist
- \`dashboard/space/index.html\`: static dashboard
- \`dashboard/space/assets/\`: UI interactions, chart and styles
- \`dashboard/publish_space.py\`: checked Hugging Face upload
- \`tests/test_public_dashboard.py\`: privacy/schema/status regression
- \`.github/workflows/hf-dashboard.yml\`: daily export and credential-gated publish
