"""Receive authorized Telegram stock requests and deliver the existing PDF report."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_STOCK_COMMAND = re.compile(r"^(?:/stock(?:@[A-Za-z0-9_]+)?\s+)?([0-9]{1,5})$", re.IGNORECASE)
_START_COMMANDS = {"/start", "/help"}


def parse_request(text: str) -> tuple[str, str | None]:
    """Return ('stock', code), ('help', None), or ('invalid', None)."""
    value = text.strip()
    if value.lower() in _START_COMMANDS:
        return "help", None
    match = _STOCK_COMMAND.fullmatch(value)
    if not match:
        return "invalid", None
    code = str(int(match.group(1)))
    if int(code) < 1 or int(code) > 99999:
        return "invalid", None
    return "stock", code


def _token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return token


def _api(method: str, fields: dict[str, Any] | None = None, *, file_field: tuple[str, Path] | None = None) -> dict[str, Any]:
    """Call Telegram without ever including the bot token or response body in errors."""
    token = _token()
    url = f"https://api.telegram.org/bot{token}/{method}"
    fields = fields or {}
    if file_field is None:
        body = urllib.parse.urlencode(fields).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"
    else:
        boundary = "TradeAgentHK" + secrets.token_hex(16)
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
            )
        upload_name, upload_path = file_field
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{upload_name}\"; filename=\"{upload_path.name}\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
        )
        chunks.append(upload_path.read_bytes())
        chunks.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        content_type = f"multipart/form-data; boundary={boundary}"

    request = urllib.request.Request(url, data=body, headers={"Content-Type": content_type}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if method == "getUpdates" and exc.code == 409:
            raise RuntimeError("Telegram polling is blocked by an active webhook; remove that webhook before enabling polling.") from None
        raise RuntimeError(f"Telegram API request failed (HTTP {exc.code})") from None
    except Exception as exc:
        raise RuntimeError(f"Telegram API request failed ({type(exc).__name__})") from None

    if not result.get("ok"):
        code = result.get("error_code", "unknown")
        if method == "getUpdates" and code == 409:
            raise RuntimeError("Telegram polling is blocked by an active webhook; remove that webhook before enabling polling.")
        raise RuntimeError(f"Telegram API rejected {method} (error {code})")
    return result


def _authorized(message: dict[str, Any], chat_id: str, allowed_users: set[str]) -> bool:
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    if str(chat.get("id", "")) != chat_id:
        return False
    if chat.get("type") == "private":
        return str(sender.get("id", "")) == chat_id
    return str(sender.get("id", "")) in allowed_users


def _write_outputs(values: dict[str, str]) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        raise RuntimeError("GITHUB_OUTPUT is not available")
    with open(output_path, "a", encoding="utf-8") as output:
        for name, value in values.items():
            if "\n" in value or "\r" in value:
                raise ValueError("Workflow output must be a single line")
            output.write(f"{name}={value}\n")


def poll() -> int:
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not configured")
    allowed_users = {
        value.strip()
        for value in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
        if value.strip()
    }
    result = _api("getUpdates", {"timeout": 0, "limit": 100, "allowed_updates": json.dumps(["message"])})
    updates = result.get("result", [])
    selected: tuple[dict[str, Any], str, str | None] | None = None
    for update in updates:
        message = update.get("message") or {}
        if not _authorized(message, chat_id, allowed_users):
            continue
        text = message.get("text")
        if not isinstance(text, str):
            continue
        # Do not process Telegram messages sent before this feature was enabled.
        if int(message.get("date", 0)) < 1791292492:  # 2026-10-06 21:14:52 HKT
            continue
        kind, ticker = parse_request(text)
        selected = (update, kind, ticker)
        break

    if selected is None:
        if updates:
            _api("getUpdates", {"offset": int(updates[-1]["update_id"]) + 1, "timeout": 0, "limit": 100})
        _write_outputs({"kind": "none", "ticker": "", "update_id": ""})
        return 0

    update, kind, ticker = selected
    update_id = int(update["update_id"])
    # Confirm older/irrelevant updates but leave the chosen command pending until it is answered.
    if updates and int(updates[0]["update_id"]) < update_id:
        _api("getUpdates", {"offset": update_id, "timeout": 0, "limit": 100})
    _write_outputs({"kind": kind, "ticker": ticker or "", "update_id": str(update_id)})
    return 0


def reply() -> int:
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    kind = os.getenv("REQUEST_KIND", "")
    ticker = os.getenv("REQUEST_TICKER", "")
    messages = {
        "help": "傳港股號碼即可，例如 700；亦可使用 /stock 700。完成後我會回覆分析 PDF。",
        "invalid": "未能辨認股票號碼。請直接傳港股號碼（例如 700），或輸入 /stock 700。",
        "stock": f"收到港股 {ticker}，正在分析；完成後會把 PDF 回覆到此 Telegram 聊天。",
    }
    message = messages.get(kind)
    if not message:
        return 0
    _api("sendMessage", {"chat_id": chat_id, "text": message})
    return 0


def send_pdf() -> int:
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    ticker = os.getenv("REQUEST_TICKER", "")
    pdfs = sorted(Path("pdf_reports").glob("*.pdf"))
    if not pdfs:
        raise RuntimeError("No PDF report was generated")
    caption = f"TradeAgent-HK｜{ticker} 分析報告\nPDF 由 TradingAgents v0.6.0 產生。"
    _api("sendDocument", {"chat_id": chat_id, "caption": caption}, file_field=("document", pdfs[0]))
    return 0


def ack() -> int:
    update_id = os.getenv("REQUEST_UPDATE_ID", "").strip()
    if update_id:
        _api("getUpdates", {"offset": int(update_id) + 1, "timeout": 0, "limit": 100})
    return 0


def notify_failure() -> int:
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    ticker = os.getenv("REQUEST_TICKER", "")
    _api("sendMessage", {
        "chat_id": chat_id,
        "text": f"港股 {ticker} 分析或 PDF 生成未能完成，請稍後再試輸入股票號碼。",
    })
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll Telegram and return a stock analysis PDF")
    parser.add_argument("action", choices=("poll", "reply", "send-pdf", "ack", "notify-failure"))
    action = parser.parse_args().action
    return {"poll": poll, "reply": reply, "send-pdf": send_pdf, "ack": ack, "notify-failure": notify_failure}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Telegram stock bot failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
