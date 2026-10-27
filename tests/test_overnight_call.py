"""Synthetic quotes verify research routing, never historical strategy returns."""
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from test_recommendations import signals

NOW = datetime(2026, 10, 7, 10, 30, tzinfo=ZoneInfo('Asia/Hong_Kong'))


def inputs(**changes):
    row = {'underlying': 'HK.00005', 'option_code': 'HK.SYNTHETIC',
           'option_type': 'CALL', 'expiry': '2026-10-21', 'spot': 100,
           'strike': 120, 'delta': 0.08, 'bid': 1, 'ask': 1.1,
           'stock_change_pct': 6, 'quote_time': NOW.isoformat(),
           'source': 'synthetic unit test', 'verified': True,
           'volume': 10, 'open_interest': 200, 'lot_size': 100,
           'initial_margin': 900, 'event_risk': False,
           'iv_reviewed': True, 'account_risk_reviewed': True,
           'assignment_reviewed': True}
    row.update(changes)
    return {'schema_version': 1, 'overnight_call': {'candidates': [row]}}


class OvernightCallTests(unittest.TestCase):
    def build(self, data=None, now=NOW):
        import overnight_call
        return overnight_call.build(data or {}, now=now)

    def test_module_exists(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('overnight_call'))

    def test_qualifying_call_has_distinct_exit_targets_and_no_dte_inheritance(self):
        result = self.build(inputs())
        self.assertEqual(result['status'], 'RESEARCH_CANDIDATE')
        self.assertFalse(result['execution_eligible'])
        row = result['candidates'][0]
        self.assertEqual(row['dte'], 14)
        self.assertEqual(row['buyback_reference_20pct'], 0.8)
        self.assertEqual(row['buyback_reference_30pct'], 0.7)
        self.assertIsNone(row['stop_loss_pct'])
        self.assertIsNone(row['time_exit_hkt'])

    def test_invalid_inputs_never_supply_candidate(self):
        changes = [{'delta': 0.10}, {'delta': -0.08}, {'delta': 0},
                   {'option_type': 'PUT'}, {'stock_change_pct': 3},
                   {'bid': float('nan')}, {'ask': 0.9}, {'ask': 1.4},
                   {'initial_margin': 1001}, {'event_risk': None},
                   {'iv_reviewed': False}, {'verified': False},
                   {'quote_time': '2026-10-06T10:30:00+08:00'},
                   {'quote_time': '2026-10-07T10:30:00'},
                   {'quote_time': '2026-10-07T10:32:00+08:00'},
                   {'expiry': '2026-10-07'}, {'option_code': 'bad\nline'},
                   {'underlying': 'not-a-ticker'}, {'lot_size': 1.5},
                   {'source': ''}, {'stock_change_pct': True}]
        for change in changes:
            with self.subTest(change=change):
                self.assertFalse(self.build(inputs(**change))['candidates'])

    def test_preopen_lunch_weekend_and_after_close_never_show_contract(self):
        for clock in [NOW.replace(hour=7), NOW.replace(hour=12),
                      NOW.replace(hour=16), NOW.replace(day=10)]:
            data = inputs(quote_time=clock.isoformat())
            self.assertEqual(self.build(data, clock)['status'], 'WAIT_SESSION')
            self.assertFalse(self.build(data, clock)['candidates'])

    def test_missing_and_malformed_manual_inputs_are_explicit(self):
        for value in [{}, {'overnight_call': None}, {'overnight_call': {'candidates': 'bad'}},
                      {'overnight_call': {'candidates': [None]}}]:
            result = self.build(value)
            self.assertFalse(result['candidates'])
            self.assertFalse(result['execution_eligible'])
            json.dumps(result, allow_nan=False)

    def test_strategy_reaches_writer_json_and_telegram_summary(self):
        from market_recommendations import write_recommendations
        from final_summary import render_final_summary
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'TAHK_RESEARCH_INPUT_JSON': json.dumps(inputs()), 'TAHK_RESEARCH_INPUT_PATH': ''}):
            root = Path(directory)
            result = write_recommendations(signals(), directory=root, now=NOW)
            self.assertIn('overnight_call', result)
            self.assertEqual(result['stocks'][0]['allowed_option_types'], ['PUT'])
            self.assertEqual(result['action'], '等待')
            saved = json.loads((root/'overnight_call.json').read_text())
            self.assertFalse(saved['execution_eligible'])
            text = (root/'final_summary.txt').read_text()
            for part in ['急升隔夜Call', 'HK.SYNTHETIC', '20–30%', '止蝕', '候選']:
                self.assertIn(part, text)
            self.assertIn('急升隔夜Call', (root/'recommendations.md').read_text())
            # Compact path also preserves the new strategy and every existing module.
            long_market = {'watchlist': [{'code':'0005', 'name':'很長公司名稱'*300}]}
            compact = render_final_summary(signals(), now=NOW, market_audit=long_market,
                workflow_audit=result['trading_workflows'], overnight_audit=saved)
            self.assertLessEqual(len(compact), 1200)
            self.assertIn('急升隔夜Call', compact)
            self.assertIn('HK.SYNTHETIC', compact)
            self.assertIn('交易日誌：', compact)

    def test_morning_strategy_survives_the_single_message_telegram_transport(self):
        import daily_delivery
        from market_recommendations import write_recommendations
        morning = NOW.replace(hour=7)
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"ok":true,"result":{"message_id":123}}'
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'TAHK_RESEARCH_INPUT_JSON': '', 'TAHK_RESEARCH_INPUT_PATH': '',
                'DAILY_DELIVERY_CLAIMED': 'true', 'TELEGRAM_BOT_TOKEN': 'test',
                'TELEGRAM_CHAT_ID': 'test'}):
            root = Path(directory)
            write_recommendations(signals(), directory=root/'morning_report', now=morning)
            previous = Path.cwd()
            os.chdir(root)
            try:
                with patch('daily_delivery.datetime') as clock, patch(
                        'daily_delivery.urllib.request.urlopen', return_value=Response()) as send:
                    clock.now.return_value = morning
                    daily_delivery.main()
                    self.assertEqual(send.call_count, 1)
                    message = json.loads(send.call_args.args[0].data)['text']
                    self.assertIn('急升隔夜Call', message)
                    self.assertIn('20–30%', message)
                    self.assertIn('缺手動行情', message)
                    self.assertLessEqual(len(message), 1200)
            finally:
                os.chdir(previous)

    def test_fallback_carries_research_rule_without_fabricating_a_contract(self):
        from daily_delivery import fallback_summary
        text = fallback_summary(NOW)
        self.assertIn('急升隔夜Call', text)
        self.assertIn('20–30%', text)
        self.assertNotIn('HK.SYNTHETIC', text)
