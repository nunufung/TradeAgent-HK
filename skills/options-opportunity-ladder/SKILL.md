# Options Opportunity Ladder Skill

## Purpose
Generate usable HKEX stock-option candidates daily or weekly without treating stock bullishness as an automatic option entry. This skill supplements, but does not silently override, the existing HKEX Options Trading Rules. Preserve current production hard gates until approved and tested.

## Output contract
Every report supplies (a) the highest-ranked actionable candidate **if and only if verified**, (b) up to three **conditional** candidates if verification is incomplete, and (c) a transparent **NO TRADE** when risk checks fail. Never manufacture option quotes, margin, Greeks, open interest, expiry, or possible fills. Morning reports before 10:00 HKT are PREMARKET IDEAS, not confirmed entries.

For each named contract: underlying / option side / strike / exact expiry / DTE / strategy / lot size / bid-ask and timestamp / IV / delta / OI / volume / margin or defined maximum loss / estimated net credit or debit after costs / entry trigger / thesis / invalidation / profit-taking / stop-and-review / position size / event dates / tier / confidence / verified-or-conditional status. If the chain lacks enough data for a contract, specify underlying + strategy + target expiry window and explicitly label STRIKE UNVERIFIED.

## Three candidate tiers (proposed policy; not live production authorization)
- A / Core income: 21–45 DTE, preferably cash-secured put, genuinely covered call or defined-risk credit spread; conservative delta chosen with assignment, trend and risk in mind. Existing strict screening remains a baseline.
- B / Balanced: 14–30 DTE, generally defined-risk bull put / bear call / debit vertical spreads. Permit higher absolute short-leg delta (indicative 0.10–0.25), subject to event, probability and max-loss checks. Do not infer probability directly from delta.
- C / Tactical: 7–14 DTE, small defined-risk spreads only, tighter monitoring, no naked short calls/puts. Never recommend trades solely to meet a daily quota.

These are research ranges, not promises of liquidity, returns or frequency. 0–6 DTE speculative entries are excluded from the routine program.

## Non-negotiable vetoes
Missing or stale chain prices; unsupported or mismatched lot/expiry/strike legs; crossed, one-sided or untradeably wide quotes; insufficient liquidity or exit capacity; material unbounded loss; naked short call; unfinanceable short put assignment; unknown buying-power impact; insufficient account buffer; earnings, results, major corporate/policy catalyst or extended holiday risk without a fully explicit bounded-risk event plan; high concentration or correlated exposure; no realistic exit mechanism. A single veto means NO UNCONDITIONAL ENTRY.

Margin/premium <=10x remains the legacy policy for naked short premium. It is an efficiency *screen*, not a measure of max loss, and should not be mechanically applied to debit or fully defined-risk spread structures. For spreads use actual max possible loss and broker buying-power requirement, including physical-delivery/assignment and early exercise mismatch risks. Broker/exchange contract specifications control.

## Candidate evaluation
1. Start with tracked HK blue chips AND current holdings, then select liquid chains. Check direction with technical/fundamental/sentiment/news analysts; discrepancies decrease confidence, not fabricated consensus.
2. Construct matching contract pairs when using spreads; compute executable pessimistic net debit/credit using available bid/ask, contract multiplier and expected trading costs.
3. Exclude vetoed structures. Score remaining candidates /100: risk and assignment capacity 30; liquidity and execution 25; catalyst and directional evidence 20; net reward-to-max-loss 15; capital efficiency/diversification 10. Minimum guideline: A 80, B 75, C 80. No qualified trade means no trade.
4. For credit spreads, disclose width, net credit, maximum loss = width*multiplier - net credit before fees, and break-even; for debit spreads, maximum loss = net debit and max gain = width*multiplier - net debit before fees. For cash-secured puts, loss can approach strike*multiplier less premium; no false assumption that stop orders cap loss.
5. Apply trade-level loss budget <=0.5% of account equity for A/B and <=0.25% for C as a *starting guideline*, plus portfolio exposure/correlation and broker margin constraints. If portfolio equity is unknown, do not calculate a contract count or claim suitability.
6. Preserve review rules: realize roughly 50–70% of short premium gains where executable; loss beyond 100% of original premium triggers immediate intervention but is **not a guaranteed loss cap**. Earlier intervention for broken thesis, event changes, widening spread, or expiration/assignment risk. For debit spreads establish a maximum predefined debit loss and exit condition. No averaging down or loss-deferring rolls.
7. For daily report output show one top-ranked idea and 2–3 alternatives: state VERIFIED / CONDITIONAL / REJECTED and the concrete reason, enabling user to consider something weekly while not promising a daily trade.
8. At 06:00–08:00 HKT generate a watchlist, refresh from the live option chain after 10:00 HKT and only then mark an entry verified. If no refresh path exists, remain CONDITIONAL.

## Integration requirement
Existing `agents/screening_agent.py` enforces strict all-or-nothing gates, including absolute delta <=0.10; therefore this Markdown skill **alone does not alter production recommendations**. Implement a separate opportunity-ladder adapter with comprehensive tests and wire it into the final report selection, preserving a hard veto for no-data / unbounded-risk conditions. Never label this integration complete until tested in the actual workflow.
