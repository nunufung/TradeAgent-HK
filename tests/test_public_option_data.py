import importlib.util
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

NOW = datetime(2026, 10, 31, 14, tzinfo=ZoneInfo('Asia/Hong_Kong'))
REPORT = '''<html><pre>
STOCK OPTIONS DAILY MARKET REPORT AS AT 30 OCT 2026
HKB HSBC HOLDINGS PLC       (00005)     13231 6436 6795 306081 122738 183343 22
CLASS HKB - HSBC HOLDINGS PLC                     CLOSING PRICE HK$ 135.700
27NOV26   120.00 P      0.00      0.00      0.00      0.25      -0.01   25         15         900           10
27NOV26   145.00 C      0.20      0.30      0.10      0.23      -0.02   22         25         800           12
30OCT26   130.00 P      0.00      0.00      0.00      0.01      -0.01   20         40         100           0
</pre></html>'''


class PublicOptionsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('public_option_data'))
        import public_option_data
        self.module = public_option_data

    def test_official_report_preserves_date_contract_and_settlement_semantics(self):
        audit = self.module.parse_report(REPORT, now=NOW)
        self.assertEqual(audit['as_of'], '2026-10-30')
        row = audit['contracts'][0]
        self.assertEqual(row['underlying'], 'HK.00005')
        self.assertEqual(row['expiry'], '2026-11-27')
        self.assertEqual(row['settlement_price'], 0.25)
        self.assertEqual(row['volume'], 15)
        self.assertEqual(row['open_interest'], 900)
        self.assertNotIn('bid', row)
        self.assertNotIn('delta', row)
        self.assertFalse(audit['execution_eligible'])

    def test_stale_future_and_wrong_document_fail_closed(self):
        for text in [REPORT.replace('30 OCT 2026', '01 OCT 2026'),
                     REPORT.replace('30 OCT 2026', '01 NOV 2026'), '<html>error</html>']:
            with self.assertRaises(ValueError):
                self.module.parse_report(text, now=NOW)

    def test_research_samples_exclude_expired_and_do_not_claim_delta_gate_passed(self):
        audit = self.module.parse_report(REPORT, now=NOW)
        lines = self.module.brief_lines(audit, now=NOW)
        text = '\n'.join(lines)
        self.assertIn('2026-11-27', text)
        self.assertIn('120', text)
        self.assertIn('145', text)
        self.assertNotIn('2026-10-30 PUT', text)
        self.assertIn('結算價', text)
        self.assertIn('非即時', text)
        self.assertIn('Delta', text)

    def test_fallback_includes_actual_option_samples_when_analysts_unavailable(self):
        from daily_delivery import fallback_summary
        audit = self.module.parse_report(REPORT, now=NOW)
        text = fallback_summary(NOW, public_option_audit=audit)
        self.assertIn('120', text)
        self.assertIn('145', text)
        self.assertIn('四分析員', text)
        self.assertIn('50–70%', text)
        self.assertLessEqual(len(text), 1200)

    def test_no_public_contracts_means_no_fabricated_sample(self):
        audit = self.module.parse_report(REPORT, now=NOW)
        audit['contracts'] = []
        self.assertIn('未取得合適合約', '\n'.join(self.module.brief_lines(audit, now=NOW)))

    def test_morning_runner_fetches_public_options_even_if_paid_research_times_out(self):
        import daily_runner
        audit = self.module.parse_report(REPORT, now=NOW)
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch('daily_runner.refresh_public_options', return_value=audit), \
                     patch('daily_runner.datetime') as clock, patch.dict(os.environ, {'DEEPSEEK_API_KEY': ''}):
                    clock.now.return_value = NOW
                    clock.combine = datetime.combine
                    daily_runner.run()
                text = Path('final_summary.txt').read_text()
                self.assertIn('結算價', text)
                self.assertIn('120', text)
                self.assertEqual(Path('daily_research_status.txt').read_text(), 'incomplete')
            finally:
                os.chdir(previous)

    def test_fetch_uses_last_completed_weekday_and_checks_embedded_date(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.read.return_value = REPORT.encode()
        with patch('public_option_data.urllib.request.urlopen', return_value=response) as get:
            audit = self.module.fetch_latest(now=NOW)
        self.assertIn('dqe261030.htm', get.call_args.args[0].full_url)
        self.assertIn('dqe261030.htm', audit['source_url'])

    def test_real_send_path_requires_and_saves_telegram_message_id(self):
        spec = importlib.util.spec_from_file_location('option_verify', Path(__file__).resolve().parents[1]/'scripts/verify-option-report.py')
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        audit = self.module.parse_report(REPORT, now=NOW)
        audit['source_url'] = 'https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/dqe261030.htm'
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch.object(verifier, 'refresh_public_options', return_value=audit), \
                     patch.object(verifier, 'datetime') as clock, \
                     patch.object(verifier, 'send_text', return_value={'ok': True, 'result': {'message_id': 123}}) as send:
                    clock.now.return_value = NOW
                    verifier.run(send=True)
                self.assertEqual(send.call_count, 1)
                self.assertIn('獨立測試', send.call_args.args[0])
                self.assertEqual(json.loads(Path('option_test_receipt.json').read_text())['message_id'], 123)
                Path('option_test_receipt.json').unlink()
                with patch.object(verifier, 'refresh_public_options', return_value=audit), \
                     patch.object(verifier, 'datetime') as clock, \
                     patch.object(verifier, 'send_text', return_value={'ok': True}) as send:
                    clock.now.return_value = NOW
                    with self.assertRaises(RuntimeError):
                        verifier.run(send=True)
                self.assertEqual(send.call_count, 1)
                self.assertFalse(Path('option_test_receipt.json').exists())
            finally:
                os.chdir(previous)

    def test_completed_research_keeps_public_contracts_in_final_summary(self):
        from final_summary import render_final_summary
        from market_recommendations import build_recommendations
        from trading_workflows import build_workflows
        from test_recommendations import signals
        payload = signals()
        payload['date'] = NOW.date().isoformat()
        audit = self.module.parse_report(REPORT, now=NOW)
        workflows = build_workflows(payload, build_recommendations(payload, now=NOW), now=NOW)
        text = render_final_summary(payload, now=NOW, workflow_audit=workflows, public_option_audit=audit)
        self.assertIn('結算價', text)
        self.assertIn('2026-11-27', text)
        self.assertIn('Short Put', text)
        self.assertLessEqual(len(text), 1200)

