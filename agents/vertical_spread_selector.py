"""Pair verified option-chain legs into bounded-risk vertical spreads.

Research-only, conservative bid/ask estimates. No trade execution.
"""
from datetime import datetime
import math
from zoneinfo import ZoneInfo

HKT = ZoneInfo("Asia/Hong_Kong")
SPECS = {
    "BULL_PUT_CREDIT": ("PUT", "CREDIT", "HIGH_SHORT"),
    "BEAR_CALL_CREDIT": ("CALL", "CREDIT", "LOW_SHORT"),
    "BULL_CALL_DEBIT": ("CALL", "DEBIT", "LOW_LONG"),
    "BEAR_PUT_DEBIT": ("PUT", "DEBIT", "HIGH_LONG"),
}

def _positive(value):
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError("positive finite number required")
    return v

def pair(short, long, strategy, now=None):
    """Return an explicitly non-executable result, or REJECTED and a reason."""
    now = now or datetime.now(HKT)
    try:
        if strategy not in SPECS: raise ValueError("unknown vertical strategy")
        if now.tzinfo is None: raise ValueError("timezone required")
        kind, flow, layout = SPECS[strategy]
        for leg in (short, long):
            if str(leg["option_type"]).upper() != kind: raise ValueError("leg type mismatch")
            if not all(leg.get(key) for key in ("expiry", "underlying", "quote_time")):
                raise ValueError("contract identity missing")
            quoted = datetime.strptime(leg["quote_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=HKT)
            if not (-1 <= (now-quoted).total_seconds()/60 <= 30):
                raise ValueError("stale quote")
            if leg.get("event_risk") is not False or leg.get("account_risk_reviewed") is not True:
                raise ValueError("event/account risk not cleared")
            if leg.get("assignment_reviewed") is not True or leg.get("portfolio_risk_ok") is not True:
                raise ValueError("assignment/portfolio risk not cleared")
            if int(leg["oi"]) < 100 or int(leg["volume"]) < 1:
                raise ValueError("insufficient liquidity")
            bid, ask = _positive(leg["bid"]), _positive(leg["ask"])
            if bid > ask or (ask-bid)/((ask+bid)/2) > 0.30:
                raise ValueError("untradeable bid/ask")
        if any(short[k] != long[k] for k in ("underlying", "expiry", "lot_size", "dte")):
            raise ValueError("leg mismatch: underlying, expiry, multiplier or DTE")
        lots = int(short["lot_size"])
        dte = int(short["dte"])
        if lots <= 0: raise ValueError("invalid contract multiplier")
        sk, lk = _positive(short["strike"]), _positive(long["strike"])
        if sk == lk: raise ValueError("same-strike legs")
        if layout in ("HIGH_SHORT", "LOW_LONG") and sk <= lk:
            raise ValueError("invalid strike ordering")
        if layout in ("LOW_SHORT", "HIGH_LONG") and sk >= lk:
            raise ValueError("invalid strike ordering")
        width = abs(sk-lk)
        if flow == "CREDIT":
            unit = float(short["bid"])-float(long["ask"])
            if unit <= 0 or unit >= width: raise ValueError("nonpositive/impossible net credit")
            credit = round(unit*lots, 4)
            max_loss = round(width*lots-credit, 4)
            max_gain = credit
        else:
            unit = float(long["ask"])-float(short["bid"])
            # For debit verticals: long is purchased, short is sold.
            if unit <= 0 or unit >= width: raise ValueError("nonpositive/impossible net debit")
            max_loss = round(unit*lots, 4)
            max_gain = round(width*lots-max_loss, 4)
        fees = float(short.get("roundtrip_fees_total", -1))
        if not math.isfinite(fees) or fees < 0: raise ValueError("round-trip fees unknown")
        net_gain = max_gain-fees
        if net_gain <= 0: raise ValueError("net reward not positive")
        max_loss_with_fees = max_loss+fees
        buying_power = _positive(short["buying_power_required"])
        if buying_power < max_loss_with_fees:
            raise ValueError("broker buying power inadequate")
        if short.get("broker_spread_supported") is not True:
            raise ValueError("broker spread treatment unknown")
        equity = _positive(short["account_equity"])
        budget = equity*(0.0025 if 7 <= dte < 14 else 0.005)
        if max_loss_with_fees > budget:
            raise ValueError("position loss budget exceeded")
        if not (7 <= dte <= 30): raise ValueError("outside spread DTE window")
        tier = "C" if dte < 14 else "B"
        # Short-leg delta is not a probability of profit.
        delta = abs(float(short["delta"]))
        if not math.isfinite(delta) or delta > 0.25:
            raise ValueError("short leg delta exceeds tier threshold")
        score = round(30 + 25*(1-max(
            (float(short["ask"])-float(short["bid"]))/((float(short["ask"])+float(short["bid"]))/2),
            (float(long["ask"])-float(long["bid"]))/((float(long["ask"])+float(long["bid"]))/2)
        )/0.30) + 20*max(0,min(1,float(short.get("thesis_strength",0))))
        + 15*min(net_gain/max_loss_with_fees,1)
        + 10*max(0,min(1,float(short.get("diversification_score",0)))),1)
        if score < (80 if tier=="C" else 75):
            raise ValueError("quality score below tier threshold")
        return {"status":"CONDITIONAL" if now.hour < 10 else "REVIEW_REQUIRED",
                "tier":tier,"strategy":strategy,"underlying":short["underlying"],
                "expiry":short["expiry"],"dte":dte,"short_strike":sk,
                "long_strike":lk,"lot_size":lots,"short_bid":float(short["bid"]),
                "long_ask":float(long["ask"]),"gross_credit_or_debit":round(abs(unit*lots),4),
                "max_gain_after_fees":round(net_gain,4),
                "max_loss_including_fees":round(max_loss_with_fees,4),
                "buying_power_required":buying_power,"score":score,
                "reason":"Research only; broker/multi-leg execution and assignment must be checked"}
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return {"status":"REJECTED","reason":str(exc)}

def screen_verticals(rows, now=None):
    """Explicit named candidates avoid arbitrary cross-product pair explosion."""
    output=[]
    for entry in rows:
        if not isinstance(entry,dict):continue
        result=pair(entry.get("short",{}),entry.get("long",{}),entry.get("strategy",""),now)
        if result["status"]!="REJECTED":output.append(result)
    return sorted(output,key=lambda x:x["score"],reverse=True)[:3]
