"""Dashboard, public fallback and owner-only Futu/research API."""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import time
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field

try:
    from .live_data import normalize_code, resolve_quote, sanitize_quote, technical_summary
except ImportError:
    from live_data import normalize_code, resolve_quote, sanitize_quote, technical_summary

ROOT = Path(__file__).resolve().parent
OWNER = 'lewisf'
RESEARCH_ENV=Path.home()/'.cache/tradeagent-hk-research'


async def research_python():
    python=RESEARCH_ENV/'bin/python'
    ready=RESEARCH_ENV/'.ready-v06'
    if python.is_file() and ready.is_file(): return str(python)
    uv=shutil.which('uv')
    if not uv: raise RuntimeError('Research environment manager unavailable')
    for args in [(uv,'venv','--python','3.11',str(RESEARCH_ENV)),
                 (uv,'pip','install','--python',str(python),'-r',str(ROOT/'research-requirements.txt'))]:
        child=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
        try: result=await asyncio.wait_for(child.wait(),timeout=240)
        except BaseException:
            child.kill(); await child.wait(); raise
        if result: raise RuntimeError('Research environment installation failed')
    ready.touch()
    return str(python)


def require_owner(request: Request):
    if request.session.get('owner') != OWNER:
        raise HTTPException(401,'請以 lewisf 登入後使用私人 Futu 或四分析員研究。')
    return OWNER


def same_origin(request: Request):
    if request.headers.get('X-TradeAgent-Request') != '1':
        raise HTTPException(403,'Invalid request')
    origin = request.headers.get('origin')
    host = os.getenv('SPACE_HOST','')
    allowed = {'https://'+host} if host else {str(request.base_url).rstrip('/')}
    if origin and origin.rstrip('/') not in allowed:
        raise HTTPException(403,'Cross-origin request rejected')


class Lookup(BaseModel):
    code: str = Field(min_length=1,max_length=28)


class Pair(BaseModel):
    code: str = Field(min_length=8,max_length=100)


class Research(BaseModel):
    packet_id: str = Field(min_length=1,max_length=100)


class DeviceResult(BaseModel):
    job_id: str = Field(min_length=1,max_length=100)
    packet: dict | None = None
    error: bool = False


class Bridge:
    def __init__(self):
        self.signing_key = os.getenv('CONNECTOR_SIGNING_KEY','')
        self.pair_hash = None
        self.pair_expiry = 0
        self.heartbeat = 0
        self.pending = {}

    @property
    def online(self):
        return bool(self.signing_key) and self.heartbeat>0 and time.monotonic()-self.heartbeat < 25

    def authenticate(self, request):
        token = request.headers.get('Authorization','').removeprefix('Bearer ')
        try:
            nonce,expires,signature=token.split('.')
            message=('tahk-futu-quote-v1|'+nonce+'|'+expires).encode()
            valid=self.signing_key and int(expires)>time.time() and secrets.compare_digest(
                signature,hmac.new(self.signing_key.encode(),message,hashlib.sha256).hexdigest())
        except (ValueError,TypeError): valid=False
        if not valid:
            raise HTTPException(401,'Connector needs pairing')

    async def quote(self, code):
        if not self.online: raise RuntimeError('Futu connector offline')
        if len(self.pending) >= 3: raise RuntimeError('Connector busy')
        job = secrets.token_urlsafe(18)
        future = asyncio.get_running_loop().create_future()
        self.pending[job] = {'code':code,'future':future,'claimed':False}
        try:
            return await asyncio.wait_for(future,timeout=10)
        finally:
            self.pending.pop(job,None)


def create_app():
    app = FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(SessionMiddleware,
        secret_key=os.getenv('OAUTH_CLIENT_SECRET') or secrets.token_urlsafe(40),
        session_cookie='tahk_session',https_only=True,same_site='lax',max_age=28800)
    bridge = Bridge()
    app.state.bridge = bridge
    packets, research_jobs, research_days = {}, {}, {}
    public_requests = deque()
    pair_requests = deque()

    @app.middleware('http')
    async def privacy_headers(request, call_next):
        if request.method == 'POST':
            try: size=int(request.headers.get('content-length','-1'))
            except ValueError: size=-1
            if size < 0 or size > 65536:
                return JSONResponse({'detail':'Request too large or missing length'},status_code=413)
        response=await call_next(request)
        if request.url.path.startswith(('/api/','/auth/')):
            response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        return response

    @app.get('/health')
    async def health():
        return {'status':'ok','public_fallback':True}

    @app.get('/api/session')
    async def session(request: Request):
        owner=request.session.get('owner')==OWNER
        return {'owner':owner,'futu_connected':bridge.online if owner else False,
                'research_configured':bool(os.getenv('DEEPSEEK_API_KEY')) if owner else False,
                'login_url':'/auth/login','standalone_url':'https://'+os.environ['SPACE_HOST']+'/?view=lookup' if os.getenv('SPACE_HOST') else '/?view=lookup'}

    @app.get('/auth/login')
    async def login(request: Request):
        client=os.getenv('OAUTH_CLIENT_ID'); host=os.getenv('SPACE_HOST')
        if not client or not host:
            raise HTTPException(503,'Hugging Face owner sign-in is not configured yet.')
        state=secrets.token_urlsafe(32)
        request.session['oauth_state']=state
        return RedirectResponse('https://huggingface.co/oauth/authorize?'+urlencode({
            'client_id':client,'redirect_uri':'https://'+host+'/auth/callback',
            'scope':'openid profile','state':state,'response_type':'code'}))

    @app.get('/auth/callback')
    async def callback(request: Request, code: str='', state: str=''):
        expected=request.session.pop('oauth_state','')
        if not expected or not secrets.compare_digest(expected,state):
            raise HTTPException(403,'Sign-in state expired; please retry.')
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response=await client.post('https://huggingface.co/oauth/token',
                    data={'grant_type':'authorization_code','code':code,'client_id':os.environ['OAUTH_CLIENT_ID'],
                          'redirect_uri':'https://'+os.environ['SPACE_HOST']+'/auth/callback'},
                    auth=(os.environ['OAUTH_CLIENT_ID'],os.environ['OAUTH_CLIENT_SECRET']))
                response.raise_for_status()
                token=response.json()['access_token']
                profile=await client.get('https://huggingface.co/oauth/userinfo',headers={'Authorization':'Bearer '+token})
                profile.raise_for_status()
                username=profile.json().get('preferred_username')
        except (httpx.HTTPError,KeyError,ValueError):
            raise HTTPException(502,'Hugging Face sign-in failed; please retry.') from None
        if username != OWNER: raise HTTPException(403,'This private connection belongs to lewisf.')
        request.session.clear(); request.session['owner']=OWNER
        return RedirectResponse('/?view=lookup',status_code=303)

    @app.post('/api/lookup',dependencies=[Depends(same_origin)])
    async def lookup(body: Lookup,request: Request):
        try: code=normalize_code(body.code)
        except ValueError as exc: raise HTTPException(422,str(exc)) from None
        now=time.monotonic()
        while public_requests and now-public_requests[0]>60: public_requests.popleft()
        if len(public_requests)>=30: raise HTTPException(429,'查詢較頻密，請稍後重試。')
        public_requests.append(now)
        owner=request.session.get('owner')==OWNER
        try: quote=await resolve_quote(code,bridge,private=owner)
        except Exception:
            raise HTTPException(503,'Futu 及公開行情暫時無法提供可核實價格。請稍後重試；未顯示模擬行情。') from None
        expired=[key for key,item in packets.items() if now-item['created']>900]
        for key in expired: packets.pop(key,None)
        if len(packets)>=200: packets.pop(next(iter(packets)))
        packet_id=secrets.token_urlsafe(24)
        packets[packet_id]={'quote':quote,'owner':OWNER if owner else None,'created':now}
        return {'packet_id':packet_id,'quote':quote,'technical':technical_summary(quote),
                'research_available':owner and bool(os.getenv('DEEPSEEK_API_KEY')),
                'research_note':'登入 lewisf 可執行四分析員；下方技術評論為計算結果，並非四分析員研究。' if not owner else '四分析員將另行顯示實際完成狀態。'}

    @app.post('/api/device/code',dependencies=[Depends(same_origin)])
    async def pair_code(owner=Depends(require_owner)):
        code=secrets.token_urlsafe(18)
        bridge.pair_hash=hashlib.sha256(code.encode()).hexdigest()
        bridge.pair_expiry=time.monotonic()+300
        return {'code':code,'expires_seconds':300}

    @app.post('/api/device/pair')
    async def pair(body: Pair):
        if not bridge.signing_key: raise HTTPException(503,'Connector signing credential is not configured.')
        now=time.monotonic()
        while pair_requests and now-pair_requests[0]>60: pair_requests.popleft()
        if len(pair_requests)>=10: raise HTTPException(429,'Too many pairing attempts')
        pair_requests.append(now)
        digest=hashlib.sha256(body.code.encode()).hexdigest()
        if not bridge.pair_hash or now>bridge.pair_expiry or not secrets.compare_digest(digest,bridge.pair_hash):
            raise HTTPException(401,'Pairing code invalid or expired')
        bridge.pair_hash=None
        nonce=secrets.token_urlsafe(24); expires=str(int(time.time())+30*86400)
        signature=hmac.new(bridge.signing_key.encode(),('tahk-futu-quote-v1|'+nonce+'|'+expires).encode(),hashlib.sha256).hexdigest()
        token=nonce+'.'+expires+'.'+signature
        bridge.heartbeat=0
        return {'token':token,'expires_seconds':30*86400}

    @app.get('/api/device/poll')
    async def poll(request: Request):
        bridge.authenticate(request); bridge.heartbeat=time.monotonic()
        for job,item in bridge.pending.items():
            if not item['claimed']:
                item['claimed']=True
                return {'job_id':job,'code':item['code']}
        return {'job_id':None}

    @app.post('/api/device/result')
    async def device_result(body: DeviceResult,request: Request):
        bridge.authenticate(request)
        item=bridge.pending.get(body.job_id)
        if not item or not item['claimed'] or item['future'].done(): raise HTTPException(404,'Quote job expired')
        if body.error:
            item['future'].set_exception(RuntimeError('OpenD quote unavailable'))
        else:
            try:
                packet=sanitize_quote(body.packet or {},item['code']); packet['source']='Futu OpenD'
            except (ValueError,TypeError): raise HTTPException(422,'Invalid Futu market packet') from None
            item['future'].set_result(packet)
        return {'accepted':True}

    async def run_research(job_id, quote):
        job=research_jobs[job_id]; job['state']='PREPARING'
        process=None
        try:
            python=await research_python()
            job['state']='RUNNING'
            process=await asyncio.create_subprocess_exec(python,str(ROOT/'research_runner.py'),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            output,_=await asyncio.wait_for(process.communicate(json.dumps(quote).encode()),timeout=600)
            if process.returncode or len(output)>150000: raise RuntimeError('Research unavailable')
            result=json.loads(output)
            if not isinstance(result.get('reports'),dict): raise ValueError('Invalid research')
            job.update(state='COMPLETED',result=result,completed=time.monotonic())
        except Exception:
            if process and process.returncode is None:
                process.kill(); await process.wait()
            job.update(state='FAILED',error='四分析員未完成；請檢查 DeepSeek 設定、額度或資料供應。未以技術評論冒充研究。')

    @app.post('/api/research',dependencies=[Depends(same_origin)])
    async def research(body: Research,owner=Depends(require_owner)):
        if not os.getenv('DEEPSEEK_API_KEY'): raise HTTPException(503,'DeepSeek backend credential is not configured.')
        item=packets.get(body.packet_id)
        if not item or item['owner']!=owner or time.monotonic()-item['created']>900:
            raise HTTPException(404,'Lookup expired; retrieve a new quote first.')
        quote=item['quote']
        for key,job in research_jobs.items():
            if job['state'] in {'QUEUED','PREPARING','RUNNING'}:
                if job['code']==quote['code']: return {'job_id':key,'state':job['state']}
                raise HTTPException(429,'已有一項四分析員研究進行中，請稍後再試。')
            if job['code']==quote['code'] and job['state']=='COMPLETED' and time.monotonic()-job.get('completed',job['created'])<600:
                return {'job_id':key,'state':job['state']}
        today=datetime.now(timezone.utc).date().isoformat()
        count=research_days.get(today,0)
        if count>=6: raise HTTPException(429,'今日即席研究已達6次上限；仍可查閱行情及技術評論。')
        research_days.clear(); research_days[today]=count+1
        if len(research_jobs)>=20: research_jobs.pop(next(iter(research_jobs)))
        key=secrets.token_urlsafe(24)
        research_jobs[key]={'state':'QUEUED','code':quote['code'],'created':time.monotonic()}
        task=asyncio.create_task(run_research(key,quote))
        app.state.tasks.add(task); task.add_done_callback(app.state.tasks.discard)
        return {'job_id':key,'state':'QUEUED'}

    @app.get('/api/research/{job_id}')
    async def research_result(job_id: str,owner=Depends(require_owner)):
        item=research_jobs.get(job_id)
        if not item: raise HTTPException(404,'Research job expired')
        return {key:value for key,value in item.items() if key not in {'created','completed'}}

    app.state.tasks=set()
    @app.get('/')
    async def index(): return FileResponse(ROOT/'index.html')
    app.mount('/assets',StaticFiles(directory=ROOT/'assets'),name='assets')
    # Only the existing sanitized snapshot is public; never mount the source tree.
    @app.get('/data/dashboard.json')
    async def snapshot(): return FileResponse(ROOT/'data/dashboard.json',headers={'Cache-Control':'no-cache'})
    return app


app=create_app()
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=7860,proxy_headers=True,forwarded_allow_ips='*',access_log=False)
