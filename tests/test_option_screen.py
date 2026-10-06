import unittest
from datetime import datetime

from agents.screening_agent import HKT, ScreeningAgent


RULES = {
    "delta_max": 0.10,
    "expiry_days": list(range(21, 46)),
    "expiry_tolerance": 0,
    "max_spread_pct": 0.30,
    "min_volume": 1,
    "min_oi": 100,
    "max_margin_premium_multiple": 10.0,
    "max_quote_age_minutes": 30,
    "top_n": 10,
}


def candidate(**changes):
    row = {
        "underlying": "HK.00700",
        "option_code": "HK.TESTP",
        "option_type": "PUT",
        "dte": 30,
        "delta": -0.10,
        "iv": 30.0,
        "bid": 2.0,
        "ask": 2.2,
        "volume": 1,
        "open_interest": 100,
        "lot_size": 1000,
        "short_required_im": 20_000,
        "strike": 85,
        "spot": 100,
        "quote_time": datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S"),
    }
    row.update(changes)
    return row


class ScreeningAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = ScreeningAgent(RULES)

    def test_contract_at_rule_boundaries_passes(self):
        result = self.agent.screen([candidate()])
        self.assertEqual(len(result), 1)
        self.assertIn("score", result[0])

    def test_pre_margin_pass_does_not_bypass_final_margin_gate(self):
        prequalified = self.agent.screen([candidate(short_required_im=None)], check_margin=False)
        self.assertEqual(len(prequalified), 1)
        self.assertEqual(self.agent.screen(prequalified), [])

    def test_hard_rules_reject_bad_contracts(self):
        cases = [
            candidate(dte=20),
            candidate(delta=-0.101),
            candidate(iv=float("nan")),
            candidate(ask=3.0),
            candidate(open_interest=99),
            candidate(short_required_im=20_001),
            candidate(quote_time="2026-10-06 09:00:00"),
            candidate(strike=101),  # A short put strike must be below spot.
            candidate(option_type="CALL", strike=99),  # Call strike must be above spot.
        ]
        for row in cases:
            with self.subTest(row=row):
                self.assertEqual(self.agent.screen([row]), [])

    def test_call_with_otm_strike_passes(self):
        result = self.agent.screen([candidate(option_type="CALL", strike=115, delta=0.08)])
        self.assertEqual(len(result), 1)

    def test_stock_signal_gate_only_keeps_matching_option_side(self):
        put = candidate()
        call = candidate(option_type="CALL", strike=115, delta=0.08)
        result = self.agent.screen(
            [put, call],
            allowed_option_types={"HK.00700": {"PUT"}},
        )
        self.assertEqual([row["option_type"] for row in result], ["PUT"])

    def test_neutral_stock_signal_blocks_all_options(self):
        result = self.agent.screen(
            [candidate()],
            allowed_option_types={"HK.00700": set()},
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
