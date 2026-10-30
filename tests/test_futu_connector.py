from datetime import datetime, timezone
from unittest.mock import patch
import pandas as pd
import pytest
from scripts.futu_lookup_connector import collect_quote


class Quote:
    closed=False
    def get_market_snapshot(self,codes):
        return 0,pd.DataFrame([{'code':codes[0],'name':'Tencent','last_price':500,'prev_close_price':490,
            'update_time':datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S'),
            'account_id':'DO_NOT_TRANSMIT'}])
    def get_market_state(self,codes): return 0,pd.DataFrame([{'market_state':'AFTERNOON'}])
    def request_history_kline(self,**kwargs):
        return 0,pd.DataFrame([{'time_key':'2026-10-29','close':490,'volume':100}]),None
    def close(self): self.closed=True


def test_connector_only_returns_allowlisted_market_fields_and_closes_context():
    q=Quote()
    result=collect_quote('HK.00700',factory=lambda **kwargs:q)
    assert result['code']=='HK.00700' and result['price']==500
    assert result['source']=='Futu OpenD'
    assert 'DO_NOT_TRANSMIT' not in str(result)
    assert q.closed


def test_connector_raises_on_missing_quote_and_always_closes():
    q=Quote()
    q.get_market_snapshot=lambda codes:(-1,'No permission; secret detail')
    with pytest.raises(RuntimeError,match='OpenD quote unavailable'):
        collect_quote('700',factory=lambda **kwargs:q)
    assert q.closed


def test_connector_rejects_input_before_opening_opend():
    with pytest.raises(ValueError): collect_quote('../700',factory=lambda **kwargs:pytest.fail('must not connect'))
