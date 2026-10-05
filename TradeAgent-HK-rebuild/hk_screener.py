from __future__ import annotations
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from tradeagent.config import load_rules
from tradeagent.data.market import fetch_stock_snapshot
from tradeagent.data.options import load_verified_csv
from tradeagent.engine.rules import rank_options


def main():
    ap = argparse.ArgumentParser(description="Rule-first HK option screener")
    ap.add_argument("--ticker", default="0700.HK")
    ap.add_argument("--options-csv", default="data/options.csv")
    args = ap.parse_args()

    rules = load_rules()
    ticker = args.ticker.upper()
    stock = fetch_stock_snapshot(ticker, period=rules["stock_scoring"].get("history_period", "3mo"))
    contracts, errors = load_verified_csv(args.options_csv)
    contracts = [c for c in contracts if c.symbol == ticker]
    now = datetime.now(ZoneInfo(rules["market"]["timezone"]))
    ranked = rank_options(contracts, [stock], rules, now.date())
    print(f"{ticker}: stock score={stock.score:.2f}/10 trend={stock.trend} spot={stock.spot:.2f}")
    for e in errors:
        print(f"DATA: {e}")
    if not ranked:
        print("OPTION: NO TRADE")
        return
    d = ranked[0]
    c = d.contract
    print(f"{d.action}: Short {c.option_type} {c.strike:g} exp {c.expiry} score={d.score:.1f}")
    for r in d.reasons:
        print(f"  + {r}")
    for w in d.warnings:
        print(f"  ! {w}")


if __name__ == "__main__":
    main()
