"""Run the four TradingAgents stock analysts and emit fail-closed Futu signals."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from free_tech_news import configure_free_news, attach_news_context, collect_news, write_news_audit

HKT = ZoneInfo("Asia/Hong_Kong")
ANALYSTS = ("market", "social", "news", "fundamentals")
RATINGS = {"Buy", "Overweight", "Hold", "Underweight", "Sell", "REVIEW"}


def _futu_code(raw: str) -> str:
    code = raw.strip().upper().replace(".HK", "").replace("HK.", "")
    if not code.isdigit() or not 1 <= int(code) <= 99999:
        raise ValueError(f"Invalid Hong Kong ticker: {raw}")
    return f"HK.{int(code):05d}"


def _yahoo_ticker(raw: str) -> str:
    code = _futu_code(raw).split(".", 1)[1].lstrip("0") or "0"
    return f"{code.zfill(4)}.HK"


def allowed_option_types(rating: str, reports_complete: bool = True) -> list[str]:
    """Map the final five-tier rating to the existing short-option strategy."""
    if not reports_complete or rating not in RATINGS:
        return []
    if rating in {"Buy", "Overweight"}:
        return ["PUT"]
    if rating in {"Underweight", "Sell"}:
        return ["CALL"]
    return []


def _report_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def analyze(tickers: list[str], *, signal_path: Path, report_path: Path, news_batch: dict | None = None) -> dict[str, Any]:
    """Run TradingAgents once per underlying and save structured signals + audit reports."""
    sys.path.insert(0, str(Path("tradingagents").resolve()))
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY/OPENAI_API_KEY is not configured")
    os.environ["OPENAI_API_KEY"] = api_key

    now = datetime.now(HKT)
    trade_date = now.strftime("%Y-%m-%d")
    signals: dict[str, dict[str, Any]] = {}
    report_sections = ["# TradingAgents 正股分析與 Futu 期權方向\n", f"分析日期：{trade_date} HKT\n"]
    news_batch = collect_news() if news_batch is None else news_batch

    for raw_ticker in tickers:
        underlying = _futu_code(raw_ticker)
        print(f"Four-analyst research starting: {underlying}", flush=True)
        ticker = _yahoo_ticker(raw_ticker)
        report_sections.extend([f"\n## {underlying}（{ticker}）\n"])
        config = deepcopy(DEFAULT_CONFIG)
        config["llm_provider"] = "openai"
        config["deep_think_llm"] = "deepseek-reasoner"
        config["quick_think_llm"] = "deepseek-chat"
        config["backend_url"] = os.getenv("TRADINGAGENTS_LLM_BACKEND_URL", "https://api.deepseek.com")
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["output_language"] = "Traditional Chinese"
        configure_free_news(config, batch=news_batch)
        graph = TradingAgentsGraph(selected_analysts=ANALYSTS, debug=False, config=config)
        attach_news_context(graph, news_batch)

        try:
            state, rating = graph.propagate(ticker, trade_date)
            write_news_audit(news_batch, ticker, state.get("news_report", ""))
            rating = str(rating).strip().capitalize()
            reports = {
                key: _report_text(state.get(state_key))
                for key, state_key in (
                    ("market", "market_report"),
                    ("social", "sentiment_report"),
                    ("news", "news_report"),
                    ("fundamentals", "fundamentals_report"),
                )
            }
            analyst_status = {
                name: {"complete": bool(reports[name]), "characters": len(reports[name])}
                for name in ANALYSTS
            }
            complete = all(item["complete"] for item in analyst_status.values())
            if rating not in RATINGS:
                rating = "REVIEW"
            signal = {
                "rating": rating,
                "allowed_option_types": allowed_option_types(rating, complete),
                "analysts": analyst_status,
                "analysis_complete": complete,
                "ticker": ticker,
                "reports": reports,
                "decision": _report_text(state.get("final_trade_decision")),
            }
            signals[underlying] = signal
            print(f"Four-analyst research ready: {underlying}; rating={rating}; complete={complete}", flush=True)
            report_sections.append(f"\n**TradingAgents 最終評級：{rating}**\n\n")
            for name in ANALYSTS:
                report_sections.append(f"### {name}\n\n{reports[name] or '分析報告缺失；方向閘門已封鎖。'}\n")
            report_sections.append(
                f"\n期權連動：{', '.join(signal['allowed_option_types']) or '不篩選（中性／需覆核）'}\n"
            )
        except Exception as exc:  # A failed stock run must never open the options gate.
            print(f"Four-analyst research unavailable: {underlying}; error={type(exc).__name__}; option direction blocked.", flush=True)
            signals[underlying] = {
                "rating": "REVIEW",
                "allowed_option_types": [],
                "analysts": {name: {"complete": False, "characters": 0} for name in ANALYSTS},
                "analysis_complete": False,
                "ticker": ticker,
                "error": f"{type(exc).__name__}: sensitive error details omitted",
            }
            report_sections.append(f"\n**TradingAgents 分析失敗：期權篩選封鎖**\n\n{type(exc).__name__}（詳細錯誤內容已隱藏）\n")

    payload = {"date": trade_date, "generated_at": datetime.now(HKT).isoformat(), "analyst_set": list(ANALYSTS), "signals": signals}
    signal_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text("\n".join(report_sections), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="TradingAgents 正股評級 → Futu 期權方向訊號")
    parser.add_argument("tickers", nargs="*", help="港股代號，例如 700 2800")
    parser.add_argument("--signals", default="stock_signals.json")
    parser.add_argument("--report", default="stock_analysis.md")
    parser.add_argument("--market-news", help="Validated market_candidates.json RSS batch for the same briefing")
    args = parser.parse_args()
    if not args.tickers:
        from main import DEFAULT_WATCHLIST
        tickers = DEFAULT_WATCHLIST
    else:
        tickers = args.tickers
    batch = None
    if args.market_news:
        batch = load_market_news(Path(args.market_news))
    payload = analyze(tickers, signal_path=Path(args.signals), report_path=Path(args.report), news_batch=batch)
    print(f"TradingAgents analyzed {len(payload['signals'])} stock(s); signals saved to {args.signals}.")
    return 0


def load_market_news(path: Path) -> dict:
    """Use only the dated, publisher-validated candidates, not raw rejected RSS."""
    batch = json.loads(path.read_text())
    return {"fetched_at": batch['fetched_at'], "sources": batch['sources'],
            "lookback_days": 2, "articles": batch['candidates']}


if __name__ == "__main__":
    raise SystemExit(main())
