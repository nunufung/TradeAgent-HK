---
name: TradeAgent-HK Options
description: Rule-first HK stock option screening and position management
---

# TradeAgent-HK Option Skill v5

Canonical machine-readable rules live in `config/rules.yaml`; this file is explanatory only.

1. No new option trade before 10:00 HKT.
2. Prefer 21–45 DTE for new Short Options.
3. Below 21 DTE, prioritize close/reduce/roll; below 7 DTE, generally do not open a new naked Short Option.
4. For the user's low-delta Short Option strategy, require absolute Delta <= 0.10.
5. Reject wide/illiquid markets.
6. Require Margin/Premium <= 10x for an actionable DO recommendation.
7. Capture 50–70% of premium, then take profit.
8. If loss exceeds 100% of original premium, act; do not average down.
9. Incorporate earnings, major news, policy and holiday risk.
10. Select at most one main option. If data or edge is insufficient, output NO TRADE.
