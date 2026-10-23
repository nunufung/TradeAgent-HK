# Telegram stock PDF requests

Automatic five-minute polling is disabled under the daily-only Token policy. The `Telegram Stock PDF Request` workflow now runs only when explicitly dispatched in GitHub Actions. The existing Telegram bridge may explicitly dispatch `hk-daily.yml` with `ticker` and `request_source=telegram`; these inputs are accepted and routed directly to the PDF workflow without polling. A manual dispatch with a blank ticker can process a pending request; it is an extra API expense outside the automatic morning budget. See [DAILY_TOKEN_POLICY.md](DAILY_TOKEN_POLICY.md).

Send either of these messages to the same Telegram chat that receives the PDF reports:

- `700`
- `/stock 700`

Use `/help` for the supported format. The workflow runs the existing TradingAgents stock analysis for that Hong Kong ticker, generates the PDF, sends a short progress reply, and returns the PDF to the configured chat. It only sends reports; it does not place trades or query Futu account balances.

## Required GitHub Actions secrets

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `DEEPSEEK_API_KEY`

For a private bot chat, the sender must be the account represented by `TELEGRAM_CHAT_ID`. For a group chat, also set `TELEGRAM_ALLOWED_USER_IDS` to a comma-separated list of numeric Telegram user IDs allowed to trigger paid analysis. Group slash commands such as `/stock 700` work with Telegram's default privacy mode; bare stock numbers may require the bot's group privacy setting to allow ordinary messages.

This workflow uses Telegram long polling (`getUpdates`). If another webhook is already configured for this bot token, Telegram rejects polling with HTTP 409. The workflow will report that condition; it will not remove an existing webhook automatically.


Direct workflow dispatch also accepts `ticker=1810` (or `01810`). It validates the ticker before analysis and saves `stock_delivery_receipt.json` only after Telegram confirms the PDF. It never acknowledges unrelated Telegram updates on the direct path.
