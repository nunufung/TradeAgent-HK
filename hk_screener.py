import os, argparse, json

# ===== DeepSeek 兼容 OpenAI SDK (你寫嘅保留) =====
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

def ask_llm(prompt):
    if client is None:
        return None # fallback 去本地 R/R 計算
    try:
        # 根據有冇 deepseek key 自動揀 model
        model_name = "deepseek-chat" if os.getenv("DEEPSEEK_API_KEY") else "gpt-4o-mini"
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role":"system","content":"You are TradeAgent-HK, HK option expert. Reply zh-HK concise."},
                {"role":"user","content":prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None

# ===== 兼容舊 code: 呢個就係你之前 get_api_key() 想做嘅嘢 =====
def get_api_key():
    # 已經喺上面處理好，無 key 都唔 crash，回傳 None 就得
    return os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")

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

    # 加埋 Psychology of Money Skill (有 key 先叫 LLM，無就用本地)
    prompt = f"{args.ticker} Bull {long_strike}/{short_strike} debit {debit} R/R {round(rr,2)}，用 Psychology of Money 評 1句"
    skill = ask_llm(prompt)
    if skill:
        print(f"📚 Skill: {skill}")
    else:
        print(f"📚 Skill: R/R {round(rr,2)} 屬 Reasonable，止蝕40%符合Survival，到60%記住Enough。")
    return

def run():
    get_api_key() # 而家 safe，就算 None 都唔 crash
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', default='0700.HK')
    parser.add_argument('--long', type=float, required=True)
    parser.add_argument('--short', type=float, required=True)
    parser.add_argument('--debit', type=float, required=True)
    parser.add_argument('--lot', type=int, default=100)
    global args
    args = parser.parse_args()
    bull_call_spread(args.long, args.short, args.debit, args.lot)

if __name__ == "__main__":
    run()
