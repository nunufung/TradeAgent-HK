import os, argparse

def get_api_key():
    # FIX: don't crash if key missing - TradeAgent-HK can run without OpenAI for calc
    key = os.getenv("OPENAI_API_KEY")
    if key:
        os.environ["OPENAI_API_KEY"] = key
    return key

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
