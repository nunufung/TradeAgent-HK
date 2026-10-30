import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from dashboard.space.live_data import normalize_code, sanitize_quote, technical_summary, resolve_quote
from dashboard.space.server import create_app, require_owner


@pytest.fixture(autouse=True)
def connector_signing_key(monkeypatch):
    monkeypatch.setenv('CONNECTOR_SIGNING_KEY','TEST_ONLY_CONNECTOR_SIGNING_KEY')


def packet(source='Futu OpenD', code='HK.00700'):
    now = datetime.now(timezone.utc).isoformat()
    return {'code': code, 'name': 'Tencent', 'source': source, 'price': 500,
            'previous_close': 490, 'currency': 'HKD', 'quote_at': now,
            'retrieved_at': now, 'candles': [{'date': f'2026-09-{i:02d}', 'close': 470+i} for i in range(1, 26)]}


@pytest.mark.parametrize('raw', ['700', '0700', 'HK.00700', '0700.HK'])
def test_normalize_hk_code(raw):
    assert normalize_code(raw) == 'HK.00700'


@pytest.mark.parametrize('raw', ['0', '100000', '../700', '700;sh', 'https://evil/700', '700abc'])
def test_reject_invalid_codes(raw):
    with pytest.raises(ValueError): normalize_code(raw)


def test_sanitization_drops_account_data_and_rejects_wrong_symbol_or_future_quote():
    raw = {**packet(), 'account_id': 'PRIVATE', 'token': 'SECRET'}
    result = sanitize_quote(raw, 'HK.00700')
    assert 'PRIVATE' not in str(result) and 'SECRET' not in str(result)
    assert result['price'] == 500
    with pytest.raises(ValueError): sanitize_quote(raw, 'HK.00005')
    raw['quote_at'] = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    with pytest.raises(ValueError): sanitize_quote(raw, 'HK.00700')


def test_source_resolution_prefers_futu_only_for_owner_and_falls_back_on_failure():
    class Bridge:
        async def quote(self, code): return packet()
    async def public(code): return packet('Yahoo Finance')
    assert asyncio.run(resolve_quote('700', Bridge(), private=True, public=public))['source'] == 'Futu OpenD'
    assert asyncio.run(resolve_quote('700', Bridge(), private=False, public=public))['source'] == 'Yahoo Finance'
    class Offline:
        async def quote(self, code): raise TimeoutError()
    result = asyncio.run(resolve_quote('700', Offline(), private=True, public=public))
    assert result['source'] == 'Yahoo Finance'
    assert result['fallback_reason']


def test_stale_futu_falls_back_and_unavailable_public_is_not_fabricated():
    class Old:
        async def quote(self, code):
            p=packet(); p['quote_at']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat(); return p
    async def public(code): return packet('Yahoo Finance')
    assert asyncio.run(resolve_quote('700', Old(), private=True, public=public))['source'] == 'Yahoo Finance'
    async def failed(code): raise RuntimeError('provider down')
    with pytest.raises(RuntimeError): asyncio.run(resolve_quote('700', Old(), private=True, public=failed))


def test_technical_summary_is_calculated_and_missing_history_is_explicit():
    s=technical_summary(packet())
    assert s['change_pct'] == pytest.approx(1000/490)
    assert s['sma20'] == pytest.approx(485.5)
    assert technical_summary({**packet(), 'candles': []})['sma20'] is None


def test_private_routes_require_owner_and_static_path_cannot_leak_server_code():
    client=TestClient(create_app())
    assert client.post('/api/device/code', headers={'X-TradeAgent-Request':'1'}).status_code == 401
    assert client.post('/api/research', json={'packet_id':'x'}, headers={'X-TradeAgent-Request':'1'}).status_code == 401
    assert client.get('/api/device/poll').status_code == 401
    assert client.get('/server.py').status_code == 404
    assert client.get('/research_runner.py').status_code == 404


def test_pairing_is_single_use_device_cannot_submit_unsolicited_quotes():
    app=create_app(); app.dependency_overrides[require_owner]=lambda:'lewisf'
    client=TestClient(app)
    headers={'X-TradeAgent-Request':'1'}
    code=client.post('/api/device/code',headers=headers).json()['code']
    paired=client.post('/api/device/pair',json={'code':code})
    assert paired.status_code==200
    assert client.post('/api/device/pair',json={'code':code}).status_code==401
    token=paired.json()['token']
    assert client.post('/api/device/result',json={'job_id':'invented','packet':packet()},headers={'Authorization':'Bearer '+token}).status_code==404


def test_public_lookup_returns_actual_provider_and_no_paid_research():
    client=TestClient(create_app())
    async def resolve(*args, **kwargs): return {**packet('Yahoo Finance'), 'fallback_reason':'Futu offline'}
    with patch('dashboard.space.server.resolve_quote',resolve):
        response=client.post('/api/lookup',json={'code':'700'},headers={'X-TradeAgent-Request':'1'})
    assert response.status_code==200
    assert response.json()['quote']['source']=='Yahoo Finance'
    assert response.json()['research_available'] is False
    assert response.json()['technical']['sma20']==485.5


def test_yahoo_accepts_datetime_metadata_without_losing_quote_time():
    import pandas as pd
    from dashboard.space.live_data import _fetch_yahoo
    at=pd.Timestamp.now(tz='UTC').floor('s')
    history=pd.DataFrame({'Close':[500], 'Volume':[100]},index=pd.DatetimeIndex([at]))
    class Ticker:
        def history(self,**kwargs): return history
        def get_history_metadata(self): return {'regularMarketTime':at,'regularMarketPrice':500}
    with patch('yfinance.Ticker',return_value=Ticker()):
        assert datetime.fromisoformat(_fetch_yahoo('HK.00700')['quote_at'])==at.to_pydatetime()


def test_real_private_bridge_roundtrip_and_public_session_isolation():
    import base64
    import httpx
    import json
    import time
    from itsdangerous import TimestampSigner
    async def run():
        with patch.dict('os.environ',{'OAUTH_CLIENT_SECRET':'TEST_SESSION_SIGNER'}): app=create_app()
        app.dependency_overrides[require_owner]=lambda:'lewisf'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://testserver') as client:
            headers={'X-TradeAgent-Request':'1'}
            code=(await client.post('/api/device/code',headers=headers)).json()['code']
            token=(await client.post('/api/device/pair',json={'code':code})).json()['token']
            device={'Authorization':'Bearer '+token}
            await client.get('/api/device/poll',headers=device)
            cookie=TimestampSigner('TEST_SESSION_SIGNER').sign(base64.b64encode(json.dumps({'owner':'lewisf'}).encode())).decode()
            lookup=asyncio.create_task(client.post('/api/lookup',json={'code':'700'},headers={**headers,'Cookie':'tahk_session='+cookie}))
            for _ in range(50):
                job=(await client.get('/api/device/poll',headers=device)).json()
                if job['job_id']: break
                await asyncio.sleep(.005)
            assert job['code']=='HK.00700'
            p={**packet(),'account_id':'PRIVATE_ACCOUNT'}
            delivered=await client.post('/api/device/result',headers=device,json={'job_id':job['job_id'],'packet':p})
            assert delivered.status_code==200
            response=await lookup
            assert response.json()['quote']['source']=='Futu OpenD'
            assert 'PRIVATE_ACCOUNT' not in response.text
            async def public(code): return packet('Yahoo Finance')
            with patch('dashboard.space.live_data.public_quote',public):
                public_result=await client.post('/api/lookup',json={'code':'700'},headers=headers)
            assert public_result.json()['quote']['source']=='Yahoo Finance'
    asyncio.run(run())


def test_cached_public_packet_keeps_actual_retrieval_time():
    p=packet('Yahoo Finance')
    p['quote_at']=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
    p['retrieved_at']=(datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat()
    assert sanitize_quote(p,'HK.00700')['retrieved_at']==p['retrieved_at']


def test_paired_device_survives_restart_but_expired_or_tampered_tokens_fail():
    app=create_app(); app.dependency_overrides[require_owner]=lambda:'lewisf'
    client=TestClient(app)
    code=client.post('/api/device/code',headers={'X-TradeAgent-Request':'1'}).json()['code']
    token=client.post('/api/device/pair',json={'code':code}).json()['token']
    restarted=TestClient(create_app())
    assert restarted.get('/api/device/poll',headers={'Authorization':'Bearer '+token}).status_code==200
    assert restarted.get('/api/device/poll',headers={'Authorization':'Bearer '+token+'x'}).status_code==401
    import time
    with patch('dashboard.space.server.time.time',return_value=time.time()+31*86400):
        assert restarted.get('/api/device/poll',headers={'Authorization':'Bearer '+token}).status_code==401


def test_public_timeout_covers_waiting_for_provider_capacity(monkeypatch):
    import time
    from dashboard.space import live_data
    monkeypatch.setattr(live_data,'PUBLIC_TIMEOUT_SECONDS',.01,raising=False)
    async def run():
        lock=asyncio.Semaphore(0)
        monkeypatch.setattr(live_data,'_public_lock',lock)
        live_data._cache.clear()
        start=time.monotonic()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(live_data.public_quote('HK.00700'),timeout=.2)
        assert time.monotonic()-start<.1
    asyncio.run(run())
