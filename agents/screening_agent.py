class ScreeningAgent:
    def __init__(self, rules):
        self.r = rules
    def screen(self, chains):
        res=[]
        for opt in chains:
            if abs(opt['delta']) > self.r['delta_max']: continue
            if not any(abs(opt['days_to_expiry']-d) <= self.r['expiry_tolerance'] for d in self.r['expiry_days']): continue
            if abs(opt['strike']-opt['spot'])/opt['spot'] > self.r['price_band_pct']: continue
            if opt['oi'] < self.r['min_oi'] or opt['vol'] < self.r['min_volume']: continue
            score = opt['vol']*0.4 + (1/max(opt['iv'],0.1))*0.3 + opt.get('gex',0)*0.3
            opt['score']=score
            res.append(opt)
        return sorted(res, key=lambda x: x['score'], reverse=True)[:5]
