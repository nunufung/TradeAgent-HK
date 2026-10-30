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
