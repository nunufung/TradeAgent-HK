import os
from sources.public_aastocks import get_chain
from sources.futu_private import get_chain_futu_if_secret

# 1. 先用Public (AAStocks) 免Login跑
chain = get_chain("1299")  # Bid/Ask + IV

# 2. 如果有GitHub Secret，自動用Futu校準Delta
if os.getenv("FUTU_PWD"):  # GitHub Secrets注入
    try:
        live = get_chain_futu_if_secret("1299")
        chain.update_live_delta(live)  # 用你Futu嘅0.0858覆蓋
        print("Used Futu Live Delta")
    except:
        pass

# 3. 跑你雙規則
filtered = [c for c in chain if c.delta<=0.10 and c.spread<=0.30]
