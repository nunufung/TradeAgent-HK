# Options Opportunity Candidate Input (manual; research only)

The daily runner calls `agents.opportunity_selector.generate()`. It reads `option_chain_manual.json` from the working directory and writes `opportunity_candidates.json` for the GitHub Actions research artifact. An absent file writes `NO_CHAIN_DATA`. This does not modify the production Telegram report or place trades.

Format:

```json
{
  "single_legs": [],
  "vertical_spreads": [
    {
      "strategy": "BULL_PUT_CREDIT",
      "short": {"underlying": "TICKER", "option_type": "PUT", "strike": 90},
      "long": {"underlying": "TICKER", "option_type": "PUT", "strike": 85}
    }
  ]
}
```

The abbreviated example is intentionally **incomplete** and will be rejected. No sample numbers should be used as live option quotes. Valid leg records must each include: same underlying, expiry (YYYY-MM-DD), DTE, actual lot_size, bid, ask, quote_time (Hong Kong YYYY-MM-DD HH:MM:SS), oi, volume, option_type, strike, event_risk=false, account_risk_reviewed=true, assignment_reviewed=true, portfolio_risk_ok=true. The short leg also requires actual buying_power_required, broker_spread_supported=true, account_equity, roundtrip_fees_total, delta, and optionally thesis_strength / diversification_score from 0 to 1.

For market-based report integration, the manual file or an explicitly verified feed must be made available to the runner. GitHub Actions does **not** have access to the user's manually entered local data merely because a local file exists. Do not commit account balances or personalized option chains to a public repository. Instead supply it securely through an approved data-ingestion method.

Only A single-leg and B/C defined-risk vertical *research* candidates are supported; no production authorization. Even B/C max-loss estimates assume the proposed spread can be opened and closed as a spread; early assignment, pin risk, physical delivery, transaction fees, price gaps, and broker restrictions must be reviewed. `CONDITIONAL` and `REVIEW_REQUIRED` never mean executable.

Run tests: `python -m unittest tests.test_opportunity_selector tests.test_vertical_spread_selector` (or `python -m unittest discover -s tests`). A historical backtest requires point-in-time bid/ask chains, expiries, corporate actions, survivorship handling and realistic fill / assignment assumptions; stock forecasts alone are insufficient.
