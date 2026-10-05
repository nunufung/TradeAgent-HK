from __future__ import annotations
import argparse
from datetime import datetime
import os
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from tradeagent.config import load_rules, load_watchlist
from tradeagent.data.market import fetch_watchlist, fetch_market_context
from tradeagent.data.options import load_verified_csv
from tradeagent.engine.rules import rank_options, market_allows_new_trade
from tradeagent.reporting import render_report, save_report


def infer_mode(rules: dict) -> str:
    now = datetime.now(ZoneInfo(rules["market"]["timezone"]))
    return "premarket" if now.hour < 10 else "actionable"


def refresh_options_csv(default_path: str) -> tuple[str, list[str]]:
    """Optionally refresh a verified CSV from a configured URL.

    This is deliberately opt-in. The engine never substitutes synthetic option
    quotes when the remote feed is absent or fails.
    """
    url = os.getenv("OPTIONS_CSV_URL", "").strip()
    if not url:
        return default_path, []
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "TradeAgent-HK/5.0"})
        resp.raise_for_status()
        p = Path(default_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(resp.content)
        return str(p), ["Option CSV refreshed from configured OPTIONS_CSV_URL"]
    except Exception as exc:
        return default_path, [f"OPTIONS_CSV_URL refresh failed: {exc}"]


def main() -> int:
    ap = argparse.ArgumentParser(description="TradeAgent-HK daily report engine")
    ap.add_argument("--mode", choices=["premarket", "actionable", "auto"], default="auto")
    ap.add_argument("--options-csv", default="data/options.csv")
    ap.add_argument("--report-dir", default="reports")
    args = ap.parse_args()

    rules = load_rules()
    mode = infer_mode(rules) if args.mode == "auto" else args.mode
    watchlist = load_watchlist()
    period = rules["stock_scoring"].get("history_period", "3mo")

    market_context, market_errors = fetch_market_context()
    stocks, stock_errors = fetch_watchlist(watchlist, period=period)

    option_decisions = []
    option_errors = []
    data_notes = []
    if mode == "actionable":
        if not market_allows_new_trade(rules):
            option_errors.append("Actionable mode requested before 10:00 HKT; new option recommendations are blocked")
        else:
            option_path, data_notes = refresh_options_csv(args.options_csv)
            contracts, option_errors = load_verified_csv(option_path)
            if contracts:
                now = datetime.now(ZoneInfo(rules["market"]["timezone"]))
                option_decisions = rank_options(contracts, stocks, rules, now.date())

    report, payload = render_report(
        mode,
        stocks,
        option_decisions,
        market_errors + stock_errors + data_notes + option_errors,
        rules,
        market_context=market_context,
    )
    print(report)
    save_report(report, payload, args.report_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
