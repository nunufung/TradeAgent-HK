---
name: TradeAgent-HK Options
description: HK stock & index options strategy - tailored for HK market hours, vol, and IV crush
---

# TradeAgent-HK Option Skill

Use this when user says: "use TradeAgent-HK option" or "期權"

## Core Logic

### 1. HK Market Reality
- Trading hours: 09:30-12:00, 13:00-16:00 HKT
- Main underlyings: 2800.HK, 0700.HK, 9988.HK, HSI, HSCEI
- Watch: IV crush before earnings, northbound flow, expiry pinning

### 2. Decision Flow
When user gives ticker + view:
1.  Identify: Stock view (bullish/bearish/neutral) + IV rank (high/low)
2.  Strategy:
    - Bullish + Low IV: Long Call / Bull Call Spread
    - Bearish + Low IV: Long Put / Bear Put Spread
    - High IV: Sell premium - Short Strangle, Iron Condor, Covered Call
    - Event soon: Avoid long premium (IV crush)
3.  Quantify: Max loss, max gain, breakeven, Greeks, expiry suggestion (weekly vs monthly)
4.  Habit: 2-min daily check - IV, Delta exposure, Theta decay

### 3. Output Format (Always)
**標的:** 
**睇法:** 
**IV:** 高/低 + 原因
**策略:** [e.g. Bull Call Spread 0700.HK]
**結構:** Strike + Expiry + Cost
**風控:** Max Loss HKD / Margin
**2-min 習慣:** 每日要睇咩
**何時離場:** 止賺/止蝕位

Language: Mix Cantonese + English, quantify risk first.
Never give financial advice as guarantee, always show max loss.

### 4. Link to Deal-Review
If this options trade is to hedge a Gov/DC deal cashflow, link back to `deal-review` skill ARR logic.

## Strategy 2: Covered Call (收租)
Trigger: use TradeAgent-HK option covered call

When user says: "我有 0700 正股, 想做 covered call"

Flow:
1. Input: holding qty (e.g. 100 shares = 1 option lot), cost basis
2. Suggest: OTM Call 5-8% above spot, 2-3 weeks expiry
3. Calc: Premium income / month, yield %, what-if assigned

Output Template:
**持有:** 0700.HK x 100 @ 410
**策略:** Sell Call 450 expiry 2026-10-24
**收租:** Premium HKD 2.1 x 100 = HKD 210 (0.5% / 2週)
**年化:** ~13% if repeat
**風控:** If assigned at 450 -> Profit = (450-410)*100 + 210 = HKD 4210, Max loss still stock downside
**2-min 習慣:** 每週五睇 Delta >0.4 就 roll 上/後

Rule: Never sell ATM call if you don't want to lose stock. Prefer 0.25 Delta.
