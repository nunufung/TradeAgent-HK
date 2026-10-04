import os, sys
sys.path.insert(0, "./tradingagents")
from datetime import datetime
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
import yfinance as yf

# 你嘅自選watchlist，日後改呢度就得
WATCHLIST = ["0700","2800","0005","1299","0941","0939","0388","2318","9988","3690","1810","1211"]

def to_ticker(n):
    n=str(n).replace(".HK","").zfill(4)
    return f"{n}.HK"

def run():
    key = os.getenv("DEEPSEEK_API_KEY")
    os.environ["OPENAI_API_KEY"]=key
    os.environ["OPENAI_API_BASE"]="https://api.deepseek.com/v1"
    date_str = datetime.now().strftime("%Y-%m-%d")
    config = DEFAULT_CONFIG.copy()
    config.update({"llm_provider":"openai","deep_think_llm":"deepseek-reasoner","quick_think_llm":"deepseek-chat","max_debate_rounds":1,"online_tools":True})

    results=[]
    for code in WATCHLIST:
        ticker=to_ticker(code)
        print(f"\n--- Scanning {ticker} ---")
        try:
            ta=TradingAgentsGraph(debug=False, config=config)
            _, decision = ta.propagate(ticker, date_str)
            action="BUY" if "BUY" in decision.upper()[:500] else "SELL" if "SELL" in decision.upper()[:500] else "HOLD"
            results.append((code, ticker, action, decision))
            with open(f"report_{code}.md","w",encoding="utf-8") as f:
                f.write(f"# {ticker} {date_str} - {action}\n\n{decision}")
        except Exception as e:
            print(f"Failed {ticker}: {e}")
            results.append((code, ticker, "ERROR", str(e)))

    # 出總結
    buys=[r for r in results if r[2]=="BUY"]
    with open("daily_buy_list.md","w",encoding="utf-8") as f:
        f.write(f"# 每日買入清單 {date_str}\n\n")
        f.write(f"掃描 {len(WATCHLIST)} 隻，發現 {len(buys)} 隻 BUY：\n\n")
        for code,ticker,action,dec in buys:
            f.write(f"## ✅ {code} {ticker} - {action}\n")
        f.write("\n---\n\n")
        for code,ticker,action,dec in results:
            f.write(f"- {code} {ticker}: **{action}**\n")
    print("\n=== DONE ===")
    print(open("daily_buy_list.md").read())

if __name__=="__main__":
    run()
