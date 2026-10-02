import sys
sys.path.insert(0, "./tradingagents")
import os
from datetime import datetime
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

def run_market_agent(hk_code: str):
    ticker = hk_code.strip().upper()
    if ".HK" not in ticker:
        ticker = f"{ticker.zfill(4)}.HK"
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"=== {ticker} @ {date_str} ===")
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openai"
    config["deep_think_llm"] = "deepseek-reasoner"
    config["quick_think_llm"] = "deepseek-chat"
    config["max_debate_rounds"] = 1
    config["online_tools"] = True
    os.environ["OPENAI_API_KEY"] = os.getenv("DEEPSEEK_API_KEY")
    os.environ["OPENAI_API_BASE"] = "https://api.deepseek.com/v1"
    ta = TradingAgentsGraph(debug=True, config=config)
    _, decision = ta.propagate(ticker, date_str)
    print(decision)

if __name__ == "__main__":
    import sys as _sys
    run_market_agent(_sys.argv[1] if len(_sys.argv)>1 else "700")
