# Detailed analysis guide

Use this guide only for an expanded stock/option request. These are project
applications of the cited concepts, not trading rules prescribed by Natenberg.

## Volatility (Ch4, Ch14, Ch18)
Record realized-volatility windows and sampling conventions. Compare option IV
against an explicitly reasoned forward range, including events over the option's
life. A short historical window and a long expiry answer different questions.
Mean reversion can be slow or fail over the holding period. Compare strikes at
similar moneyness/Delta and maturities on consistent units; skew can change with
spot and stress. Missing history means relative value is unknown, even with IV.

## Position risk (Ch6, Ch9, Ch17)
Position sensitivity equals signed quantity times contract multiplier times the
option sensitivity, using verified provider units. A short put has positive
position Delta; a short call has negative position Delta. For vanilla options,
short Gamma makes directional exposure deteriorate as spot moves adversely.
Theta and Vega depend on position and maturity; multi-leg calendars may have
mixed or changing signs. Do not generalize single-option signs to every spread.

For a small-move illustration only, use:
change in position value approximately signed quantity * multiplier *
(Delta*dS + 0.5*Gamma*dS^2 + Vega*dIV + Theta*dt).
Specify whether Vega is per one percentage point or unit volatility, and Theta
per calendar day or year. Include signed legs separately. This excludes cross
Greeks and is unreliable for jumps, major IV changes or expiry transitions.
A numerical result requires actual data; otherwise give qualitative stress cases.

## Strategy and obligations (Ch7-Ch13)
Explain both the expiration payoff and pre-expiry mark-to-market risk. A defined
risk vertical may cap the terminal payoff loss when both matched legs remain
intact, but execution, early assignment and funding can still cause difficulties.
An unmatched ratio spread may retain a naked tail. A calendar is exposed to the
relative movement of two expiries and is not a guaranteed volatility hedge.
Discuss these as comparisons; current TradeAgent-HK supports its gated short
Put/Call pipeline, so do not silently add new strategies or order capability.

For a short put, distinguish initial margin from cash required for assignment
(strike * multiplier * quantity, adjusted for proceeds/costs where appropriate).
For covered calls, verify sufficient shares and discuss capped upside. For naked
calls state unlimited theoretical loss. Broker margin can increase under stress.

## Expanded output
Give stock thesis and counterargument; timestamped contract terms and quotes;
volatility comparison; signed Greek exposures; adverse spot/IV/time scenarios;
assignment and funding; gate outcomes and missing inputs; exit/invalidation plan.
Use tables for contract comparisons. Identify hypothetical scenarios explicitly.
Never promise a return or imply that a book establishes current market edge.
