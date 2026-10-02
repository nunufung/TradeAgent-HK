import yfinance as yf, datetime
HOLDINGS = ["0700.HK","0005.HK","0941.HK","3690.HK","9988.HK","1810.HK","1299.HK","2318.HK"]
class DataAgent:
    def get_chains(self):
        mock=[]
        for sym in HOLDINGS:
            spot = yf.Ticker(sym).history(period="1d")['Close'].iloc[-1] if True else 100
            mock.append({'symbol':sym,'type':'CALL','strike':round(spot*1.18,1),'spot':spot,'delta':0.09,'days_to_expiry':32,'oi':1200,'vol':350,'iv':0.42,'expiry':'2026-11-28','gex':0.5})
            mock.append({'symbol':sym,'type':'PUT','strike':round(spot*0.85,1),'spot':spot,'delta':-0.08,'days_to_expiry':58,'oi':980,'vol':280,'iv':0.51,'expiry':'2026-12-20','gex':-0.2})
        return mock
