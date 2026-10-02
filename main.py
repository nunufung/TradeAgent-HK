import os
from sources.public_aastocks import get_chain_public
from sources.futu_private import get_chain_futu_if_secret
from calc_delta import filter_chain

STOCKS = ["1299", "00005"]

for code in STOCKS:
    print(f"\n=== {code} ===")
    chain = get_chain_public(code)
    print(f"Public source: {len(chain)} contracts")

    # 1+3混合: 有Secret先校準
    if os.getenv("FUTU_PWD"):
        live = get_chain_futu_if_secret(code)
        if live:
            for c in chain:
                if c['strike'] in live:
                    c['delta'] = live[c['strike']]['delta'] # 用Futu Live Delta 0.0858覆蓋
                    c['bid'] = live[c['strike']]['bid']
                    c['ask'] = live[c['strike']]['ask']
            print(">> Futu Live校準完成")

    # 雙規則
    passed = filter_chain(chain, max_delta=0.10, max_spread=0.30)
    for p in passed[:3]:
        print(f"PASS: {p['strike']} Delta={p['delta']:.4f} Spread={p['spread']:.1%} Bid={p['bid']} Ask={p['ask']}")
