"""Bounded Fincept artifact reader; no market/model dependencies in daily process."""
import json,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
HKT=timezone(timedelta(hours=8))

def brief(path=Path('fincept_forecast.json'),now=None):
    fallback='Fincept：暫無有效新預測；沿用四分析員及期權風控。'
    try:
        d=json.loads(Path(path).read_text());now=now or datetime.now(HKT)
        if d.get('source_commit')!='3d8617cae3f13c93874d4bee4fb0f2846e9c83bc':return fallback
        if d.get('lookback')!=400 or d.get('horizon')!=5 or d.get('order')!=[1,1,1]:return fallback
        if d['schema_version']!=1 or not timedelta(0)<=now-datetime.fromisoformat(d['generated_at'])<=timedelta(hours=26):return fallback
        if not 0<=(now.date()-datetime.fromisoformat(d['data_cutoff']).date()).days<=7:return fallback
        expected={s['code'] for s in d['universe'] if s['group']=='bluechip'}
        rows=d['forecasts']
        if not 1<=len(rows)<=50 or len({r['ticker'] for r in rows})!=len(rows):return fallback
        good=[r for r in rows if r['status']=='FORECAST_ONLY' and r['ticker'] in expected and r['ticker'].isdigit() and len(r['ticker'])==4 and r['data_cutoff']==d['data_cutoff'] and math.isfinite(r['endpoint_return']) and r['endpoint_return']>-1 and r['last_close']>0 and math.isfinite(r['last_close']) and math.isclose(r['endpoint_return'],r['forecast'][-1]/r['last_close']-1,rel_tol=1e-8,abs_tol=1e-10) and len(r['forecast'])==5 and all(math.isfinite(v) and v>0 for v in r['forecast'])]
        if not good:return fallback
        values=[r['endpoint_return'] for r in good]
        return f"Fincept ARIMA（截至{d["data_cutoff"][5:]}）｜{len(good)}/{len(expected)}標的：各股5日情景{min(values):+.2%}至{max(values):+.2%}；非區間保證／期權入場訊號。"
    except (OSError,ValueError,KeyError,TypeError,OverflowError,IndexError,AttributeError):return fallback
