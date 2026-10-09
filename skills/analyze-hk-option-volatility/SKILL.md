---
name: analyze-hk-option-volatility
description: Apply reviewed Sheldon Natenberg option pricing, volatility and risk principles to TradingAgent-HK daily reports, individual Hong Kong stock research and option analysis. Separate the stock thesis from volatility value, Greek exposure and execution eligibility.
---

# HK stock and option volatility analysis

Source: Sheldon Natenberg, Option Volatility and Pricing, 1994 second edition,
user-supplied OCR EPUB. Apply the reviewed concepts below, not historical prices
or US contract conventions. See references/source-map.md for chapter provenance
and references/analysis-guide.md for detailed analysis when file access is available.
The core rules here are self-contained for the runtime; do not fetch the whole book.

## Evidence and precedence

Apply current TradingAgent-HK deterministic gates and user instructions first.
Keep the four analysts' actual independent findings. Do not change option direction,
relax a failed gate, authorize orders, or treat this book as current market evidence.
Separate verified facts, model assumptions and missing inputs. Cite book concepts
by chapter; cite market evidence with source and timestamp in Asia/Hong_Kong.
Do not invent IV history, Greeks, dividends, prices, margin or account capacity.
Verify current HKEX contract terms with official sources when needed; never transfer
1994 US multipliers, exercise calendars or settlement conventions to HK contracts.

## Required analysis

1. Establish the stock thesis using market, social, news and fundamentals reports.
   State the catalyst, opposing evidence and thesis invalidation. A bullish stock
   thesis does not alone make a short put attractive; a bearish thesis does not
   alone justify a short call. Respect the existing stock-to-option direction gate.
2. Evaluate volatility separately (Ch4, Ch14): distinguish historical realized,
   forecast and option-implied volatility. Compare like horizons and record the
   estimation window, annualization and units. Check trend, stability, events,
   strike skew and expiry term structure. High IV alone is not a sell signal;
   IV minus historical volatility is not a guaranteed edge or future forecast.
3. Explain exposures (Ch6, Ch17): normalize Delta to -1..1 only when provider
   units are known. Distinguish option Greeks from signed position Greeks and
   include quantity and contract multiplier. For a vanilla short option, highlight
   negative Gamma/Vega and usually positive Theta; do not describe Theta as income
   without adverse-price and volatility risk. Low absolute Delta is not a
   guaranteed probability of success or a limit on loss.
4. Assess liquidity, costs and obligations (Ch9, Ch12, Ch13): use executable bid/ask,
   not a midpoint as guaranteed proceeds. Check depth, spread, lot size, margin
   buffer and assignment funding; a covered call sacrifices upside, while a
   naked call can have unlimited loss. Short puts can require buying the shares.
   Check exercise style and ex-dividend/early-assignment exposure where applicable.
5. Stress price, volatility and time jointly (Ch17, Ch18): describe adverse gaps,
   volatility expansion, accelerating near-expiry Gamma and liquidity withdrawal.
   Use full repricing for large moves if a validated model and inputs exist;
   label local Greek estimates as approximations. Do not fabricate numerical
   scenario P/L. Explain model limits, including jumps, fat tails and changing skew.
6. Conclude with WAIT, research candidate, reduce or close as supported by evidence.
   Preserve project entry/exit gates. Missing relative-IV, events, support/resistance
   or account capacity prevents unconditional entry. A roll closes one trade and
   opens another; recheck gates and costs, and do not call it recovery of a loss.

## Report use and efficiency

For each underlying, add one concise volatility/risk sentence to the final analyst
trade decision. State either the measured volatility finding or the missing data;
do not list this entire checklist in the daily report. Keep stock rating, option
status, principal risk and next verification condition clear. Keep the daily
summary within its existing 1,200-character limit. Before the permitted entry
window, present a research watchlist and conditions, not an executable new trade.
Retain 06:00 HKT preparation and the existing one-message pre-09:00 delivery policy.
Reuse same-day evidence and load this bounded core once per graph; detailed
references are for on-demand work, with no extra paid model calls required.
