"""Execute a pinned Fincept ARIMA wrapper in an isolated research process."""
import argparse,concurrent.futures,hashlib,importlib.util,json,math,warnings
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import urlopen

HKT=timezone(timedelta(hours=8))
COMMIT='3d8617cae3f13c93874d4bee4fb0f2846e9c83bc'
MODULE='fincept-qt/scripts/Analytics/statsmodels_wrapper/timeseries_models.py'
HASH='321c395b250288e2ed139989fecae0676aa7e0b076d621fde7b25c517e124785'

def prepare_module(path):
    p=Path(path)
    if not p.is_file():
        p.parent.mkdir(parents=True,exist_ok=True)
        with urlopen(f'https://raw.githubusercontent.com/Fincept-Corporation/FinceptTerminal/{COMMIT}/{MODULE}',timeout=60) as response:
            raw=response.read()
        if hashlib.sha256(raw).hexdigest()!=HASH:raise ValueError('Source hash mismatch')
        p.write_bytes(raw)
    if hashlib.sha256(p.read_bytes()).hexdigest()!=HASH:raise ValueError('Source hash mismatch')
    return str(p.resolve())

def predict(module,history):
    import numpy as np
    from statsmodels.tools.sm_exceptions import ConvergenceWarning
    values=np.asarray(history,dtype=float)
    if len(values)!=400 or not np.isfinite(values).all() or (values<=0).any():raise ValueError('Invalid 400-bar history')
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        result=module.forecast_arima(np.log(values).tolist(),order=(1,1,1),steps=5)
    if any(issubclass(w.category,ConvergenceWarning) for w in captured):raise ValueError('ARIMA did not converge')
    prices=np.exp(np.asarray(result['forecast'],dtype=float))
    if len(prices)!=5 or not np.isfinite(prices).all() or (prices<=0).any():raise ValueError('Invalid forecast')
    return prices.tolist()

def worker(task):
    import numpy as np,pandas as pd,yfinance as yf,exchange_calendars as xc
    stock,module_path,cutoff,backtest,output=task
    code=stock['code'];out=Path(output)/code;out.mkdir(parents=True,exist_ok=True)
    result={'ticker':code,'name':stock['name'],'status':'FAILED','windows':[]}
    try:
        spec=importlib.util.spec_from_file_location('fincept_ts',module_path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cal=xc.get_calendar('XHKG');last=pd.Timestamp(cutoff)
        frame=yf.Ticker(code+'.HK').history(period='3y',auto_adjust=True,raise_errors=True)
        frame.columns=frame.columns.str.lower();frame=frame[frame.index.date<=last.date()][['open','high','low','close','volume']]
        if len(frame)<520 or frame.index[-1].date()!=last.date() or not frame.index.is_unique or not frame.index.is_monotonic_increasing:raise ValueError('Insufficient/stale/duplicate history')
        if not np.isfinite(frame.to_numpy()).all() or (frame[['open','high','low','close']]<=0).any().any() or (frame.volume<0).any():raise ValueError('Invalid historical values')
        if ((frame.high+1e-10<frame[['open','close','low']].max(axis=1))|(frame.low-1e-10>frame[['open','close','high']].min(axis=1))).any():raise ValueError('Invalid historical candle order')
        raw=frame.to_csv();(out/'history.csv').write_text(raw)
        result['data_sha256']=hashlib.sha256(raw.encode()).hexdigest()
        result['retrieved_at']=datetime.now(HKT).isoformat();result['data_cutoff']=cutoff
        future=cal.sessions_in_range(last+pd.Timedelta(days=1),last+pd.Timedelta(days=20))[:5]
        if len(future)!=5:raise ValueError('Calendar horizon unavailable')
        # Treat each observation as one verified exchange session, not a calendar day.
        history=frame.iloc[-400:]
        if list(history.index.date)!=list(cal.sessions_in_range(str(history.index[0].date()),cutoff).date):raise ValueError('Missing/non-session dates in current 400-bar history')
        try:
            prices=predict(module,history.close)
            result.update(status='FORECAST_ONLY',last_close=float(frame.close.iloc[-1]),forecast=prices,sessions=[str(x.date()) for x in future],endpoint_return=prices[-1]/float(frame.close.iloc[-1])-1)
        except Exception as exc:result['forecast_error']=str(exc)
        if backtest:
            for i in range(len(frame)-121,len(frame)-5,5):
                h=frame.iloc[i-399:i+1];target=frame.iloc[i+1:i+6];base=float(frame.close.iloc[i])
                row={'ticker':code,'origin':str(frame.index[i].date()),'target':str(frame.index[i+5].date()),'actual':float(frame.close.iloc[i+5])/base-1,'zero':0.,'trend':float(frame.close.iloc[i]/frame.close.iloc[i-20])**.25-1,'valid':False,'predicted':None}
                try:
                    if list(h.index.date)!=list(cal.sessions_in_range(str(h.index[0].date()),str(h.index[-1].date())).date):raise ValueError('Missing/non-session training dates')
                    if list(target.index.date)!=list(cal.sessions_in_range(pd.Timestamp(h.index[-1].date())+pd.Timedelta(days=1),str(target.index[-1].date())).date):raise ValueError('Missing/non-session target dates')
                    p=predict(module,h.close)
                    row.update(valid=True,predicted=p[-1]/base-1)
                except Exception as exc:row['reason']=str(exc)
                result['windows'].append(row)
    except Exception as exc:result['error']=f'{type(exc).__name__}: {exc}'
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    print(code,result['status'],'valid windows',sum(r['valid'] for r in result['windows']),flush=True)
    return result

def run(args):
    import exchange_calendars as xc
    from kronos_backtest import metrics
    module=prepare_module(args.module)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    watch=json.loads(Path(args.watchlist).read_text());stocks=[s for s in watch['stocks'] if s['group']=='bluechip']
    if not stocks:raise ValueError('Empty universe')
    now=datetime.now(HKT);cal=xc.get_calendar('XHKG');sessions=cal.sessions_in_range((now-timedelta(days=15)).date(),now.date());last=[s for s in sessions if cal.session_close(s).to_pydatetime()<now][-1]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(worker,[(s,module,str(last.date()),args.backtest,str(out)) for s in stocks]))
    windows=[w for r in results for w in r['windows']]
    from importlib.metadata import version
    artifact={'dependency_versions':{name:version(name) for name in ['numpy','pandas','scipy','statsmodels','yfinance','exchange_calendars']},'schema_version':1,'generated_at':datetime.now(HKT).isoformat(),'data_cutoff':str(last.date()),'source_commit':COMMIT,'module':MODULE,'module_sha256':HASH,'provider':'Yahoo Finance via yfinance, auto_adjust=True; NOT independently certified','watchlist_sha256':hashlib.sha256(Path(args.watchlist).read_bytes()).hexdigest(),'universe':stocks,'method':'Fincept forecast_arima on log adjusted close; fixed ARIMA(1,1,1); exp(log-level point forecast), not a calibrated expected return','lookback':400,'horizon':5,'order':[1,1,1],'backtest':bool(args.backtest),'forecasts':[{k:v for k,v in r.items() if k!='windows'} for r in results],'metrics':metrics(windows) if windows else None,'stock_metrics':{s['code']:metrics([w for w in windows if w['ticker']==s['code']]) for s in stocks} if windows else None,'limitations':['Fixed parameters, no tuning on these test windows.','Re-fit separately per origin; no foundation-model pretraining.','Current watchlist and adjusted historical snapshots introduce selection and point-in-time limitations.','Same-date stocks correlated; windows not independent across stocks.','Source/provider errors and nonconvergence rejected without substitution.','Forecast validation is not a net-return or option-profit backtest.']}
    (out/'fincept_forecast.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2,allow_nan=False))
    if windows:
        import csv
        with (out/'windows.csv').open('w') as f:
            cols=['ticker','origin','target','actual','predicted','zero','trend','valid','reason'];writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader();writer.writerows(windows)
    from fincept_audit_report import render
    (out/'REPORT.md').write_text(render(artifact,windows))
    from fincept_report import brief
    print(brief(out/'fincept_forecast.json'),flush=True)
    if artifact['metrics']:print(json.dumps(artifact['metrics']),flush=True)
    if not any(r['status']=='FORECAST_ONLY' for r in results):raise RuntimeError('No valid forecasts; failure evidence saved')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--module',default='/tmp/fincept-research/timeseries_models.py');p.add_argument('--watchlist',default='market_watchlist.json');p.add_argument('--output',default='fincept-output');p.add_argument('--backtest',action='store_true');run(p.parse_args())
