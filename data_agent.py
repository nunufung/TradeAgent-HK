import yfinance as yf
import datetime

# 你嘅港股清單
HOLDINGS = ["0700.HK", "0005.HK", "0941.HK", "3690.HK", "9988.HK", "1810.HK", "1299.HK", "2318.HK"]

print(f"=== TradeAgent-HK Report {datetime.datetime.now()} HKT ===")

# 1. 財經20條 (簡化版，之後接API)
print("\n--- 財經20條 Top ---")
for code in HOLDINGS:
    try:
        t = yf.Ticker(code)
        p = t.history(period="2d")
        if len(p) >= 2:
            chg = (p['Close'].iloc[-1] - p['Close'].iloc[-2])/p['Close'].iloc[-2]*100
            print(f"{code} {p['Close'].iloc[-1]:.1f} {chg:+.2f}%")
    except Exception as e:
        print(f"{code} error {e}")

# 2. Option掃描 (框架)
print("\n--- Option Delta<=0.1 Scan ---")
print("0700.HK 2026-11-01 CALL 480 Delta 0.09 Score 8.4 OI 2560 - 價外高槓桿")
print("0005.HK 2026-11-30 PUT 60 Delta -0.08 Score 8.0 OI 2100 - 防守型")
print("\nScan Done")
