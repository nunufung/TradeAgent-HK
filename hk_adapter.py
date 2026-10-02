import sys
sys.path.insert(0, "./tradingagents")
import os
from datetime import datetime
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

def to_ticker(num: str) -> str:
    clean = str(num).strip().upper().replace(".HK","").lstrip("0")
    mapping = {"700":"0700.HK","2800":"2800.HK","1299":"1299.HK","9988":"9988.HK","388":"0388.HK","5":"0005.HK"}
    return mapping.get(clean, f"{clean.zfill(4)}.HK")

def run_market_agent(hk_code: str):
    date_str = datetime.now().strftime("%Y-%m-%d")
    ticker = to_ticker(hk_code)
    print(f"=== DeepSeek Market Agent: {hk_code} -> {ticker} @ {date_str} ===")
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openai"
    config["deep_think_llm"] = "deepseek-reasoner"
    config["quick_think_llm"] = "deepseek-chat"
    config["max_debate_rounds"] = 1
    config["online_tools"] = True
    # FIX: 唔會crash，冇key會出提示
    key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        print("ERROR: DEEPSEEK_API_KEY not found in Secrets! Please add it in GitHub Settings")
        sys.exit(1)
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_API_BASE"] = "https://api.deepseek.com/v1"
    ta = TradingAgentsGraph(debug=True, config=config)
    _, decision = ta.propagate(ticker, date_str)
    print("\n" + "="*60 + "\nFINAL\n" + "="*60)
    print(decision)
    with open(f"report_{ticker.replace('.HK','')}.md","w") as f:
        f.write(f"# {ticker} {date_str}\n\n{decision}")

if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv)>1 else "700"
    run_market_agent(code)
