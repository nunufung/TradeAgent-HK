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
