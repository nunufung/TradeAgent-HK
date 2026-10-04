#!/usr/bin/env python3
"""
hk_screener.py - Dynamic Bull Call Spread R/R calculator
No hardcoded tickers. All inputs via CLI.
"""
import argparse
import os
import sys

# --- Psychology of Money Skill ---
def load_skill():
    try:
        with open("skills/psychology-of-money/SKILL.md","r",encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return "Skill: psychology-of-money"
SKILL_TEXT = load_skill()
print(f"📚 Loaded Skill: {len(SKILL_TEXT)} chars")
# ---------------------------------

def get_api_key():
    return os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")

def calc_spread(long_strike, short_strike, debit, lot_size=100, fx=1.0):
    if long_strike >= short_strike:
        raise ValueError("long_strike must < short_strike")
    if debit <= 0:
        raise ValueError("debit must > 0")

    max_loss = debit * lot_size * fx
    max_gain = (short_strike - long_strike - debit) * lot_size * fx
    rr = max_gain / max_loss if max_loss else 0
    breakeven = long_strike + debit
    return max_loss, max_gain, rr, breakeven

def ask_llm(rr, ticker, long_s, short_s, debit):
    key = get_api_key()
    # local fallback - no ticker specific logic
    local_msg = f"R/R {rr:.2f} -> {'High Conviction' if rr>=3 else 'Reasonable' if rr>=2 else 'Low'}: Reward {'covers' if rr>=2 else 'barely covers'} risk. Check breakeven & position size."

    if not key:
        print("⚠️ No DEEPSEEK_API_KEY, use local calc only")
        return f"📚 Skill: {local_msg} | Ticker={ticker} Long={long_s} Short={short_s} Debit={debit}"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        prompt = f"Ticker {ticker} Bull Call Spread: long {long_s} short {short_s} debit {debit} R/R {rr:.2f}. Give 1-line Quant-Risk skill comment."
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"user","content":prompt}],
            max_tokens=120
        )
        return f"📚 Skill (deepseek-chat): {resp.choices[0].message.content.strip()}"
    except Exception as e:
        return f"📚 Skill: {local_msg} (LLM fallback: {e})"

def main():
    p = argparse.ArgumentParser(description="Dynamic HK Bull Call R/R - no hardcoded tickers")
    p.add_argument("--ticker", required=True, help="Any ticker e.g. 0700.HK, 1818, AAPL")
    p.add_argument("--long", type=float, required=True, dest="long_strike", help="Long strike")
    p.add_argument("--short", type=float, required=True, dest="short_strike", help="Short strike")
    p.add_argument("--debit", type=float, required=True, help="Debit per share")
    p.add_argument("--lot", type=int, default=100, help="Lot size, default 100")
    p.add_argument("--fx", type=float, default=1.0, help="FX multiplier")
    args = p.parse_args()

    max_loss, max_gain, rr, breakeven = calc_spread(args.long_strike, args.short_strike, args.debit, args.lot, args.fx)

    print(f"\nTicker: {args.ticker} | Long {args.long_strike} / Short {args.short_strike} / Debit {args.debit}")
    print(f"Max Loss {max_loss:.2f} / Max Gain {max_gain:.2f} / R/R {rr:.2f} / Breakeven {breakeven:.2f}")

    skill_msg = ask_llm(rr, args.ticker, args.long_strike, args.short_strike, args.debit)
    print(skill_msg)

if __name__ == "__main__":
    main()
