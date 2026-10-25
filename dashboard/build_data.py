"""Produce a PUBLIC, whitelist-only static dashboard snapshot for Hugging Face.

Only public repo watchlist, public historical research and explicit GitHub Actions
artifacts are consumed. Never publish positions, accounts, prompts, secrets or
unfiltered reports. Missing live evidence is always displayed as unavailable.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HKT = ZoneInfo("Asia/Hong_Kong")


def safe_number(value, digits=3):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        return None
    return round(value, digits)


def safe_text(value, max_length=110):
    return str(value)[:max_length] if isinstance(value, str) else None


def load_local(path):
    try:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def load_import(folder, filename):
    """Read a single whitelisted file downloaded by official GitHub Actions."""
    root = ROOT / "dashboard" / "import" / folder
    if not root.is_dir():
        return None
    matches = [p for p in root.rglob(filename) if p.is_file() and p.stat().st_size < 3_000_000]
    if len(matches) != 1:
        return None
    try:
        result = json.loads(matches[0].read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else None
    except (OSError, ValueError):
        return None


def select_sources():
    """GitHub Actions downloads the main-branch artifacts by run ID first."""
    health = load_import("health", "production_health.json")
    fincept = load_import("fincept", "fincept_forecast.json")
    kronos = load_import("kronos", "kronos_forecast.json")
    # Historical fallback is labeled by its source-generated timestamp.
    if fincept is None:
        fincept = load_local("research/fincept-bluechips-2026-10-25/fincept_forecast.json")
    recommendation = load_import("recommendations", "recommendations.json")
    return health, fincept, kronos, recommendation


def audit_status(health, today):
    if not isinstance(health, dict) or health.get("date_hkt") != today:
        return {"state": "UNVERIFIED", "day": today, "research": "unknown",
                "telegram": "unverified", "futu": "unverified", "api_calls": None,
                "tokens": None, "cache_hits": None}
    api = health.get("deepseek") or {}
    return {"state": safe_text(health.get("overall"), 20),
            "day": today,
            "research": safe_text(health.get("research"), 30) or "unknown",
            "telegram": safe_text(health.get("telegram"), 30) or "unverified",
            "futu": safe_text(health.get("futu_opend"), 50) or "unverified",
            "api_calls": safe_number(api.get("measured_calls"), 0),
            "tokens": safe_number(api.get("actual_tokens"), 0),
            "cache_hits": safe_number(api.get("cache_hit_tokens"), 0)}


def public_recommendations(raw, today):
    """Whitelist only same-day research decisions; never export evidence, account or option quotes."""
    empty = {"state": "UNAVAILABLE", "analysis_date": today, "action": "等待",
             "stocks": [], "option": None, "reason": "未有同日完整研究紀錄，不能提供交易建議。"}
    if not isinstance(raw, dict) or raw.get("analysis_date") != today:
        return empty
    rows = []
    for item in raw.get("stocks", [])[:6]:
        if not isinstance(item, dict):
            continue
        code = item.get("underlying")
        if not isinstance(code, str) or not __import__("re").fullmatch(r"HK\.\d{5}", code):
            continue
        complete = item.get("complete") is True
        rating = item.get("rating") if item.get("rating") in ("Buy", "Overweight", "Hold", "Underweight", "Sell", "REVIEW") else "REVIEW"
        rows.append({"ticker": code[5:], "rating": rating if complete else "REVIEW",
                     "complete": complete, "strategy": safe_text(item.get("strategy"), 70) if complete else "不做",
                     "summary": safe_text(item.get("decision_summary"), 210) if complete else "四分析員研究未齊備。"})
    action = raw.get("action") if raw.get("action") in ("等待", "不做") else "等待"
    reasons = raw.get("reasons") if isinstance(raw.get("reasons"), list) else []
    # Option audit and contracts may carry quote/account-sensitive data. Publish no contract.
    return {"state": "RESEARCH_ONLY" if rows else "UNAVAILABLE",
            "analysis_date": today, "action": action, "stocks": rows,
            "option": None, "reason": safe_text(reasons[0], 180) if reasons else "未通過完整期權風控審核。",
            "risk_review_complete": False}


def snapshot(*, health=None, fincept=None, kronos=None, recommendations=None, watchlist=None, kronos_backtest=None, now=None):
    now = now or datetime.now(HKT)
    today = now.astimezone(HKT).date().isoformat()
    watchlist = watchlist if watchlist is not None else load_local("market_watchlist.json")
    kronos_backtest = kronos_backtest if kronos_backtest is not None else load_local(
        "research/kronos-bluechips-2026-10-25/metrics.json")
    if not isinstance(watchlist, dict) or not isinstance(watchlist.get("stocks"), list):
        raise ValueError("Missing verified watchlist")
    if not isinstance(kronos_backtest, dict):
        raise ValueError("Missing backtest metrics")
    fincept = fincept if isinstance(fincept, dict) else {}
    kronos = kronos if isinstance(kronos, dict) else {}
    f_by = {x.get("ticker"): x for x in fincept.get("forecasts", []) if isinstance(x, dict)}
    k_by = {x.get("ticker"): x for x in kronos.get("forecasts", []) if isinstance(x, dict)}
    kb_by = {x.get("ticker"): x for x in kronos_backtest.get("stocks", []) if isinstance(x, dict)}
    stocks = []
    for row in watchlist["stocks"]:
        if not isinstance(row, dict):
            continue
        code = row.get("code")
        if not isinstance(code, str) or len(code) != 4 or not code.isdigit():
            continue
        f, k, b = f_by.get(code, {}), k_by.get(code, {}), kb_by.get(code, {})
        fm = f if f.get("status") == "FORECAST_ONLY" else {}
        km = k if k.get("status") == "FORECAST_ONLY" else {}
        kmtr = b.get("metrics") or {}
        model = kmtr.get("predicted") or {}
        baseline = kmtr.get("zero") or {}
        n = model.get("direction_n", 0)
        stocks.append({
            "ticker": code,
            "name": safe_text(row.get("name"), 36),
            "group": row.get("group") if row.get("group") in ("bluechip", "technology") else "other",
            "fincept": {
                "status": "FORECAST_ONLY" if fm else "UNAVAILABLE",
                "last_close": safe_number(fm.get("last_close")),
                "forecast_return_pct": safe_number(fm.get("endpoint_return") * 100, 2)
                    if isinstance(fm.get("endpoint_return"), (int, float)) else None,
                "data_cutoff": safe_text(fm.get("data_cutoff") or fincept.get("data_cutoff"), 12) if fm else None,
                "sessions": [safe_text(v, 12) for v in fm.get("sessions", [])[:5]],
                "prices": [safe_number(v) for v in fm.get("forecast", [])[:5]],
            },
            "kronos": {
                "status": "FORECAST_ONLY" if km else "UNAVAILABLE",
                "last_close": safe_number(km.get("last_close")),
                "forecast_return_pct": safe_number(km.get("endpoint_return") * 100, 2)
                    if isinstance(km.get("endpoint_return"), (int, float)) else None,
                "data_cutoff": safe_text(km.get("data_cutoff"), 12) if km else None,
                "sessions": [safe_text(v, 12) for v in km.get("sessions", [])[:5]],
                "prices": [safe_number(c.get("close")) for c in km.get("candles", [])[:5] if isinstance(c, dict)],
            },
            "backtest": {
                "valid": int(kmtr.get("valid", 0)) if type(kmtr.get("valid")) is int else 0,
                "kronos_mae_pp": safe_number(model.get("mae") * 100, 2)
                    if isinstance(model.get("mae"), (int, float)) else None,
                "baseline_mae_pp": safe_number(baseline.get("mae") * 100, 2)
                    if isinstance(baseline.get("mae"), (int, float)) else None,
                "direction_pct": safe_number(100 * model.get("direction_correct", 0) / n, 1)
                    if type(n) is int and n > 0 and type(model.get("direction_correct")) is int else None,
            },
        })
    metric = fincept.get("metrics") if isinstance(fincept.get("metrics"), dict) else {}
    predicted, zero = metric.get("predicted") or {}, metric.get("zero") or {}
    pooled = kronos_backtest.get("pooled") or {}
    return {
        "schema_version": 1,
        "meta": {
            "generated_at": now.isoformat(),
            "timezone": "Asia/Hong_Kong",
            "watchlist_updated": safe_text(watchlist.get("updated_at"), 12),
            "data_policy": "PUBLIC research only. No holdings, options account, order, keys or Telegram recipient data.",
            "not_live": True,
        },
        "health": audit_status(health, today),
        "daily_recommendations": public_recommendations(recommendations, today),
        "model_status": {
            "daily_llm": {"provider": "DeepSeek", "model": "deepseek-chat",
                          "description": "GitHub Actions bounded TradingAgents analysis"},
            "fincept": {"label": "Fincept ARIMA(1,1,1)", "generated_at": safe_text(fincept.get("generated_at"), 42),
                        "data_cutoff": safe_text(fincept.get("data_cutoff"), 12),
                        "source": "GitHub artifact / dated archived research",
                        "valid_windows": safe_number(metric.get("valid"), 0),
                        "mae_pp": safe_number(predicted.get("mae") * 100, 2) if isinstance(predicted.get("mae"), (int, float)) else None,
                        "baseline_mae_pp": safe_number(zero.get("mae") * 100, 2) if isinstance(zero.get("mae"), (int, float)) else None},
            "kronos": {"label": "Kronos small forecast",
                       "generated_at": safe_text(kronos.get("generated_at"), 42),
                       "data_cutoff": safe_text(kronos.get("forecasts", [{}])[0].get("data_cutoff"), 12) if kronos.get("forecasts") else None,
                       "backtest": "Historical 2026-10-25 public backtest; not live trading P&L",
                       "valid_windows": safe_number(pooled.get("valid"), 0),
                       "mae_pp": safe_number((pooled.get("predicted") or {}).get("mae", 0) * 100, 2)
                         if isinstance((pooled.get("predicted") or {}).get("mae"), (float, int)) else None},
        },
        "stocks": stocks,
        "links": {
            "github": "https://github.com/nunufung/TradeAgent-HK",
            "actions": "https://github.com/nunufung/TradeAgent-HK/actions",
            "health_workflow": "https://github.com/nunufung/TradeAgent-HK/actions/workflows/production-health.yml",
            "fincept_report": "https://github.com/nunufung/TradeAgent-HK/blob/main/research/fincept-bluechips-2026-10-25/REPORT.md",
            "kronos_report": "https://github.com/nunufung/TradeAgent-HK/blob/main/research/kronos-bluechips-2026-10-25/REPORT.md",
        },
    }


def main():
    health, fincept, kronos = select_sources()
    data = snapshot(health=health, fincept=fincept, kronos=kronos)
    out = ROOT / "dashboard/space/data/dashboard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Prepared sanitized public dashboard: {len(data['stocks'])} symbols, health {data['health']['state']}")
    print(f"Fincept cut-off: {data['model_status']['fincept']['data_cutoff']}; Kronos model: {data['model_status']['kronos']['generated_at'] or 'unavailable'}")


if __name__ == "__main__":
    main()
