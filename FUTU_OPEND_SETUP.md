# Futu OpenD option screen setup

The option screen uses Futu OpenD on the same Mac as a GitHub Actions self-hosted runner. A GitHub-hosted runner cannot reach `127.0.0.1` on your Mac. Do not expose OpenD's port to the public internet.

## One-time Mac setup

1. Keep Futu OpenD installed, signed in, and listening on `127.0.0.1:11111`. Confirm the quote test works from this Mac.
2. In GitHub, open **TradeAgent-HK → Settings → Actions → Runners → New self-hosted runner**, select **macOS**, and follow GitHub's displayed download/configure commands on this Mac. Keep the runner service active and give it the default `self-hosted` and `macOS` labels.
3. Keep the Mac awake and the OpenD session signed in when the scheduled screen is due. The scheduled run is weekdays at **10:10 HKT**.
4. In **Settings → Secrets and variables → Actions**, confirm `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` exist. Optionally add secret `FUTU_ACC_ID` if the first Hong Kong securities account is not the intended account. `FUTU_ACC_INDEX` is an optional repository variable (default `0`).
5. Run **Actions → Futu HK Option Screen → Run workflow** to test. A custom ticker list accepts comma-separated stock numbers such as `700,2800`.

The workflow runs `main.py`, which collects real OpenD option-chain and snapshot data, then passes those rows to `agents/screening_agent.py` through its `ScreeningAgent.screen(chains)` interface. It screens once for quote quality, queries account-specific short initial margin only for the highest-ranked quotes, then screens again with the complete rule set. The code only reads quotes and margin; it never unlocks trading or submits, changes, or cancels an order. If margin data, a fresh two-sided quote, or another required field is unavailable, that contract is excluded. No mock or fallback option prices are used.

## Screening gates

- Short Put / Short Call only; absolute Delta at or below 0.10.
- IV must be present; whether IV is high relative to its own history remains a human check.
- 21–45 calendar days to expiry.
- Both Bid and Ask must be valid; relative spread `(Ask - Bid) / midpoint` at or below 30%.
- Open interest at least 100 and daily volume at least 1 contract.
- Put strike below spot / Call strike above spot.
- Broker-reported incremental short initial margin divided by premium at the Bid must be at most 10x.
- Option quote must be no more than 30 minutes old; no new-entry suggestion before 10:00 HKT.

Trend/support or resistance, earnings and news risk, holiday exposure, cash buffer, and whether assignment is acceptable still require a human check. The daily result is a candidate screen, not an order instruction.
