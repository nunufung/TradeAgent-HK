"""Synthetic spread tests: no assertion represents a live HKEX quote."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from agents.vertical_spread_selector import pair, screen_verticals

NOW=datetime(2026,10,26,10,30,tzinfo=ZoneInfo("Asia/Hong_Kong"))

def leg(kind,strike,bid,ask,**kw):
    d=dict(option_type=kind,strike=strike,bid=bid,ask=ask,
           underlying="0700",expiry="2026-11-16",dte=21,lot_size=100,
           oi=600,volume=30,quote_time="2026-10-26 10:10:00",
           event_risk=False,account_risk_reviewed=True,assignment_reviewed=True,
           portfolio_risk_ok=True,account_equity=400000,
           buying_power_required=1800,broker_spread_supported=True,
           roundtrip_fees_total=20,delta=0.15,thesis_strength=1,
           diversification_score=1)
    d.update(kw)
    return d

class VerticalTest(unittest.TestCase):
    def test_bull_put_credit(self):
        s=leg("PUT",90,3,3.1); l=leg("PUT",85,1,1.1)
        r=pair(s,l,"BULL_PUT_CREDIT",NOW)
        self.assertEqual(r["tier"],"B")
        self.assertAlmostEqual(r["gross_credit_or_debit"],190)
        self.assertAlmostEqual(r["max_loss_including_fees"],330)
    def test_bear_call_credit(self):
        s=leg("CALL",105,3,3.1);l=leg("CALL",110,1,1.1)
        self.assertEqual(pair(s,l,"BEAR_CALL_CREDIT",NOW)["tier"],"B")
    def test_bull_call_debit(self):
        s=leg("CALL",105,1,1.1);l=leg("CALL",100,3,3.1)
        self.assertEqual(pair(s,l,"BULL_CALL_DEBIT",NOW)["tier"],"B")
    def test_bear_put_debit(self):
        s=leg("PUT",95,1,1.1);l=leg("PUT",100,3,3.1)
        self.assertEqual(pair(s,l,"BEAR_PUT_DEBIT",NOW)["tier"],"B")
    def test_expiry_mismatch(self):
        s=leg("PUT",90,3,3.1);l=leg("PUT",85,1,1.1,expiry="2026-11-23")
        self.assertEqual(pair(s,l,"BULL_PUT_CREDIT",NOW)["status"],"REJECTED")
    def test_unknown_event(self):
        s=leg("PUT",90,3,3.1,event_risk=None);l=leg("PUT",85,1,1.1)
        self.assertEqual(pair(s,l,"BULL_PUT_CREDIT",NOW)["status"],"REJECTED")
    def test_budget_veto(self):
        s=leg("PUT",90,3,3.1,account_equity=10000);l=leg("PUT",85,1,1.1)
        self.assertEqual(pair(s,l,"BULL_PUT_CREDIT",NOW)["status"],"REJECTED")
    def test_stale_quote(self):
        s=leg("PUT",90,3,3.1,quote_time="2026-10-25 10:10:00");l=leg("PUT",85,1,1.1)
        self.assertEqual(pair(s,l,"BULL_PUT_CREDIT",NOW)["status"],"REJECTED")
    def test_no_cross_expiry_pairing(self):
        s=leg("PUT",90,3,3.1);l=leg("PUT",85,1,1.1)
        items=screen_verticals([dict(short=s,long=l,strategy="BULL_PUT_CREDIT")],NOW)
        self.assertEqual(len(items),1)

if __name__=="__main__":unittest.main()
