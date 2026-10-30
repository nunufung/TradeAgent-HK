---
title: TradeAgent-HK Intelligence
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: static
app_file: index.html
pinned: false
short_description: Hong Kong trading research dashboard
---

# TradeAgent-HK Intelligence

Public, read-only research dashboard automatically exported from the official
[TradeAgent-HK GitHub repository](https://github.com/nunufung/TradeAgent-HK).

- **No live market quotes**. Dates and origins are displayed; outdated predictions are not recommendations.
- **No account or transaction data**. GitHub Actions exports only allowlisted fields for model research and system health.
- **No order execution / brokerage integration** on this Space. Futu OpenD stays on a trusted Mac.
- **No secrets** are deployed here. Hugging Face Static Spaces run HTML/CSS/JavaScript without a backend.

The accompanying GitHub Action regenerates data from dated public research and selected
production artifacts. Models such as Fincept ARIMA and Kronos are not verified to
outperform the baseline and are not option trading approval signals.
