from datetime import date, datetime, timezone
from tradeagent.config import load_rules
from tradeagent.models import StockSnapshot, OptionContract
from tradeagent.engine.rules import evaluate_option


def stock(trend="bullish"):
    return StockSnapshot("0700.HK", 450, 445, .02, .05, 440, 430, 60, 1000, 900, 8.0, trend, datetime.now(timezone.utc))


def contract(**kw):
    base = dict(symbol="0700.HK", option_type="PUT", strike=400, expiry=date(2026,11,4), bid=2.0, ask=2.1, delta=-0.08, iv=.3, volume=100, open_interest=500, margin=1500, lot_size=100, source="test")
    base.update(kw)
    return OptionContract(**base)


def test_put_delta_uses_absolute_value():
    r = evaluate_option(contract(delta=-0.08), stock(), load_rules(), date(2026,10,5))
    assert r.action == "DO"


def test_reject_short_dte():
    r = evaluate_option(contract(expiry=date(2026,10,10)), stock(), load_rules(), date(2026,10,5))
    assert r.action == "REJECT"


def test_reject_margin_ratio_over_10x():
    r = evaluate_option(contract(margin=25000), stock(), load_rules(), date(2026,10,5))
    assert r.action == "REJECT"


def test_wait_when_margin_missing():
    r = evaluate_option(contract(margin=None), stock(), load_rules(), date(2026,10,5))
    assert r.action == "WAIT"


def test_reject_short_put_in_bearish_trend():
    r = evaluate_option(contract(), stock("bearish"), load_rules(), date(2026,10,5))
    assert r.action == "REJECT"
