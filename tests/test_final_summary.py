import importlib.util
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

from test_recommendations import signals

spec = importlib.util.find_spec('final_summary')
if spec:
    import final_summary as summary
else:
    summary = None
NOW = datetime(2026, 10, 7, 10, 30, tzinfo=ZoneInfo('Asia/Hong_Kong'))


class FinalSummaryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(summary, 'Short Telegram final summary is missing')

    def test_bullish_research_and_one_final_conclusion_fit_a_short_message(self):
        payload = signals()
        payload['generated_at'] = NOW.isoformat()
        market = {'watchlist': [{'code': '0005', 'name': '匯豐控股'}]}
        text = summary.render_final_summary(payload, market_audit=market, now=NOW)
        self.assertIn('0005 匯豐控股', text)
        self.assertIn('優先研究', text)
        self.assertIn('Short Put', text)
        self.assertEqual(sum(line.startswith('期權：') for line in text.splitlines()), 1)
        self.assertIn('等待', text)
        self.assertLess(len(text), 1000)

    def test_bearish_stocks_are_not_disguised_as_buy_recommendations(self):
        text = summary.render_final_summary(signals('Underweight'), now=NOW)
        self.assertIn('沒有新增買入推薦', text)
        self.assertIn('暫不增持', text)
        self.assertIn('Short Call', text)
        self.assertNotIn('優先研究 0005', text)

    def test_incomplete_and_previous_day_analysis_do_not_open_a_recommendation(self):
        for payload in [signals(complete=False), {**signals(), 'date': '2026-10-06'}]:
            text = summary.render_final_summary(payload, now=NOW)
            self.assertIn('未有同日四分析員完整研究', text)
            self.assertNotIn('Short Put', text)

    def test_only_three_bullish_stocks_are_selected_from_all_analyzed_stocks(self):
        payload = signals()
        one = payload['signals']['HK.00005']
        payload['signals'] = {f'HK.{code:05d}': dict(one) for code in (5,388,700,1810,9988)}
        text = summary.render_final_summary(payload, now=NOW)
        self.assertEqual(sum(line.startswith('• ') for line in text.splitlines()), 3)
        self.assertNotIn('9988', text)

    def test_unverified_quote_is_never_promoted_to_an_entry_recommendation(self):
        from test_option_screen import candidate
        row = candidate(underlying='HK.00005', option_code='HK.TEST', expiry='2026-11-06', quote_time=NOW.strftime('%Y-%m-%d %H:%M:%S'))
        with patch('agents.screening_agent.datetime') as clock:
            clock.strptime.side_effect = datetime.strptime
            clock.now.return_value = NOW
            text = summary.render_final_summary(signals(), option_audit={'generated_at': NOW.isoformat(), 'candidates': [row], 'errors': []}, now=NOW)
        self.assertIn('HK.TEST', text)
        self.assertIn('主候選', text)
        self.assertIn('等待', text)
        self.assertIn('不開新倉', text)

    def test_after_close_does_not_reuse_an_intraday_option_candidate(self):
        text = summary.render_final_summary(signals(), option_audit={'generated_at': NOW.isoformat(), 'candidates': [], 'errors': []}, now=NOW.replace(hour=22))
        self.assertIn('交易時段外', text)
        self.assertIn('不開新倉', text)

    def test_recommendation_writer_creates_a_plain_text_summary(self):
        from market_recommendations import write_recommendations
        with tempfile.TemporaryDirectory() as directory:
            write_recommendations(signals(), directory=Path(directory), now=NOW)
            self.assertIn('每日決策摘要', (Path(directory)/'final_summary.txt').read_text())
            self.assertIn('期權：等待', (Path(directory)/'final_summary.txt').read_text())

    def test_transport_posts_one_text_message_and_hides_sensitive_errors(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): return b'{"ok":true}'
        with patch('final_summary.urllib.request.urlopen', return_value=Response()) as post:
            summary.send_text('最終總結：等待', token='TEST_VALUE', chat='TEST_CHAT')
        request = post.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body['text'], '最終總結：等待')
        self.assertNotIn('parse_mode', body)
        with patch('final_summary.urllib.request.urlopen', side_effect=HTTPError('private_url', 403, 'private_body', {}, None)):
            with self.assertRaisesRegex(RuntimeError, 'sensitive details omitted') as error:
                summary.send_text('等待', token='TEST_VALUE', chat='TEST_CHAT')
            self.assertNotIn('private', str(error.exception))

