"""Produce a PUBLIC, whitelist-only static dashboard snapshot for Hugging Face.

Only public repo watchlist, public historical research and explicit GitHub Actions
artifacts are consumed. Never publish positions, accounts, prompts, secrets or
unfiltered reports. Missing live evidence is always displayed as unavailable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HKT = ZoneInfo("Asia/Hong_Kong")
API_ROOT = "https://api.github.com/repos/nunufung/TradeAgent-HK"
MAX_ZIP = 12_000_000


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


def get_json(url, token):
    req = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TradeAgent-HK-public-dashboard",
    })
    with urlopen(req, timeout=20) as response:
        return json.load(response)


def load_artifact(artifacts, prefix, filename, token):
    """Read only the named JSON entry from a main-branch artifact ZIP."""
    for item in sorted(artifacts, key=lambda a: a.get("created_at", ""), reverse=True):
        if not item.get("name", "").startswith(prefix) or item.get("expired"):
            continue
        # Do not trust PR or arbitrary branch artifacts for the public Space.
        branch = (item.get("workflow_run") or {}).get("head_branch")
        if branch != "main":
            continue
        try:
            req = Request(
                f"{API_ROOT}/actions/artifacts/{int(item['id'])}/zip",
                headers={"Authorization": "Bearer " + token,
                         "User-Agent": "TradeAgent-HK-public-dashboard"})
            with urlopen(req, timeout=20) as response:
                raw = response.read(MAX_ZIP + 1)
            if len(raw) > MAX_ZIP:
                continue
            with ZipFile(BytesIO(raw)) as archive:
                candidates = [entry for entry in archive.infolist()
                              if entry.filename.split("/")[-1] == filename
                              and not entry.is_dir() and entry.file_size < 3_000_000]
                if len(candidates) != 1:
                    continue
                with archive.open(candidates[0]) as data:
                    result = json.loads(data.read())
                if isinstance(result, dict):
                    return result, item.get("created_at")
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None, None


def select_sources(artifact_fetch=True):
    health = fincept = kronos = None
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token and artifact_fetch:
        try:
            data = get_json(API_ROOT + "/actions/artifacts?per_page=100", token)
            artifacts = data.get("artifacts", [])
            health, _ = load_artifact(artifacts, "production-health-", "production_health.json", token)
            fincept, _ = load_artifact(artifacts, "fincept-research-", "fincept_forecast.json", token)
            kronos, _ = load_artifact(artifacts, "kronos-forecast-", "kronos_forecast.json", token)
        except (OSError, ValueError, KeyError):
            pass
    # These are archived research snapshots, explicitly labeled as historical.
    if fincept is None:
        fincept = load_local("research/fincept-bluechips-2026-10-25/fincept_forecast.json")
    return health, fincept, kronos


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


def snapshot(*, health=None, fincept=None, kronos=None, watchlist=None, kronos_backtest=None, now=None):
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
