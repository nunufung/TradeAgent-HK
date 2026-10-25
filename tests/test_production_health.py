import json
from pathlib import Path
import tempfile
import unittest
from production_health import evaluate, format_markdown


class ProductionHealthTests(unittest.TestCase):
    def fixture(self, base, *, receipt=True, research='complete'):
        for part in ('receipt', 'morning_report', 'ledger'):
            (base / part).mkdir()
        if receipt:
            (base / 'receipt' / 'delivery_receipt.json').write_text(json.dumps({
                'date': '2026-10-25', 'message_id': 91,
                'sent_at': '2026-10-25T07:17:22+08:00'}))
        (base / 'morning_report' / 'daily_research_status.txt').write_text(research)
        (base / 'ledger' / 'daily_token_usage.json').write_text(json.dumps({
            'date': '2026-10-25', 'calls': 12, 'actual_tokens': 8400,
            'prompt_tokens': 7000, 'completion_tokens': 1400,
            'cache_hit_tokens': 3000, 'unconfirmed_calls': 0}))
        return {'date': '2026-10-25', 'checked_at_utc': '2026-10-25T00:05:00Z',
                'artifacts': {'delivery_receipt': receipt, 'delivery_claim': True},
                'futu_latest': {'conclusion': 'success', 'created_at': '2026-10-24T02:00:00Z'}}

    def test_valid_receipt_and_complete_research_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = evaluate(self.fixture(base), base)
            self.assertEqual(result['overall'], 'PASS')
            self.assertEqual(result['telegram_message_id'], 91)
            self.assertEqual(result['deepseek']['actual_tokens'], 8400)
            self.assertIn('API calls: 12', format_markdown(result))

    def test_green_run_without_receipt_is_failure_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = evaluate(self.fixture(base, receipt=False), base)
            self.assertEqual(result['overall'], 'FAILED')
            self.assertEqual(result['telegram'], 'unconfirmed')
            self.assertTrue(any('do not auto-retry' in x for x in result['warnings']))

    def test_fallback_is_not_misreported_as_successful_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = evaluate(self.fixture(base, research='incomplete'), base)
            self.assertEqual(result['overall'], 'FAILED')
            self.assertEqual(result['telegram'], 'api_acknowledged')

    def test_receipt_wrong_hk_date_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manifest = self.fixture(base)
            path = base / 'receipt' / 'delivery_receipt.json'
            value = json.loads(path.read_text())
            value['sent_at'] = '2026-10-24T23:58:00+08:00'
            path.write_text(json.dumps(value))
            self.assertEqual(evaluate(manifest, base)['telegram'], 'unconfirmed')

    def test_futu_missing_is_warning_not_fabricated_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manifest = self.fixture(base)
            manifest['futu_latest'] = None
            result = evaluate(manifest, base)
            self.assertEqual(result['overall'], 'WARNING')
            self.assertEqual(result['futu_opend'], 'unverified')

    def test_stale_futu_success_does_not_count_as_connected_today(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manifest = self.fixture(base)
            manifest['futu_latest']['created_at'] = '2026-10-01T02:00:00Z'
            result = evaluate(manifest, base)
            self.assertEqual(result['futu_opend'], 'stale_smoke_test')
            self.assertEqual(result['overall'], 'WARNING')


if __name__ == '__main__':
    unittest.main()
