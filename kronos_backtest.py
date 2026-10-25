"""Fixed-parameter chronological forecast audit, not a trading strategy backtest."""
import argparse
import hashlib
import json
import random
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE='67b630e67f6a18c9e9be918d9b4337c960db1e9a'
MODELS={'NeoQuasar/Kronos-Tokenizer-base':'0e0117387f39004a9016484a186a908917e22426', 'NeoQuasar/Kronos-small':'901c26c1332695a2a8f243eb2f37243a37bea320'}

def price_order_valid(open_price, high, low, close, tolerance=1e-10):
    """Accept only sub-tick floating-point noise; never alter prices."""
    return high+tolerance >= max(open_price, close, low) and low-tolerance <= min(open_price, close, high)

def metrics(rows):
    import math
    valid=[r for r in rows if r['valid']]
    if not valid:return {'attempted':len(rows),'valid':0}
    n=len(valid)
    result={'attempted':len(rows),'valid':n,'rejected':len(rows)-n}
    for key in ['predicted','zero','trend']:
        errors=[r[key]-r['actual'] for r in valid]
        signs=[r for r in valid if r['actual']!=0]
        sign=lambda v:(v>0)-(v<0)
        result[key]={'mae':sum(abs(e) for e in errors)/n,'rmse':math.sqrt(sum(e*e for e in errors)/n),'direction_correct':sum(sign(r[key])==sign(r['actual']) for r in signs),'direction_n':len(signs)}
    result['always_up_correct']=sum(r['actual']>0 for r in valid)
    result['zero_mae_all_attempts']=sum(abs(r['actual']) for r in rows)/len(rows)
    return result

def run(args):
    import numpy as np
    import pandas as pd
    import torch
    import yfinance as yf
    import exchange_calendars as xc
    assert subprocess.check_output(['git','-C',args.source,'rev-parse','HEAD'],text=True).strip()==SOURCE
    sys.path.insert(0,str(Path(args.source).resolve()))
    from model import Kronos,KronosTokenizer,KronosPredictor
    torch.set_num_threads(2)
    random.seed(42);np.random.seed(42);torch.manual_seed(42)
    ids=list(MODELS)
    tokenizer=KronosTokenizer.from_pretrained(ids[0],revision=MODELS[ids[0]])
    model=Kronos.from_pretrained(ids[1],revision=MODELS[ids[1]])
    predictor=KronosPredictor(model,tokenizer,device='cpu',max_context=512)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone(timedelta(hours=8)))
    cal=xc.get_calendar('XHKG')
    recent=cal.sessions_in_range((now-timedelta(days=15)).date(),now.date())
    cutoff=[s for s in recent if cal.session_close(s).to_pydatetime()<now][-1]
    records=[]; hashes={}
    tickers=args.tickers or ['0700','9988']
    for ticker in tickers:
        frame=yf.Ticker(ticker+'.HK').history(period='3y',auto_adjust=True,raise_errors=True)
        frame.columns=frame.columns.str.lower();frame=frame[frame.index.date<=cutoff.date()]
        cols=['open','high','low','close','volume'];frame=frame[cols]
        assert frame.index[-1].date()==cutoff.date() and len(frame)>=520
        assert frame.index.is_unique and frame.index.is_monotonic_increasing
        assert np.isfinite(frame.to_numpy()).all() and (frame[['open','high','low','close']]>0).all().all() and (frame.volume>=0).all()
        assert all(price_order_valid(o,h,l,c) for o,h,l,c in zip(frame.open,frame.high,frame.low,frame.close)), 'OHLC ordering exceeds 1e-10 tolerance'
        raw=frame.to_csv();(out/(ticker+'-history.csv')).write_text(raw);hashes[ticker]=hashlib.sha256(raw.encode()).hexdigest()
        origins=list(range(len(frame)-120-1,len(frame)-5,5))
        assert len(origins)==24
        for batch in range(0,len(origins),4):
            positions=origins[batch:batch+4]
            histories=[];xs=[];ys=[]
            for i in positions:
                h=frame.iloc[i-399:i+1]
                target=frame.iloc[i+1:i+6]
                expected=cal.sessions_in_range(pd.Timestamp(h.index[-1].date())+pd.Timedelta(days=1),pd.Timestamp(target.index[-1].date()))
                assert list(expected.date)==list(target.index.date), 'Suspended/missing sessions'
                assert h.index[-1].date()>datetime(2026,4,13).date()
                histories.append(h.reset_index(drop=True));xs.append(pd.Series(pd.to_datetime(h.index.date)));ys.append(pd.Series(pd.to_datetime(target.index.date)))
            # No future feature values are supplied, only future session labels.
            with torch.inference_mode():
                predictions=predictor.predict_batch(histories,xs,ys,pred_len=5,T=1.,top_p=.9,top_k=0,sample_count=5,verbose=False)
            for i,p in zip(positions,predictions):
                base=float(frame.close.iloc[i]);actual=float(frame.close.iloc[i+5])/base-1
                prices=p[['open','high','low','close']]
                valid=bool(len(p)==5 and np.isfinite(p.to_numpy()).all() and (prices>0).all().all() and (p[['volume','amount']]>=0).all().all() and (p.high>=p[['open','close','low']].max(axis=1)).all() and (p.low<=p[['open','close','high']].min(axis=1)).all())
                record={'ticker':ticker,'origin':str(frame.index[i].date()),'target':str(frame.index[i+5].date()),'actual':actual,'predicted':float(p.close.iloc[-1])/base-1,'zero':0.,'trend':float(frame.close.iloc[i]/frame.close.iloc[i-20])**.25-1,'valid':valid,'candles':p.to_dict('records')}
                records.append(record)
            (out/'checkpoint.json').write_text(json.dumps(records,allow_nan=False))
            print(ticker,'completed',batch+len(positions),'of 24',flush=True)
    result={'generated_at':now.isoformat(),'source_commit':SOURCE,'models':MODELS,'parameters':{'lookback':400,'horizon':5,'sample_count':5,'seed':42,'T':1.,'top_p':.9,'top_k':0,'device':'cpu','batch_size':4},'data_source':'Yahoo Finance via yfinance; auto_adjust=True; retrieved at evaluation time, not point-in-time snapshots','data_sha256':hashes,'limitations':['Model pretraining cutoff unverified; source date alone does not establish absence of training overlap.','Fixed parameters; no fine-tuning or selection on these windows.','Five-day target intervals do not overlap within each stock; shared dates across stocks remain correlated.','Invalid candles rejected without repair; paired metrics only on valid windows, rejection rate disclosed.','No trading P/L, costs, option chains, assignment or margin model; not a strategy profitability validation.','Adjusted histories downloaded today can reflect subsequent corporate actions.'],'metrics':{t:metrics([r for r in records if r['ticker']==t]) for t in tickers},'records':records}
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps(result['metrics'],indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--tickers',nargs='+');p.add_argument('--output',default='research/kronos-backtest-2026-10-25');run(p.parse_args())
