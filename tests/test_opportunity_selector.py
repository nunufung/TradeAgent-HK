"""Deterministic unit tests; fixtures are synthetic and not trade recommendations."""
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import unittest

from agents.opportunity_selector import evaluate, generate

NOW=datetime(2026,10,26,10,30,tzinfo=ZoneInfo("Asia/Hong_Kong"))

def fixture(**changes):
    d={"underlying":"0005","strategy":"CASH_SECURED_PUT","option_type":"PUT",
       "strike":90,"spot":100,"expiry":"2026-11-23","dte":28,"delta":-0.08,
       "bid":2,"ask":2.1,"lot_size":100,"oi":500,"volume":25,
       "quote_time":"2026-10-26 10:15:00","event_risk":False,
       "assignment_reviewed":True,"account_risk_reviewed":True,
       "portfolio_risk_ok":True,"cash_secured":True,
       "buying_power_required":9000,"thesis_strength":0.8,
       "diversification_score":0.7}
    d.update(changes)
    return d

class OpportunitySelectorTest(unittest.TestCase):
    def test_legacy_margin_gate_preserved(self):
        self.assertEqual(evaluate(fixture(),NOW)["status"],"REJECTED")
    def test_approved_research_only(self):
        row=fixture(bid=10,ask=10.5,buying_power_required=8100)
        result=evaluate(row,NOW)
        self.assertEqual(result["status"],"REVIEW_REQUIRED")
        self.assertEqual(result["tier"],"A")
    def test_preopen_not_executable(self):
        row=fixture(bid=10,ask=10.5,buying_power_required=8100,
                    quote_time="2026-10-26 09:35:00")
        self.assertEqual(evaluate(row,NOW.replace(hour=9,minute=40))["status"],"CONDITIONAL")
    def test_stale_quote_rejected(self):
        self.assertEqual(evaluate(fixture(quote_time="2026-10-25 10:15:00"),NOW)["status"],"REJECTED")
    def test_unknown_event_rejected(self):
        self.assertEqual(evaluate(fixture(event_risk=None),NOW)["status"],"REJECTED")
    def test_short_call_not_allowed(self):
        row=fixture(strategy="COVERED_CALL",option_type="CALL",strike=105,covered=False)
        self.assertEqual(evaluate(row,NOW)["status"],"REJECTED")
    def test_no_chain_is_explicit(self):
        with tempfile.TemporaryDirectory() as t:
            r=generate(source=str(Path(t)/"absent.json"),destination=str(Path(t)/"out.json"),now=NOW)
            self.assertEqual(r["status"],"NO_CHAIN_DATA")
            self.assertTrue((Path(t)/"out.json").exists())

if __name__=="__main__":
    unittest.main()
