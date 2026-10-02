# hk_adapter.py - DeepSeek版 TradingAgents for HK stocks
import os
from datetime import datetime
from tradingagents.graph.trading_graph import TradingGraph
from tradingagents.default_config import DEFAULT_CONFIG

def to_ticker(num: str) -> str:
    """700 / 00700 / 0700.HK -> 0700.HK"""
    clean = str(num).strip().upper().replace(".HK","").lstrip("0")
    mapping = {
        "700": "0700.HK",
        "2800": "2800.HK",
        "1299": "1299.HK",
        "9988": "9988.HK",
        "388": "0388.HK",
        "5": "0005.HK",
    }
    return mapping.get(clean, f"{clean.zfill(4)}.HK")

def run_market_agent(hk_code: str, date_str: str = None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    ticker = to_ticker(hk_code)
    print(f"=== DeepSeek Market Agent: {hk_code} -> {ticker} @ {date_str} ===")

    # --- DeepSeek設定 ---
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openai" # DeepSeek行OpenAI兼容
    config["deep_think_llm"] = "deepseek-reasoner" # R1
    config["quick_think_llm"] = "deepseek-chat" # V3
    config["max_debate_rounds"] = 1
    config["online_tools"] = True
    config["max_memory"] = 3

    # 指向DeepSeek API
    # GitHub Secrets會注入 DEEPSEEK_API_KEY
    deepseek_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not deepseek_key:
        raise ValueError("搵唔到 DEEPSEEK_API_KEY，請去GitHub Secrets設定")

    os.environ["OPENAI_API_KEY"] = deepseek_key
    os.environ["OPENAI_API_BASE"] = "https://api.deepseek.com/v1"

    ta = TradingGraph(debug=True, config=config)
    _, decision = ta.propagate(ticker, date_str)

    print("\n" + "="*50)
    print(decision)
    print("="*50)
    return decision

if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv)>1 else "700"
    run_market_agent(code)
