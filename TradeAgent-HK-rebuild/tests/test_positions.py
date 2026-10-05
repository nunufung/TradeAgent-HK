from tradeagent.config import load_rules
from tradeagent.engine.positions import manage_short_option


def test_take_profit():
    r = manage_short_option(2.0, 0.8, 25, load_rules())
    assert r["action"] == "TAKE_PROFIT"


def test_stop_loss():
    r = manage_short_option(2.0, 4.2, 30, load_rules())
    assert r["action"] == "CLOSE_OR_ROLL"


def test_profitable_short_dte_closes_first():
    r = manage_short_option(2.0, 1.4, 15, load_rules())
    assert r["action"] == "CLOSE_PRIORITY"
