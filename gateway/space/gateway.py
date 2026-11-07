"""Narrow authenticated edge for a loopback-only FCC process."""
from contextlib import asynccontextmanager
from datetime import date
import asyncio
import json
import os
import secrets

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

UPSTREAM = 'http://127.0.0.1:8082'


def create_app(*, transport=None, start_fcc=True):
    token=os.getenv('FCC_API_KEY','').strip()
    models=tuple(dict.fromkeys(x.strip() for x in os.getenv('FCC_ALLOWED_MODELS','deepseek/deepseek-chat').split(',') if x.strip()))
    if len(token)<32 or not models:
        raise RuntimeError('Set a strong FCC_API_KEY and FCC_ALLOWED_MODELS')
    slots=asyncio.Semaphore(2)
    daily={'day':date.today(),'count':0}

    @asynccontextmanager
    async def lifespan(app):
        child=None
        try:
            if start_fcc:
                env={**os.environ,'HOST':'127.0.0.1','PORT':'8082','FCC_OPEN_BROWSER':'false',
                     'PROXY_AUTH_ENABLED':'true','ANTHROPIC_AUTH_TOKEN':token,'MODEL':models[0],
                     'MESSAGING_PLATFORM':'none','LOG_LEVEL':'WARNING',
                     'LOG_RAW_API_PAYLOADS':'false','LOG_RAW_SSE_EVENTS':'false',
                     'LOG_API_ERROR_TRACEBACKS':'false'}
                child=await asyncio.create_subprocess_exec('fcc-server',env=env,
                    stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            async with httpx.AsyncClient(base_url=UPSTREAM,transport=transport,
                    timeout=httpx.Timeout(120,connect=5),follow_redirects=False) as client:
                app.state.client=client
                yield
        finally:
            if child and child.returncode is None:
                child.terminate()
                try: await asyncio.wait_for(child.wait(),10)
                except asyncio.TimeoutError: child.kill(); await child.wait()

    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

    @app.middleware('http')
    async def headers(request,call_next):
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    def authenticate(request):
        supplied=request.headers.get('authorization','').removeprefix('Bearer ')
        # ChatAnthropic sends x-api-key rather than Authorization by default.
        supplied=supplied or request.headers.get('x-api-key','')
        if not secrets.compare_digest(supplied.encode(),token.encode()):
            raise HTTPException(401,'Authentication required')

    @app.get('/health')
    async def health():
        try:
            response=await app.state.client.get('/health')
            ready=response.status_code==200
        except httpx.HTTPError: ready=False
        return JSONResponse({'status':'ready' if ready else 'starting'},status_code=200 if ready else 503)

    @app.get('/v1/models')
    async def catalog(request: Request):
        authenticate(request)
        return {'object':'list','data':[{'id':model,'object':'model'} for model in models]}

    @app.post('/v1/messages')
    @app.post('/v1/messages/count_tokens')
    async def messages(request: Request):
        authenticate(request)
        # Bound actual received bytes, including chunked requests.
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>1048576: raise HTTPException(413,'Request too large')
        try: body=json.loads(raw)
        except (ValueError,UnicodeDecodeError): raise HTTPException(400,'Invalid JSON') from None
        if not isinstance(body,dict) or body.get('model') not in models:
            raise HTTPException(422,'Select a configured model')
        if 'max_tokens' in body and (type(body['max_tokens']) is not int or not 1<=body['max_tokens']<=4096):
            raise HTTPException(422,'max_tokens must be between 1 and 4096')
        if slots.locked(): raise HTTPException(429,'Gateway busy')
        if daily['day']!=date.today(): daily.update(day=date.today(),count=0)
        if daily['count']>=200: raise HTTPException(429,'Daily request limit reached')
        daily['count']+=1
        await slots.acquire()
        try:
            forwarded={'x-api-key':token,'anthropic-version':'2023-06-01','content-type':'application/json'}
            upstream=await app.state.client.send(app.state.client.build_request('POST',request.url.path,
                        content=bytes(raw),headers=forwarded),stream=True)
            if upstream.status_code>=300:
                status=upstream.status_code if upstream.status_code in {400,422,429} else 502
                await upstream.aclose()
                slots.release()
                return JSONResponse({'error':{'type':'api_error','message':'Provider request failed; check server configuration or quota'}},status_code=status)
        except httpx.HTTPError:
            slots.release()
            raise HTTPException(502,'FCC backend unavailable') from None
        except BaseException:
            slots.release()
            raise
        async def stream():
            try:
                async for chunk in upstream.aiter_bytes(): yield chunk
            finally:
                await upstream.aclose()
                slots.release()
        return StreamingResponse(stream(),media_type='text/event-stream' if body.get('stream') else 'application/json')
    return app
