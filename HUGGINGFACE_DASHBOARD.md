# Hugging Face: TradeAgent-HK Public Research Dashboard

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
