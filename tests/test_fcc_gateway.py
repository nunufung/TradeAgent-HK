import os
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from gateway.space.gateway import create_app

TOKEN='test-only-'+'x'*40


def client_for(handler):
    with patch.dict(os.environ,{'FCC_API_KEY':TOKEN,'FCC_ALLOWED_MODELS':'deepseek/deepseek-chat,groq/test'},clear=True):
        return TestClient(create_app(transport=httpx.MockTransport(handler),start_fcc=False))


def test_auth_admin_and_model_allowlist():
    with client_for(lambda r:httpx.Response(200,json={'status':'healthy'})) as c:
        assert c.get('/health').status_code==200
        for path in ['/admin','/admin/api/config','/docs','/openapi.json','/stop']:
            assert c.get(path).status_code==404
        assert c.get('/v1/models').status_code==401
        headers={'x-api-key':TOKEN}
        assert len(c.get('/v1/models',headers=headers).json()['data'])==2
        assert c.post('/v1/messages',headers=headers,json={'model':'unconfigured'}).status_code==422
        assert c.post('/v1/messages',headers=headers,json={'model':'groq/test','max_tokens':99999}).status_code==422
        assert c.post('/v1/messages',headers=headers,content=b'x'*1048577).status_code==413


def test_messages_streaming_and_error_redaction():
    seen=[]
    def upstream(r):
        seen.append(r)
        assert r.headers['x-api-key']==TOKEN
        assert 'x-untrusted-header' not in r.headers
        return httpx.Response(200,content=b'data: {"type":"message_stop"}\n\n')
    with client_for(upstream) as c:
        response=c.post('/v1/messages',headers={'Authorization':'Bearer '+TOKEN,'x-untrusted-header':'bad'},
                        json={'model':'groq/test','max_tokens':50,'stream':True,'messages':[]})
        assert response.status_code==200 and response.headers['content-type'].startswith('text/event-stream')
        assert 'message_stop' in response.text
        assert seen[0].url.path=='/v1/messages'
    with client_for(lambda r:httpx.Response(500,text='PRIVATE_PROVIDER_KEY')) as c:
        response=c.post('/v1/messages',headers={'x-api-key':TOKEN},json={'model':'groq/test'})
        assert response.status_code==502 and 'PRIVATE_PROVIDER_KEY' not in response.text


def test_missing_secret_fails_closed_and_health_is_not_fake():
    import pytest
    with patch.dict(os.environ,{},clear=True):
        with pytest.raises(RuntimeError): create_app(start_fcc=False)
    with client_for(lambda r:httpx.Response(503)) as c:
        assert c.get('/health').status_code==503


def test_publisher_refuses_ineligible_account_before_writes():
    import sys
    import types
    import pytest
    from gateway.publish import main
    class Api:
        def __init__(self,**kwargs): pass
        def whoami(self): return {'name':'lewisf','isPro':False}
        def create_repo(self,**kwargs): raise AssertionError('Must not provision')
    with patch.dict(sys.modules,{'huggingface_hub':types.SimpleNamespace(HfApi=Api)}), \
         patch.dict(os.environ,{'HF_TOKEN':'TEST_ONLY'},clear=True):
        with pytest.raises(SystemExit,match='eligible paid plan'): main()
