cat > hk_screener.py << 'PY'
import os
import argparse

# --- 1. Load Psychology of Money Skill ---
def load_skill():
    path = "skills/psychology-of-money/SKILL.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "# Skill: psychology-of-money - Reasonable > Rational"

SKILL_TEXT = load_skill()
print(f"📚 Skill loaded: {len(SKILL_TEXT)} chars from skills/psychology-of-money/SKILL.md")

# --- 2. R/R Calculator (your original logic) ---
def calc_rr(long_price, short_price, debit):
    """
    long: stop/lower
    short: target/upper
    debit: cost/premium
    """
    if debit == 0:
        return 0
    # Example: (short - long) / debit or similar
    # Adjust to your formula
    max_profit = short_price - long_price
    risk = debit
    if risk == 0:
        return 0
    return round(max_profit / risk, 2)

# --- 3. DeepSeek call with Skill ---
def ask_llm(ticker, long_p, short_p, debit, rr):
    prompt = f"""
Ticker: {ticker}
Long: {long_p}, Short: {short_p}, Debit: {debit}
R/R: {rr}

Analyze this trade.
"""
    # If you have DEEPSEEK_API_KEY, it will use skill
    try:
        from openai import OpenAI
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return f"R/R {rr} - Set DEEPSEEK_API_KEY to get AI analysis. 📚 Skill [Ch11: Reasonable > Rational]: R/R {rr} is Reasonable if you can hold it."

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SKILL_TEXT + "\n\nYou MUST end every analysis with: 📚 Skill [ChX: Title]: <1 sentence> | Action: Hold/Trim/Size. Use Reasonable > Rational logic."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"R/R {rr} - Error: {e} | 📚 Skill [Ch11: Reasonable > Rational]: Fallback - R/R {rr} is Reasonable"

# --- 4. Main (dynamic tickers, no hardcoded) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HK Screener + Psychology of Money Skill")
    parser.add_argument("--ticker", type=str, default="0700.HK", help="Any HK ticker, e.g. 1818.HK, 0700.HK")
    parser.add_argument("--long", type=float, default=17.5)
    parser.add_argument
