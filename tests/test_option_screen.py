import unittest
from datetime import datetime

from main import HKT, Rules, _fresh_quote_time, evaluate_option


def candidate(**changes):
    row = {
        "dte": 30,
        "delta": -0.10,
        "bid": 2.0,
        "ask": 2.2,
        "volume": 1,
        "open_interest": 100,
        "lot_size": 1000,
        "short_required_im": 20_000,
    }
    row.update(changes)
    return row


class OptionScreenTests(unittest.TestCase):
    def test_contract_at_rule_boundaries_passes(self):
        self.assertEqual(evaluate_option(candidate()), (True, []))

    def test_missing_delta_or_margin_fails_closed(self):
        ok, reasons = evaluate_option(candidate(delta=float("nan")))
        self.assertFalse(ok)
        self.assertTrue(any("Delta" in reason for reason in reasons))
        ok, reasons = evaluate_option(candidate(short_required_im=None))
        self.assertFalse(ok)
        self.assertTrue(any("保證金" in reason for reason in reasons))

    def test_hard_risk_limits_reject(self):
        rules = Rules()
        for row in (
            candidate(dte=20),
            candidate(delta=-0.101),
            candidate(ask=3.0),
            candidate(open_interest=99),
            candidate(short_required_im=20_001),
        ):
            self.assertFalse(evaluate_option(row, rules)[0], row)

    def test_cached_quotes_fail_freshness_check(self):
        now = datetime(2026, 10, 6, 10, 10, tzinfo=HKT)
        self.assertTrue(_fresh_quote_time("2026-10-06 10:00:00", now))
        self.assertFalse(_fresh_quote_time("2026-10-06 09:39:00", now))
        self.assertFalse(_fresh_quote_time("", now))


if __name__ == "__main__":
    unittest.main()
