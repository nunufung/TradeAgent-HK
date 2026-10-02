import os, sys, requests, re
from bs4 import BeautifulSoup

# 讀你WhatsApp俾嘅號碼：優先 sys.argv > env > default
raw = (sys.argv[1] if len(sys.argv)>1 else os.getenv("STOCK_CODE") or "00700")
CODE = raw.zfill(5) # 700 -> 00700, 1299 -> 01299
print(f"掃描: {CODE}")

MAX_DELTA = 0.10
MAX_SPREAD = 0.30

def get_real_chain():
    url = f"https://www.aastocks.com/tc/stocks/market/option/hk6/option-price.aspx?underlying={CODE}"
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")
        rows=[]
        for tr in soup.find_all("tr"):
            tds=[td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds)<10: continue
            try:
                strike=float(re.sub(r"[^\d.]","",tds[1]))
                bid=float(re.sub(r"[^\d.]","",tds[5])) if tds[5] not in ["-",""] else 0
                ask=float(re.sub(r"[^\d.]","",tds[6])) if tds[6] not in ["-",""] else 0
                delta=float(tds[9]) if tds[9] not in ["-",""] else 0
                if bid>0 and ask>0:
                    rows.append({"strike":strike,"bid":bid,"ask":ask,"delta":abs(delta)})
            except: continue
        if rows: return rows
    except Exception as e:
        print(f"抓取失敗: {e}")
    return []

chain=get_real_chain()
if not chain:
    print(f"{CODE} 暫時抓唔到，試緊模擬")
    chain=[{"strike":500,"delta":0.08,"bid":1.2,"ask":1.4}]

cnt=0
for c in chain:
    spread=(c["ask"]-c["bid"])/c["bid"]
    if c["delta"]<=MAX_DELTA and spread<=MAX_SPREAD:
        cnt+=1
        print(f"PASS {CODE} Strike={c['strike']} Delta={c['delta']:.4f} Spread={spread:.1%} {c['bid']}/{c['ask']}")

print(f"完成: {CODE} 共{cnt}張符合")
