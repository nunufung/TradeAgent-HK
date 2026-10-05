# TradeAgent-HK v5.0

Rule-first Hong Kong stock and options intelligence. The deterministic risk engine is authoritative; LLM/TradingAgents commentary is optional and cannot override hard controls.

## Daily schedule (Hong Kong time)

- **07:00 HKT** — pre-market report. Market/watchlist context only; no new option trade is authorized.
- **10:00 HKT** — actionable scan. Ranks stocks and selects at most one verified option candidate; otherwise prints **OPTION: NO TRADE**.

GitHub Actions uses UTC cron (`23:00 UTC` and `02:00 UTC`) to match those HKT times.

## Canonical option rules

- Do not open new HK option positions before 10:00 HKT.
- Preferred new Short Option window: **21–45 DTE**.
- Under 21 DTE: management/close/roll priority.
- Under 7 DTE: generally no new naked Short Option.
- Target low Delta; maximum absolute Delta **0.10** for this strategy.
- Reject excessive spread / inadequate liquidity.
- `Margin / Premium <= 10x` required for a DO decision.
- Take profit after capturing **50–70%** of original premium.
- If loss exceeds **100% of original premium**, close/reduce/roll; do not average down.
- Event/news risk can downgrade or reject a setup.

All thresholds live in `config/rules.yaml`.

## Data policy

The prior synthetic option-chain fallback was removed. `data/options.csv` must contain verified observations (broker export, HKEX-derived feed, or another trusted source). Copy `data/options.csv.example` to start. Missing critical option fields result in WAIT / NO TRADE, never fabricated values.

Expected columns:

`symbol,type,strike,expiry,bid,ask,delta,iv,volume,open_interest,margin,lot_size,source`

## Run

```bash
pip install -r requirements.txt
python main.py --mode premarket
python main.py --mode actionable --options-csv data/options.csv
pytest -q
```

## Architecture

`market data -> hard rules -> option ranking -> optional TradingAgents commentary -> report/dashboard`

TradingAgents is a git submodule. GitHub Actions checks out submodules recursively. Set repository variable `ENABLE_TRADINGAGENTS=1` and secret `DEEPSEEK_API_KEY` only if you want that optional commentary enabled.

### Optional automated option-data feed

For a fully automated 10:00 option scan, set GitHub secret `OPTIONS_CSV_URL` to a trusted CSV endpoint that returns the expected schema. The workflow downloads it at runtime. If the URL is absent/fails, or required fields are missing, the report still runs but returns **OPTION: NO TRADE** rather than substituting made-up data.

## WhatsApp daily alerts

The 07:00 and 10:00 HKT GitHub Actions runs can send a compact report through the Meta WhatsApp Cloud API.

For security, **do not commit the recipient phone number or access token**. Add these GitHub repository secrets instead:

- `WHATSAPP_ACCESS_TOKEN` — Meta WhatsApp Cloud API access token
- `WHATSAPP_PHONE_NUMBER_ID` — the sender Phone Number ID from your WhatsApp Business setup
- `WHATSAPP_RECIPIENT` — recipient number in international format (digits/country code)

Add these GitHub repository variables:

- `WHATSAPP_ENABLED=1`
- `WHATSAPP_GRAPH_VERSION` — the Graph API version enabled for your Meta app
- `WHATSAPP_MESSAGE_MODE=template` (recommended for scheduled/business-initiated alerts)
- `WHATSAPP_TEMPLATE_NAME` — your approved WhatsApp template name
- `WHATSAPP_TEMPLATE_LANGUAGE=en_US`

The recommended template body has two text parameters:

`TradeAgent-HK {{1}} report\n{{2}}`

Parameter 1 receives `premarket` or `actionable`; parameter 2 receives the compact market/trade summary.

For testing inside an active WhatsApp conversation window, `WHATSAPP_MESSAGE_MODE=text` is also supported. Scheduled daily delivery should normally use the template mode permitted for your WhatsApp Business account.

The workflow sends WhatsApp only after the report is successfully generated. It never sends a fabricated option: if the option risk/data gate fails, the message explicitly says `Option: NO TRADE`.
