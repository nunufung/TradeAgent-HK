import os, argparse

# ===== DeepSeek 兼容 OpenAI SDK =====
try:
    from openai import OpenAI
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = "https://api.deepseek.com" if os.getenv("DEEPSEEK_API_KEY") else None

    if api_key:
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        print(f"✅ LLM client ready: {'DeepSeek' if base_url else 'OpenAI'}")
    else:
        client = None
        print("⚠️ No DEEPSEEK_API_KEY / OPENAI_API_KEY, use local calc only")
except Exception as e:
    client = None
    print(f"⚠️ LLM init failed ({e}), use local calc only")

# 用嘅時候咁 check：
def ask_llm(prompt):
    if client is None:
        return None # fallback 去本地 R/R 計算
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat", # 用 deepseek-chat / deepseek-reasoner
            messages=[{"role":"user","content":prompt}],
            temperature=0.3
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None
        

def bull_call_spread(long_strike, short_strike, debit, lot_size=100):
    max_loss = debit * lot_size
    max_gain = (short_strike - long_strike - debit) * lot_size
    breakeven = long_strike + debit
    rr = max_gain / max_loss if max_loss else 0
    print(f"--- TradeAgent-HK Option Calc: Bull Call Spread ---")
    print(f"Ticker: {args.ticker} | Long {long_strike} / Short {short_strike}")
    print(f"Net Debit: {debit} x {lot_size} = HKD {max_loss}")
    print(f"Max Loss: HKD {max_loss}")
    print(f"Max Gain: HKD {max_gain}")
    print(f"Breakeven: {breakeven}")
    print(f"R/R: {round(rr,2)}")
    print(f"2-min check: IV high? -> Spread is safer. Don't hold past Thu.")
    return

def run():
    get_api_key() # now safe even if None
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', default='0700.HK')
    parser.add_argument('--long', type=float, required=True)
    parser.add_argument('--short', type=float, required=True)
    parser.add_argument('--debit', type=float, required=True)
    global args
    args = parser.parse_args()
    bull_call_spread(args.long, args.short, args.debit)

if __name__ == "__main__":
    run()
