"""Optional TradingAgents adapter retained for compatibility.

TradingAgents commentary is explicitly non-authoritative. The deterministic
TradeAgent-HK rule engine decides whether an option is eligible.
"""
import sys
sys.path.insert(0, "./tradingagents")
from tradeagent.agents.tradingagents_adapter import analyze_underlying


def to_ticker(num: str) -> str:
    clean = str(num).strip().upper().replace(".HK", "").lstrip("0")
    return f"{clean.zfill(4)}.HK"


def run_market_agent(hk_code: str):
    ticker = to_ticker(hk_code)
    result = analyze_underlying(ticker)
    print(result or "TradingAgents disabled. Set ENABLE_TRADINGAGENTS=1 to enable optional commentary.")


if __name__ == "__main__":
    run_market_agent(sys.argv[1] if len(sys.argv) > 1 else "700")
