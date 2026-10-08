import sys
sys.path.append("./tradingagents")
import os
import json
from pathlib import Path
from linked_stock_analysis import signal_from_state, _futu_code, ANALYSTS
from market_recommendations import write_recommendations
from datetime import datetime
from copy import deepcopy
from zoneinfo import ZoneInfo
from free_tech_news import configure_free_news, attach_news_context, write_news_audit
from book_skill_context import attach_book_context
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

def to_ticker(num: str) -> str:
    clean = str(num).strip().upper().replace(".HK","").lstrip("0")
    mapping = {"700":"0700.HK","2800":"2800.HK","1299":"1299.HK","9988":"9988.HK","388":"0388.HK","5":"0005.HK"}
    return mapping.get(clean, f"{clean.zfill(4)}.HK")

def run_market_agent(hk_code: str):
    date_str = datetime.now(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d")
    ticker = to_ticker(hk_code)
    print(f"=== DeepSeek Market Agent: {hk_code} -> {ticker} @ {date_str} ===")
    config = deepcopy(DEFAULT_CONFIG)
    config["llm_provider"] = "openai"
    config["deep_think_llm"] = "deepseek-reasoner"
    config["quick_think_llm"] = "deepseek-chat"
    config["max_debate_rounds"] = 1
    config["online_tools"] = True
    config["backend_url"] = "https://api.deepseek.com"
    config["output_language"] = "Traditional Chinese"
    # FIX: 唔會crash，冇key會出提示
    key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        print("ERROR: DEEPSEEK_API_KEY not found in Secrets! Please add it in GitHub Settings")
        sys.exit(1)
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_API_BASE"] = "https://api.deepseek.com/v1"
    selected_analysts = ("market", "social", "news", "fundamentals")
    print("Analyst team: " + ", ".join(selected_analysts))
    news_batch = configure_free_news(config)
    ta = TradingAgentsGraph(selected_analysts=selected_analysts, debug=True, config=config)
    attach_news_context(ta, news_batch)
    book_skills = attach_book_context(ta)
    state, decision = ta.propagate(ticker, date_str)
    write_news_audit(news_batch, ticker, state.get("news_report", ""))
    print("\n" + "="*60 + "\nFINAL\n" + "="*60)
    print(decision)
    payload = {"date": date_str, "generated_at": datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(),
               "analyst_set": list(ANALYSTS), "book_skills": book_skills,
               "signals": {_futu_code(hk_code): signal_from_state(state, decision, ticker)}}
    payload['signals'][_futu_code(hk_code)]['book_skills'] = book_skills
    Path("stock_signals.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    skill_note = '已載入書籍風控 Skill：' + ', '.join(item['name'] for item in book_skills) + '；期權硬性守則優先。\n\n'
    Path("stock_analysis.md").write_text(skill_note + "\n\n".join(
        f"## {name}\n\n{text}" for name, text in payload["signals"][_futu_code(hk_code)]["reports"].items()), encoding="utf-8")
    write_recommendations(payload)
    final_report = state.get("final_trade_decision") or decision
    with open(f"report_{ticker.replace('.HK','')}.md","w", encoding="utf-8") as f:
        f.write(f"# {ticker} {date_str}\n\n{skill_note}評級：{decision}\n\n{final_report}")

if __name__ == "__main__":
    sys.excepthook = lambda exc_type, *_: print(f"Analysis failed ({exc_type.__name__}); sensitive error details omitted.")
    code = sys.argv[1] if len(sys.argv)>1 else "700"
    run_market_agent(code)
