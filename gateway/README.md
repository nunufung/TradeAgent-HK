# TradeAgent-HK FCC gateway

Deployment target: a separate Docker Space, `lewisf/tradeagent-hk-fcc-gateway`.
The existing static dashboard is not converted or replaced.

## Current verification

The edge tests pass with a mock FCC backend. A real FCC install, Docker image,
live deployment and upstream inference have NOT passed verification here.
The reviewed latest release, v6.18.11 (immutable commit
65d9f29788392d6e9948bfdee6519a44b1ceaad3), requires exactly Python 3.14.10.
This environment has no Docker and its Python manager reports no download for
3.14.10. The deployment workflow therefore requires a successful container build
before publishing; it must fail rather than silently substitute an unreviewed
upstream release or relax its dependency requirements.

As checked on 2026-11-06, the connected HF account is not Pro and its OAuth
credential has no repo write scope. HF currently requires a paid plan for new
Docker Spaces on CPU Basic. The publisher checks identity and Pro eligibility
before writing, never enables billing and never upgrades hardware.

## Operation

1. On an eligible account with a compatible Python image available, merge the PR.
2. Use the existing GitHub Actions `HF_TOKEN` write secret and `DEEPSEEK_API_KEY`.
   The new workflow does not reveal or copy their plaintext into the repo.
3. Run **Build and deploy FCC gateway**, enabling its deploy checkbox. The image
   must build first. Default configuration uses existing DeepSeek credentials.
4. A distinct 64-character gateway credential is derived from HF_TOKEN, stored
   as a gateway Space secret and as matching dashboard Space secrets. Rotating
   HF_TOKEN and redeploying rotates it. Do not paste it into chat or browser code.
5. Verify `/health` and an authenticated request from a trusted backend. A ready
   health response proves only the FCC process is reachable, not provider access.
6. Restore the owner-authenticated dashboard backend to use this gateway.
   Static hosting cannot securely hold gateway credentials or run research.

## Multiple providers

Set optional Actions secrets NVIDIA_NIM_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY
and the Actions variable FCC_ALLOWED_MODELS, a comma-separated list of exact FCC
model IDs for your accounts, e.g. `deepseek/deepseek-chat,groq/<your-model-id>`.
The first ID is FCC's default. Requests can select any allowlisted model. Test
each account/model's tool support and quota; a gateway does not grant free Claude.
The TradeAgent PR's two-route selector chooses direct DeepSeek or its configured
FCC_MODEL; per-model picker expansion is separate work.

## Protection and limits

FCC listens on 127.0.0.1:8082; the edge listens on 7860. Only `/health`, authenticated
`GET /v1/models`, `POST /v1/messages` and `POST /v1/messages/count_tokens` exist at
the edge. Admin, code sessions, file access, messaging and shutdown endpoints are
not forwarded. Credentials use Bearer or Anthropic x-api-key. No CORS access or
browser credential storage is enabled. Raw FCC output and access logs are suppressed.

The edge permits 1 MiB requests, at most 4096 requested output tokens, two active
requests and 200 attempts per UTC day per process. Run one worker. Counters reset
on restarts; use provider account spending limits for durable budget enforcement.
There is no silent cross-provider fallback. No orders or Telegram messages are sent.

## Other Docker hosts

The same image can run on another container host with HTTPS termination and a
single replica. Supply FCC_API_KEY, provider keys and FCC_ALLOWED_MODELS as runtime
secrets. Bind only port 7860 through HTTPS; never expose internal port 8082.

## Provenance

Upstream FCC is AGPL-3.0-only. Its source and license remain available at the
pinned upstream URL in the Space README. No upstream code is copied into this
repository; the Docker build installs the reviewed revision from GitHub.
