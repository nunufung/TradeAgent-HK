import os

def get_chain():
    # Public免費版，先用mock，你之後換AAStocks都係改呢度
    return [
        {"strike": 87.5, "delta": 0.0858, "bid": 0.42, "ask": 0.50},
        {"strike": 90, "delta": 0.045, "bid": 0.25, "ask": 0.35},
    ]

chain = get_chain()
print(f"Found {len(chain)} contracts")

# 有Secret就提示
if os.getenv("FUTU_PWD"):
    print("Futu Live mode: ON")
else:
    print("Public mode: ON (冇Futu密碼)")

# 你嘅雙規則
for c in chain:
    spread = (c["ask"]-c["bid"])/c["bid"]
    if abs(c["delta"]) <= 0.10 and spread <= 0.30:
        print(f"PASS: Strike {c['strike']} Delta {c['delta']} Spread {spread:.1%} Bid {c['bid']} Ask {c['ask']}")

print("DONE")
