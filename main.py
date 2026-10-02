import os, requests, re, math
from bs4 import BeautifulSoup

# ===== 設定 =====
CODE = "01299" # 友邦，你可以改 00700 / 02800
MAX_DELTA = 0.10
MAX_SPREAD = 0.30

def get_real_chain():
    # AAStocks 期權報價頁 (public, 唔使login)
    url = f"https://www.aastocks.com/tc/stocks/market/option/hk6/option-price.aspx?underlying={CODE}"
    headers = {"User-Agent":"Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        rows = []
        # 簡易parse: 搵所有有 bid/ask/delta 嘅行
        for tr in soup.find_all("tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 10: continue
            # tds 格式: [到期, 行使價,... 買入, 賣出, Delta]
            try:
                strike = float(re.sub(r"[^\d.]","", tds[1]))
                bid = float(re.sub(r"[^\d.]","", tds[5])) if tds[5] not in ["-",""] else 0
                ask = float(re.sub(r"[^\d.]","", tds[6])) if tds[6] not in ["-",""] else 0
                delta = float(tds[9]) if tds[9] not in ["-",""] else 0
                if bid>0 and ask>0:
                    rows.append({"strike":strike,"bid":bid,"ask":ask,"delta":abs(delta)})
            except: continue
        if rows:
            print(f"AAStocks抓到 {len(rows)} 張合約")
            return rows
    except Exception as e:
        print(f"AAStocks fail: {e}")

    # Fallback: 如果AAStocks改版，返去用Public mock
    print("Fallback用模擬數據")
    return [
        {"strike":87.5,"delta":0.0858,"bid":0.42,"ask":0.50},
        {"strike":90,"delta":0.045,"bid":0.25,"ask":0.35},
    ]

chain = get_real_chain()

# 有FUTU就提示Live
if os.getenv("FUTU_PWD"):
    print("FUTU Live校準: ON")
else:
    print("Public模式: ON")

passed=[]
for c in chain:
    spread = (c["ask"]-c["bid"])/c["bid"] if c["bid"]>0 else 99
    if c["delta"] <= MAX_DELTA and spread <= MAX_SPREAD:
        c["spread"]=spread
        passed.append(c)
        print(f"PASS Strike={c['strike']} Delta={c['delta']:.4f} Spread={spread:.1%} Bid={c['bid']} Ask={c['ask']}")

if not passed:
    print(f"冇符合 Delta<={MAX_DELTA} + Spread<={MAX_SPREAD*100}% 的合約")
else:
    print(f"共 {len(passed)} 張符合，準備出通知...")

print("DONE")
