from __future__ import annotations
import os
from datetime import datetime


def analyze_underlying(symbol: str) -> str | None:
    """Optional TradingAgents commentary. Never overrides deterministic rules."""
    if os.getenv("ENABLE_TRADINGAGENTS", "0") != "1":
        return None
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        cfg = DEFAULT_CONFIG.copy()
        cfg["llm_provider"] = "openai"
        cfg["deep_think_llm"] = "deepseek-reasoner"
        cfg["quick_think_llm"] = "deepseek-chat"
        cfg["max_debate_rounds"] = 1
        cfg["online_tools"] = True
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            return "TradingAgents skipped: DEEPSEEK_API_KEY unavailable"
        os.environ["OPENAI_API_KEY"] = key
        os.environ["OPENAI_API_BASE"] = "https://api.deepseek.com/v1"
        graph = TradingAgentsGraph(debug=False, config=cfg)
        _, decision = graph.propagate(symbol, datetime.now().strftime("%Y-%m-%d"))
        return str(decision)
    except Exception as exc:
        return f"TradingAgents unavailable: {exc}"
