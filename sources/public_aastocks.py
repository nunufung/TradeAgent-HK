import requests, re
# AAStocks 免費期權頁，唔使密碼
def get_chain_public(code):
    # 示例: 用yfinance/AAStocks抓，你之後可以換成真URL
    # 這裡先做mock + 實抓框架
    url = f"https://www.aastocks.com/tc/stocks/options/detail.aspx?symbol={code}"
    # resp = requests.get(url, headers={"User-Agent":"Mozilla"})
    # parse Bid/Ask...
    # 為demo，先回傳你已知
    if code=="1299":
        return [
            {"strike":87.5, "delta":0.0858, "bid":0.42, "ask":0.50, "expiry":"2025-12-30", "type":"call"},
            {"strike":90, "delta":0.045, "bid":0.25, "ask":0.35, "expiry":"2025-12-30", "type":"call"},
        ]
    return []
