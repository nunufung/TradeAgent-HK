---
title: TradeAgent-HK Intelligence
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.31.0
python_version: "3.11"
app_file: server.py
hf_oauth: true
pinned: false
short_description: Hong Kong trading research dashboard
---

# TradeAgent-HK Intelligence

Public, read-only research dashboard automatically exported from the official
[TradeAgent-HK GitHub repository](https://github.com/nunufung/TradeAgent-HK).

- **Stock lookup retrieves fresh available quotes**. Signed-in owner requests prefer a paired local Futu connector. If Futu is unavailable, public Yahoo Finance data is used with source and quote timestamps. Quotes may be delayed or stale; no real-time entitlement is assumed.
- **No account or transaction data**. GitHub Actions exports only allowlisted fields for model research and system health.
- **No order execution / brokerage integration** on this Space. Futu OpenD stays on a trusted Mac.
- **Server-side credentials only**. Owner-only DeepSeek research is separate from the public technical calculations. Credentials are never sent to browser code or the snapshot export. Sign-in uses Hugging Face profile-only OAuth.
- **Mac pairing**. The connector polls outbound HTTPS, reads local OpenD at 127.0.0.1:11111 and returns allowlisted quote/history fields only. No GitHub runner or inbound Mac port is used. Keep the Mac awake, OpenD signed in and the connector running. Pairing survives routine restarts and expires after 30 days or publisher-key rotation. Re-pairing does not revoke older unexpired device tokens; publisher credential rotation invalidates all of them.
- **Owner-only private data**. Futu jobs, results, device pairing and paid four-agent research require owner authentication. Anonymous lookup uses only public market data and calculated technical commentary. Research is limited to one concurrent job and six new jobs per process/day, with ten-minute same-stock reuse.

This Python Space serves the existing static dashboard and a FastAPI backend on port 7860. It does not invoke a public Gradio prediction endpoint. The existing public snapshot remains separate from on-demand quotes and research. No higher hardware tier is requested.

Mac setup: clone the TradeAgent-HK repository, run `bash scripts/install-futu-connector.sh`, then enter the five-minute pairing code generated in the signed-in standalone dashboard. Do not put pairing/device credentials in chat or GitHub. To renew an expired pairing, run the installer with `--pair`.

The accompanying GitHub Action regenerates data from dated public research and selected
production artifacts. Models such as Fincept ARIMA and Kronos are not verified to
outperform the baseline and are not option trading approval signals.
