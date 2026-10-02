import datetime
print(f"=== HK TradeAgent Daily Scan {datetime.date.today()} ===")

stocks = ["0700.HK", "0005.HK", "0941.HK", "3690.HK", "9988.HK", "1810.HK", "1299.HK"]
for s in stocks:
    print(f"{s} checked - placeholder for Option scan Delta<=0.1")

print("Done - Top2 will be generated here after")
