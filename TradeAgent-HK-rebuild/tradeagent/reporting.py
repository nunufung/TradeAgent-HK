from __future__ import annotations
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json


def _pct(v: float) -> str:
    return f"{v*100:.1f}%"


def render_report(mode: str, stocks, option_decisions, errors, rules, market_context=None) -> tuple[str, dict]:
    tz = ZoneInfo(rules["market"]["timezone"])
    now = datetime.now(tz)
    market_context = market_context or []
    lines = [f"# TradeAgent-HK Daily Report — {now:%Y-%m-%d %H:%M HKT}", ""]
    payload = {
        "generated_at": now.isoformat(),
        "mode": mode,
        "market": market_context,
        "stocks": [],
        "stock_recommendation": None,
        "option": None,
        "errors": errors,
    }

    if mode == "premarket":
        lines += ["## 07:00 Pre-market", "Informational only. No new option position is authorized before 10:00 HKT.", ""]
    else:
        lines += ["## 10:00 Actionable Scan", "The engine applies hard risk filters before ranking any option.", ""]

    if market_context:
        lines += ["## Market context", "| Market | Last | 1D | 5D |", "|---|---:|---:|---:|"]
        for m in market_context:
            lines.append(f"| {m['label']} | {m['last']:.3f} | {_pct(m['day_change'])} | {_pct(m['five_day_change'])} |")
        lines.append("")

    lines += ["## Stock ranking", "| Rank | Symbol | Score | Trend | Spot | 5D | 20D | RSI |", "|---:|---|---:|---|---:|---:|---:|---:|"]
    for i, s in enumerate(stocks[:5], 1):
        lines.append(f"| {i} | {s.symbol} | {s.score:.2f}/10 | {s.trend} | {s.spot:.2f} | {_pct(s.return_5d)} | {_pct(s.return_20d)} | {s.rsi14:.1f} |")
        payload["stocks"].append({
            "symbol": s.symbol,
            "score": s.score,
            "trend": s.trend,
            "spot": s.spot,
            "return_5d": s.return_5d,
            "return_20d": s.return_20d,
            "rsi14": s.rsi14,
            "risk_flags": s.risk_flags,
            "headlines": s.headlines,
        })

    lines.append("")
    if stocks:
        lines += ["## Watchlist news / risk",]
        for s in stocks[:3]:
            flags = ", ".join(s.risk_flags) if s.risk_flags else "none detected from retrieved headlines"
            lines.append(f"- **{s.symbol}** — risk flags: {flags}")
            for h in s.headlines[:2]:
                lines.append(f"  - {h}")
        lines.append("")

    if mode == "actionable":
        min_score = rules["stock_scoring"]["actionable_min_score"]
        best = stocks[0] if stocks else None
        if best and best.score >= min_score and not best.risk_flags:
            stock_action = "WATCH / BULLISH BIAS" if best.trend != "bearish" else "WATCH / BEARISH BIAS"
            payload["stock_recommendation"] = {
                "action": stock_action,
                "symbol": best.symbol,
                "score": best.score,
                "trend": best.trend,
                "spot": best.spot,
            }
            lines += ["## Stock recommendation", f"**{stock_action}: {best.symbol}** — technical score {best.score:.2f}/10, trend {best.trend}.", ""]
        else:
            lines += ["## Stock recommendation", "**NO STOCK TRADE** — no name cleared the configured quality/risk threshold.", ""]

        lines.append("## Option recommendation")
        if option_decisions:
            d = option_decisions[0]
            c = d.contract
            payload["option"] = {
                "action": d.action,
                "score": d.score,
                "symbol": c.symbol,
                "type": c.option_type,
                "strike": c.strike,
                "expiry": c.expiry.isoformat(),
                "dte": c.dte(now.date()),
                "bid": c.bid,
                "ask": c.ask,
                "delta": c.delta,
                "spread_pct": c.spread_pct,
                "margin_premium_ratio": c.margin_premium_ratio,
                "reasons": d.reasons,
                "warnings": d.warnings,
            }
            lines += [
                f"**{d.action}: {c.symbol} Short {c.option_type} {c.strike:g} exp {c.expiry.isoformat()}**",
                f"- DTE: {c.dte(now.date())}",
                f"- Bid / Ask: {c.bid:g} / {c.ask:g}",
                f"- Delta: {c.delta:.3f}" if c.delta is not None else "- Delta: unavailable",
                f"- Spread: {c.spread_pct*100:.1f}%" if c.spread_pct is not None else "- Spread: unavailable",
                f"- Margin/Premium: {c.margin_premium_ratio:.2f}x" if c.margin_premium_ratio is not None else "- Margin/Premium: unavailable",
                f"- Rule score: {d.score:.1f}/100",
                "- Take profit: close when 50–70% of original premium has been captured.",
                "- Stop/repair: if loss exceeds 100% of original premium, close/reduce/roll; do not average down.",
            ]
            if d.warnings:
                lines.append("- Warnings: " + "; ".join(d.warnings))
        else:
            lines += [
                "**OPTION: NO TRADE**",
                "No verified contract passed all required data/risk checks. The engine does not fabricate Delta, DTE, liquidity, spread, or margin inputs.",
            ]
        lines.append("")

    if errors:
        lines += ["## Data quality notes"] + [f"- {e}" for e in errors]

    return "\n".join(lines).rstrip() + "\n", payload


def save_report(markdown: str, payload: dict, report_dir: str | Path = "reports") -> tuple[Path, Path]:
    p = Path(report_dir)
    p.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(payload["generated_at"]).strftime("%Y%m%d_%H%M")
    mode = payload["mode"]
    md = p / f"{stamp}_{mode}.md"
    js = p / f"{stamp}_{mode}.json"
    md.write_text(markdown, encoding="utf-8")
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (p / f"latest_{mode}.md").write_text(markdown, encoding="utf-8")
    (p / f"latest_{mode}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return md, js
