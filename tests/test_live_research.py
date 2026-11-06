from datetime import date, datetime, timezone
import os
from unittest.mock import patch
from dashboard.space.research_runner import research


def test_existing_four_agent_roles_receive_actual_quote_and_missing_report_is_incomplete():
    seen={}
    class Graph:
        def __init__(self,**kwargs): seen.update(kwargs)
        def resolve_instrument_context(self,*args): return 'Instrument context'
        def propagate(self,ticker,day):
            seen['evidence']=self.resolve_instrument_context(ticker)
            return {'market_report':'Market evidence','fundamentals_report':'Fundamentals evidence',
                    'news_report':'News evidence','sentiment_report':'','final_trade_decision':'Hold'},'Hold'
    packet={'code':'HK.00700','source':'Futu OpenD','price':500,'quote_at':datetime.now(timezone.utc).isoformat()}
    with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'TEST_ONLY_NOT_REAL'}):
        result=research(packet,graph_factory=Graph,default_config={})
    assert set(seen['selected_analysts'])=={'market','fundamentals','news','social'}
    assert 'Futu OpenD' in seen['evidence'] and '500' in seen['evidence']
    assert result['complete'] is False
    assert result['reports']['Sentiment']==''
    assert 'TEST_ONLY_NOT_REAL' not in str(result)
    assert seen['config']['max_tool_rounds']==3


def test_early_hkt_morning_does_not_pass_a_future_date_to_upstream():
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls,tz=None):
            value=datetime(2026,10,30,20,0,tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    class FrozenDate(date):
        @classmethod
        def today(cls): return date(2026,10,30)
    class Graph:
        def __init__(self,**kwargs): pass
        def resolve_instrument_context(self,*args): return 'Instrument'
        def propagate(self,ticker,day):
            assert day=='2026-10-30'
            return {},'Hold'
    p={'code':'HK.00700','source':'Yahoo Finance','price':500,'quote_at':'2026-10-30T08:00:00Z'}
    with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'TEST_ONLY'}), \
         patch('dashboard.space.research_runner.datetime',FrozenDatetime), \
         patch('dashboard.space.research_runner.date',FrozenDate,create=True):
        research(p,graph_factory=Graph,default_config={})


def test_fcc_uses_messages_protocol_without_exposing_credentials():
    from dashboard.space.research_runner import provider_choices
    seen={}
    class Graph:
        def __init__(self,**kwargs): seen.update(kwargs)
        def resolve_instrument_context(self,*args): return 'Instrument'
        def propagate(self,*args): return {},'Hold'
    env={'FCC_BASE_URL':'https://gateway.example/v1','FCC_API_KEY':'TEST_PRIVATE',
         'FCC_MODEL':'groq/test-model'}
    packet={'code':'HK.00700','source':'Yahoo','quote_at':'2026-11-06'}
    with patch.dict(os.environ,env,clear=True):
        result=research(packet,provider='fcc',graph_factory=Graph,default_config={})
        assert os.environ['ANTHROPIC_API_KEY']=='TEST_PRIVATE'
        assert 'OPENAI_API_KEY' not in os.environ
        assert seen['config']['llm_provider']=='anthropic'
        assert seen['config']['backend_url']=='https://gateway.example'
        assert seen['config']['deep_think_llm']=='groq/test-model'
        assert result['provider']=='fcc'
        assert 'TEST_PRIVATE' not in str(result)+str(provider_choices())


def test_provider_selection_fails_closed():
    import pytest
    from dashboard.space.research_runner import provider_config
    with patch.dict(os.environ,{},clear=True):
        for provider in ['fcc','unknown','deepseek']:
            with pytest.raises(ValueError): provider_config(provider)
    for base in ['http://gateway.example','https://user:pass@gateway.example',
                 'https://gateway.example?token=x','https://gateway.example/v1/messages']:
        with patch.dict(os.environ,{'FCC_BASE_URL':base,'FCC_API_KEY':'TEST',
                                   'FCC_MODEL':'test'},clear=True):
            with pytest.raises(ValueError): provider_config('fcc')
