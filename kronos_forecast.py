"""Optional CPU inference; never run inside the paid morning process."""
import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE = '67b630e67f6a18c9e9be918d9b4337c960db1e9a'
HKT = timezone(timedelta(hours=8))

def run(source, output):
    import numpy as np
    import pandas as pd
    import torch
    import yfinance as yf
    import exchange_calendars as xc
    from huggingface_hub import HfApi
    import subprocess
    if subprocess.check_output(['git','-C',source,'rev-parse','HEAD'],text=True).strip()!=SOURCE:
        raise ValueError('Unreviewed source revision')
    sys.path.insert(0,str(Path(source).resolve()))
    from model import Kronos, KronosTokenizer, KronosPredictor
    torch.set_num_threads(2)
    seed=42
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    ids=['NeoQuasar/Kronos-Tokenizer-base','NeoQuasar/Kronos-small']
    revisions=[HfApi().model_info(i).sha for i in ids]
    tokenizer=KronosTokenizer.from_pretrained(ids[0], revision=revisions[0])
    model=Kronos.from_pretrained(ids[1], revision=revisions[1])
    predictor=KronosPredictor(model,tokenizer,device='cpu',max_context=512)
    now=datetime.now(HKT)
    cal=xc.get_calendar('XHKG')
    # A session is available only after its official closing time.
    sessions=cal.sessions_in_range((now-timedelta(days=15)).date(),now.date())
    completed=[s for s in sessions if cal.session_close(s).to_pydatetime() < now]
    last=completed[-1]
    future=cal.sessions_in_range(last + pd.Timedelta(days=1), last + pd.Timedelta(days=20))[:5]
    if len(future)!=5: raise ValueError('Calendar horizon missing')
    forecasts=[]
    for ticker in ['0700','9988']:
        history=yf.Ticker(ticker+'.HK').history(period='2y',auto_adjust=True,raise_errors=True)
        history.columns=history.columns.str.lower()
        history=history[history.index.date<=last.date()].tail(400).copy()
        if len(history)!=400 or history.index[-1].date()!=last.date():
            raise ValueError('Missing/stale completed history for '+ticker)
        if not history.index.is_unique or not history.index.is_monotonic_increasing:
            raise ValueError('Invalid timestamp order')
        cols=['open','high','low','close','volume']
        a=history[cols]
        if not np.isfinite(a.to_numpy()).all() or (a[['open','high','low','close']]<=0).any().any() or (a.volume<0).any():
            raise ValueError('Invalid history')
        if ((a.high<a[['open','close','low']].max(axis=1)) | (a.low>a[['open','close','high']].min(axis=1))).any():
            raise ValueError('Invalid OHLC history')
        x=pd.Series(pd.to_datetime(history.index.date))
        y=pd.Series(pd.to_datetime(future.date))
        with torch.inference_mode():
            forecast=predictor.predict(df=a,x_timestamp=x,y_timestamp=y,pred_len=5,T=1.0,top_p=.9,top_k=0,sample_count=5,verbose=False)
        prices=forecast[['open','high','low','close']]
        if len(forecast)!=5 or not np.isfinite(forecast.to_numpy()).all() or (prices<=0).any().any() or (forecast[['volume','amount']]<0).any().any():
            raise ValueError('Invalid output')
        if ((prices.high<prices[['open','close','low']].max(axis=1)) | (prices.low>prices[['open','close','high']].min(axis=1))).any():
            raise ValueError('Invalid forecast candles for '+ticker+': '+prices.to_json())
        close=float(a.close.iloc[-1]); endpoint=float(forecast.close.iloc[-1])
        forecasts.append({'ticker':ticker,'status':'FORECAST_ONLY','data_cutoff':str(last.date()),'last_close':close,'endpoint':endpoint,'endpoint_return':endpoint/close-1,'sessions':[str(d.date()) for d in y],'candles':forecast.to_dict(orient='records')})
    data={'generated_at':datetime.now(HKT).isoformat(),'source_commit':SOURCE,'models':dict(zip(ids,revisions)),'provider':'Yahoo Finance via yfinance; auto_adjust=True','amount':'upstream estimated proxy from volume and mean OHLC, not observed turnover','seed':seed,'lookback':400,'horizon':5,'sample_count':5,'temperature':1.0,'top_p':.9,'device':'cpu','evaluation':'not backtested; uncalibrated mean of five sampled paths','forecasts':forecasts}
    Path(output).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False))
    from kronos_report import brief
    print(brief(Path(output)))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--source',required=True); p.add_argument('--output',default='kronos_forecast.json'); args=p.parse_args()
    run(args.source,args.output)
