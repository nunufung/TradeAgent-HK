"""Append-only, bounded research event trace. No prompts, report text or keys."""
from __future__ import annotations
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

HKT = ZoneInfo("Asia/Hong_Kong")
ROLES = ("market", "social", "news", "fundamentals")
EVENTS = {"RUN_STARTED", "GRAPH_STARTED", "GRAPH_FINISHED", "GRAPH_FAILED",
          "REPORT_OBSERVED", "REPORT_MISSING", "RUN_FINISHED"}
LIMIT = 250

def emit(kind: str, *, ticker: str = "", role: str = "", state: str = "", path: str | None = None):
    """Emit only known enum events and codes; do not accept arbitrary model output."""
    if kind not in EVENTS or (role and role not in ROLES):
        raise ValueError("Invalid event type or role")
    dest = Path(path or os.getenv("TAHK_AGENT_EVENTS_PATH", "agent_events.jsonl"))
    if not ticker.startswith("HK.") or not ticker[3:].isdigit() or len(ticker) != 8:
        raise ValueError("Invalid ticker")
    item = {"version": 1, "timestamp_hkt": datetime.now(HKT).isoformat(),
            "kind": kind, "ticker": ticker, "role": role or None,
            "state": state if state in ("STARTED", "COMPLETED", "FAILED", "OBSERVED", "MISSING") else None}
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as out:
        out.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item

def read(path: str | Path) -> list[dict]:
    f = Path(path)
    if not f.is_file() or f.stat().st_size > 160_000:
        return []
    events = []
    for line in f.read_text(encoding="utf-8").splitlines()[:LIMIT]:
        try:
            item = json.loads(line)
        except (ValueError, TypeError):
            return []
        if (not isinstance(item, dict) or item.get("kind") not in EVENTS
                or item.get("version") != 1 or item.get("role") not in (*ROLES, None)):
            return []
        events.append(item)
    return events
