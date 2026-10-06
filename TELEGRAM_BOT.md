# Telegram stock PDF requests

The `Telegram Stock PDF Request` GitHub Actions workflow checks the configured Telegram chat every five minutes. GitHub may delay scheduled runs during periods of high Actions load, so replies are not guaranteed to be immediate.

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
