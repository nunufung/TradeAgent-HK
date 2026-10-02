import math
from scipy.stats import norm

def bs_delta(S,K,T,r,iv, type='call'):
    d1 = (math.log(S/K)+(r+0.5*iv*iv)*T)/(iv*math.sqrt(T))
    return norm.cdf(d1) if type=='call' else norm.cdf(d1)-1

def filter_chain(chain, max_delta=0.10, max_spread=0.30):
    out=[]
    for c in chain:
        if c['bid']<=0 or c['ask']<=0: continue
        spread = (c['ask']-c['bid'])/c['bid']
        if abs(c['delta'])<=max_delta and spread<=max_spread:
            c['spread']=spread
            out.append(c)
    return sorted(out, key=lambda x: abs(x['delta']-0.08)) # 貼近0.08最好
