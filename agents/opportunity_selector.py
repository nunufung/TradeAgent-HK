"""Risk-tiered HKEX option candidate selector; research only, never trade authorization.

Input is a verified, same-session manually entered or OpenD sourced chain JSON list.
No synthetic prices or guessed strikes. Legacy ScreeningAgent remains unchanged.
"""
from __future__ import annotations
from datetime import datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

HKT=ZoneInfo("Asia/Hong_Kong")
TIERS={"A":(21,45,0.10),"B":(14,30,0.25),"C":(7,14,0.25)}

def _num(row,key):
    v=float(row[key])
    if not math.isfinite(v): raise ValueError(key)
    return v

def evaluate(row, now=None):
    now=now or datetime.now(HKT)
    if now.tzinfo is None: raise ValueError("now must be timezone-aware")
    try:
        dte=int(row["dte"]); delta=abs(_num(row,"delta"))
        bid=_num(row,"bid");ask=_num(row,"ask")
        strike=_num(row,"strike");spot=_num(row,"spot")
        lot=int(row["lot_size"]);oi=int(row["oi"]);volume=int(row["volume"])
        dt=datetime.strptime(row["quote_time"],"%Y-%m-%d %H:%M:%S").replace(tzinfo=HKT)
        if not (-1 <= (now-dt).total_seconds()/60 <= 30): raise ValueError("stale quote")
        if min(bid,ask,strike,spot,lot)<=0 or ask<bid:raise ValueError("invalid prices")
        if oi<100 or volume<1:raise ValueError("thin market")
        spread=(ask-bid)/((ask+bid)/2)
        if spread>0.30:raise ValueError("spread too wide")
        if row.get("event_risk") is not False:raise ValueError("event risk not cleared")
        if row.get("assignment_reviewed") is not True:raise ValueError("assignment not reviewed")
        if row.get("account_risk_reviewed") is not True:raise ValueError("account risk not reviewed")
        side=str(row["option_type"]).upper()
        if side not in ("PUT","CALL"):raise ValueError("option side")
        if not row.get("expiry") or not row.get("underlying"):raise ValueError("missing contract")
        if row.get("strategy") not in ("CASH_SECURED_PUT","COVERED_CALL"):raise ValueError("single-leg structure not approved")
        if row["strategy"]=="CASH_SECURED_PUT" and (side!="PUT" or strike>=spot or row.get("cash_secured") is not True):
            raise ValueError("put not funded/out of money")
        if row["strategy"]=="COVERED_CALL" and (side!="CALL" or strike<=spot or row.get("covered") is not True):
            raise ValueError("call not covered/out of money")
        premium=bid*lot
        buying_power=_num(row,"buying_power_required")
        if buying_power<=0:raise ValueError("buying power")
        if row["strategy"]=="CASH_SECURED_PUT" and buying_power < strike*lot-premium:
            raise ValueError("cash coverage insufficient")
        if row.get("portfolio_risk_ok") is not True:raise ValueError("portfolio capacity unknown")
        tier=next((t for t,(lo,hi,dmax) in TIERS.items()
                   if lo<=dte<=hi and delta<=dmax and (t=="A" or row.get("defined_risk") is True)),None)
        # A is the only currently supported single-leg tier. B/C require validated multi-leg pricers.
        if tier!="A":raise ValueError("requires validated defined-risk multi-leg spread")
        if buying_power/premium>10:raise ValueError("legacy margin/premium limit")
        score=round(30+25*(1-spread/0.30)+20*float(row.get("thesis_strength",0))
                    +15*min(premium/buying_power*10,1)+10*float(row.get("diversification_score",0)),1)
        score=min(100,max(0,score))
        return {"status":"CONDITIONAL" if now.hour<10 else "REVIEW_REQUIRED",
                "tier":tier,"score":score,"underlying":row["underlying"],
                "strategy":row["strategy"],"option_type":side,"strike":strike,
                "expiry":row["expiry"],"dte":dte,"bid":bid,"ask":ask,
                "lot_size":lot,"premium_before_fees":premium,"quote_time":row["quote_time"],
                "reason":"Requires human/broker execution verification; no auto-trade"}
    except (ValueError,KeyError,TypeError,OverflowError) as e:
        return {"status":"REJECTED","reason":str(e)}

def generate(source="option_chain_manual.json",destination="opportunity_candidates.json",now=None):
    path=Path(source)
    if not path.is_file():
        result={"status":"NO_CHAIN_DATA","candidates":[],"rejected":0}
    else:
        raw=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw,list):raise ValueError("option chain must be list")
        checked=[evaluate(item,now=now) for item in raw]
        candidates=sorted((x for x in checked if x["status"]!="REJECTED"),
                          key=lambda x:x["score"],reverse=True)[:3]
        result={"status":"CONDITIONAL_RESEARCH" if candidates else "NO_ELIGIBLE_CANDIDATE",
                "candidates":candidates,"rejected":sum(x["status"]=="REJECTED" for x in checked)}
    Path(destination).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result

if __name__=="__main__":
    print(json.dumps(generate(),ensure_ascii=False))
