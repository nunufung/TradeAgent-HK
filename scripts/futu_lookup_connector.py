"""Outbound-only market-data connector. Never opens a trade context."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import getpass
import json
import math
import os
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

HKT=ZoneInfo('Asia/Hong_Kong')
ENDPOINT='https://lewisf-tradeagent-hk-dashboard.hf.space'
CONFIG=Path.home()/'.config/tradeagent-hk/futu-connector.json'
HISTORY={}


def normalize(raw):
    m=re.fullmatch(r'(?:HK\.)?([0-9]{1,5})(?:\.HK)?',str(raw).strip().upper())
    if not m or not 1<=int(m[1])<=99999: raise ValueError('Invalid HK stock code')
    return f'HK.{int(m[1]):05d}'


def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError): return None


def collect_quote(raw, *, factory=None):
    code=normalize(raw)
    if factory is None:
        from futu import OpenQuoteContext
        factory=OpenQuoteContext
    context=factory(host='127.0.0.1',port=11111)
    try:
        ret,frame=context.get_market_snapshot([code])
        if ret!=0 or frame.empty: raise RuntimeError('OpenD quote unavailable')
        row=frame.iloc[0]
        if str(row.get('code',''))!=code: raise RuntimeError('OpenD returned wrong stock')
        at=datetime.fromisoformat(str(row.get('update_time','')))
        if at.tzinfo is None: at=at.replace(tzinfo=HKT)
        state='UNKNOWN'
        ret,market=context.get_market_state([code])
        if ret==0 and not market.empty: state=str(market.iloc[0].get('market_state','UNKNOWN'))
        cached=HISTORY.get(code)
        candles=cached[1] if cached and time.monotonic()-cached[0]<3600 else []
        if not candles:
            ret,daily,_=context.request_history_kline(code=code,start=(datetime.now(HKT)-timedelta(days=210)).date().isoformat(),max_count=150)
            if ret==0:
                candles=[{'date':str(item.get('time_key',''))[:10],'close':number(item.get('close')),'volume':number(item.get('volume'))}
                         for _,item in daily.iterrows() if number(item.get('close')) is not None]
                HISTORY[code]=(time.monotonic(),candles)
        return {'code':code,'name':str(row.get('name',code))[:100],'source':'Futu OpenD',
                'price':number(row.get('last_price')),'previous_close':number(row.get('prev_close_price')),
                'quote_at':at.isoformat(),'retrieved_at':datetime.now(timezone.utc).isoformat(),
                'market_state':state,'currency':'HKD','delay_minutes':None,'candles':candles[-150:]}
    finally:
        context.close()


def save_token(token):
    CONFIG.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(CONFIG.parent,0o700)
    fd=os.open(CONFIG,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        os.fchmod(stream.fileno(),0o600)
        json.dump({'token':token},stream)


def main():
    import requests
    parser=argparse.ArgumentParser(description='Private outbound Futu quote connector; keep this terminal open.')
    parser.add_argument('--pair',action='store_true',help='Prompt securely for a new pairing code')
    args=parser.parse_args()
    token=None
    if CONFIG.exists() and not args.pair:
        token=json.loads(CONFIG.read_text()).get('token')
    with requests.Session() as session:
        if not token:
            code=getpass.getpass('Pairing code from your signed-in dashboard (hidden): ').strip()
            response=session.post(ENDPOINT+'/api/device/pair',json={'code':code},timeout=15)
            if response.status_code!=200: raise SystemExit('Pairing failed or expired. Generate a new code in the dashboard.')
            token=response.json()['token']; save_token(token)
        session.headers['Authorization']='Bearer '+token
        print('Connector running. OpenD must be signed in at 127.0.0.1:11111. Ctrl-C stops it. No GitHub runner is used.')
        while True:
            try:
                response=session.get(ENDPOINT+'/api/device/poll',timeout=15)
                if response.status_code==401:
                    raise SystemExit('Pairing expired or its signing key changed. Re-run with --pair.')
                response.raise_for_status(); job=response.json()
                if job.get('job_id'):
                    try: payload={'job_id':job['job_id'],'packet':collect_quote(job['code'])}
                    except Exception: payload={'job_id':job['job_id'],'error':True}
                    delivered=session.post(ENDPOINT+'/api/device/result',json=payload,timeout=15)
                    print('Market request handled.' if delivered.status_code==200 else 'Request expired; dashboard used public fallback.')
            except requests.RequestException:
                print('Dashboard unavailable; retrying. Public fallback remains independent of this connector.')
            time.sleep(1)


if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('\nConnector stopped.')
