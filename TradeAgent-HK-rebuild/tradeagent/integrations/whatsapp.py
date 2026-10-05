from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_recipient(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        raise ValueError("WhatsApp recipient contains no digits")
    return digits


def compact_summary(payload: dict[str, Any], max_chars: int = 1200) -> str:
    mode = str(payload.get("mode", "report")).lower()
    lines: list[str] = []

    if mode == "premarket":
        lines.append("07:00 HKT PRE-MARKET")
        markets = payload.get("market") or []
        for m in markets[:4]:
            try:
                lines.append(
                    f"{m.get('label', 'Market')}: {float(m.get('day_change', 0))*100:+.1f}% 1D"
                )
            except (TypeError, ValueError):
                continue
        stocks = payload.get("stocks") or []
        if stocks:
            top = stocks[:3]
            lines.append("Watch: " + ", ".join(
                f"{s.get('symbol')} {s.get('trend', '')} {float(s.get('score', 0)):.1f}/10"
                for s in top
            ))
        lines.append("No new option trade before 10:00 HKT.")
    else:
        lines.append("10:00 HKT ACTIONABLE")
        stock = payload.get("stock_recommendation")
        if stock:
            lines.append(
                f"Stock: {stock.get('symbol')} | {stock.get('action')} | "
                f"{float(stock.get('score', 0)):.1f}/10 | {stock.get('trend', '')}"
            )
        else:
            lines.append("Stock: NO STOCK TRADE")

        opt = payload.get("option")
        if opt:
            margin = opt.get("margin_premium_ratio")
            margin_text = f" | M/P {float(margin):.1f}x" if margin is not None else ""
            delta = opt.get("delta")
            delta_text = f" | Δ {float(delta):.2f}" if delta is not None else ""
            lines.append(
                f"Option: {opt.get('action')} {opt.get('symbol')} Short {opt.get('type')} "
                f"{opt.get('strike')} exp {opt.get('expiry')} | DTE {opt.get('dte')}"
                f"{delta_text}{margin_text}"
            )
            lines.append("TP: capture 50–70% premium | Loss >100%: close/reduce/roll")
        else:
            lines.append("Option: NO TRADE")

    errors = payload.get("errors") or []
    if errors:
        lines.append("Data note: " + str(errors[0])[:240])

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return text


def send_whatsapp(summary: str, report_mode: str) -> dict[str, Any]:
    token = _required("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = _required("WHATSAPP_PHONE_NUMBER_ID")
    recipient = normalize_recipient(_required("WHATSAPP_RECIPIENT"))
    graph_version = _required("WHATSAPP_GRAPH_VERSION")
    message_mode = os.getenv("WHATSAPP_MESSAGE_MODE", "template").strip().lower()

    endpoint = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if message_mode == "template":
        template_name = _required("WHATSAPP_TEMPLATE_NAME")
        language = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "en_US").strip() or "en_US"
        body: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": report_mode},
                            {"type": "text", "text": summary},
                        ],
                    }
                ],
            },
        }
    elif message_mode == "text":
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": summary},
        }
    else:
        raise ValueError("WHATSAPP_MESSAGE_MODE must be 'template' or 'text'")

    response = requests.post(endpoint, headers=headers, json=body, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(
            f"WhatsApp API returned HTTP {response.status_code}: {response.text[:1000]}"
        )
    return response.json()


def main() -> int:
    ap = argparse.ArgumentParser(description="Send a TradeAgent-HK report to WhatsApp")
    ap.add_argument("report_json", help="Path to latest_premarket.json or latest_actionable.json")
    ap.add_argument("--dry-run", action="store_true", help="Print message without sending")
    args = ap.parse_args()

    payload = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    report_mode = str(payload.get("mode", "report"))
    summary = compact_summary(payload)

    if args.dry_run:
        print(summary)
        return 0

    result = send_whatsapp(summary, report_mode)
    message_ids = [m.get("id") for m in result.get("messages", []) if isinstance(m, dict)]
    print("WhatsApp alert sent" + (f": {', '.join(message_ids)}" if message_ids else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
