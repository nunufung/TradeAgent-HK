"""Multi-stock news scope, source-only facts and the scheduled/manual boundary."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import free_tech_news as news

if importlib.util.find_spec('hk_market_briefing'):
    import hk_market_briefing as market
else:
    market = None

NOW = datetime(2026, 10, 7, 6, 40, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def article(title, url, *, source='RTHK Finance', kind='media', publisher_url=''):
    return {'title': title, 'url': url, 'published_at': '2026-10-07T04:00:00+00:00',
            'source': source, 'source_type': kind, 'summary': '測試 RSS 摘錄；不是真實市場新聞。',
            'topics': [], 'publisher_url': publisher_url}


class MarketBriefingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(market, 'Cross-stock morning news feature is missing')
        self.watchlist = market.load_watchlist()
        self.batch = {'fetched_at': NOW.isoformat(), 'lookback_hours': 48,
                      'sources': [{'source': 'RTHK Finance', 'status': 'ok'}],
                      'articles': [article('匯豐公布銀行業務更新', 'https://example.com/hsbc'),
                                   article('小米及阿里巴巴公布科技業務更新', 'https://example.com/tech')]}

    def test_bluechips_and_multiple_technology_codes_reach_same_briefing(self):
        rows = market.prepare_candidates(self.batch, self.watchlist)
        self.assertEqual(rows[0]['direct_codes'], ['0005'])
        self.assertEqual(set(rows[1]['direct_codes']), {'1810', '9988'})
        self.assertFalse(any('0700' in row['direct_codes'] for row in rows))

    def test_outdated_future_and_untrusted_aggregator_items_are_excluded(self):
        self.batch['articles'] += [
            {**article('騰訊舊聞', 'https://example.com/old'), 'published_at': '2026-09-01T04:00:00+00:00'},
            {**article('騰訊未來新聞', 'https://example.com/future'), 'published_at': '2026-10-08T04:00:00+00:00'},
            article('騰訊商品推广', 'https://news.google.com/articles/untrusted', kind='aggregator', publisher_url='https://example.com'),
        ]
        self.assertEqual(len(market.prepare_candidates(self.batch, self.watchlist)), 2)

    def test_model_cannot_replace_source_facts_or_add_unlisted_stocks(self):
        rows = market.prepare_candidates(self.batch, self.watchlist)
        choice = {'selected': [{'id': rows[0]['id'], 'title': '捏造股價', 'url': 'https://invented.example',
                               'indirect_codes': ['0700', '9998'], 'impact': '可能影響銀行板塊風險偏好。',
                               'uncertainty': '需要核對公司後續公告。'}]}
        selected = market.validate_selection(choice, rows, self.watchlist)
        self.assertEqual(selected[0]['title'], '匯豐公布銀行業務更新')
        self.assertEqual(selected[0]['url'], 'https://example.com/hsbc')
        self.assertEqual(selected[0]['direct_codes'], ['0005'])
        self.assertEqual(selected[0]['indirect_codes'], ['0700'])

    def test_duplicate_and_unknown_model_selections_cannot_create_news(self):
        rows = market.prepare_candidates(self.batch, self.watchlist)
        selected = market.validate_selection({'selected': [{'id': rows[0]['id']}, {'id': rows[0]['id']}, {'id': 'M999'}]}, rows, self.watchlist)
        self.assertEqual(len(selected), 1)

    def test_one_company_cannot_dominate_the_daily_news_selection(self):
        self.batch['articles'] = [article(f'騰訊業務更新事件 {index}', f'https://example.com/tencent/{index}') for index in range(4)] + self.batch['articles']
        rows = market.prepare_candidates(self.batch, self.watchlist)
        selected = market.validate_selection({'selected': [{'id': row['id']} for row in rows]}, rows, self.watchlist)
        self.assertEqual(sum(row['direct_codes'] == ['0700'] for row in selected), 2)
        self.assertTrue(any('0005' in row['direct_codes'] for row in selected))
        self.assertTrue(any('1810' in row['direct_codes'] for row in selected))

    def test_price_listing_and_external_url_claims_are_removed_from_commentary(self):
        rows = market.prepare_candidates(self.batch, self.watchlist)
        selected = market.validate_selection({'selected': [{'id': rows[0]['id'], 'impact': '未上市，目標價HK$900，https://invented.example'}]}, rows, self.watchlist)
        self.assertNotIn('未上市', selected[0]['impact'])
        self.assertNotIn('900', selected[0]['impact'])
        self.assertNotIn('https://', selected[0]['impact'])

    def test_no_analyst_output_is_marked_as_source_preview(self):
        rows = market.prepare_candidates(self.batch, self.watchlist)
        with tempfile.TemporaryDirectory() as directory:
            market.write_briefing(self.batch, rows, self.watchlist, {'selected': []}, 'unavailable', Path(directory))
            report = Path(directory, 'report_market.md').read_text()
            self.assertIn('分析員未完成篩選', report)
            self.assertNotIn('評級：Buy', report)
            audit = json.loads(Path(directory, 'market_briefing.json').read_text())
            self.assertEqual(audit['analyst_status'], 'unavailable')

    def test_market_pdf_contains_news_and_codes_without_single_stock_price_card(self):
        import generate_pdf as pdf
        from pypdf import PdfReader
        rows = market.prepare_candidates(self.batch, self.watchlist)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            market.write_briefing(self.batch, rows, self.watchlist, {'selected': [{'id': row['id']} for row in rows]}, 'success', root)
            report = pdf.parse_report(str(root/'report_market.md'))
            pdf.build_pdf([report], str(root/'market.pdf'))
            reader = PdfReader(root/'market.pdf')
            text = '\n'.join(page.extract_text() for page in reader.pages)
            self.assertIn('港股藍籌及科技股', text)
            for code in ('0005', '1810', '9988'):
                self.assertIn(code, text)
            self.assertNotIn('Reference price', text)
            self.assertNotIn('FINAL TRANSACTION PROPOSAL', text)
            urls = [annotation.get_object()['/A'].get('/URI') for page in reader.pages for annotation in page.get('/Annots', []) if '/A' in annotation.get_object()]
            self.assertIn('https://example.com/hsbc', urls)


class BroadRSSFeedTests(unittest.TestCase):
    def test_finance_feed_keeps_non_technology_bluechip_headlines(self):
        data = '<rss><channel><item><title>匯豐及友邦業務更新</title><link>https://example.com/banks</link><pubDate>Wed, 07 Oct 2026 04:00:00 GMT</pubDate></item></channel></rss>'.encode()
        kwargs = {'now': NOW, 'start': NOW-timedelta(days=2)}
        try:
            rows = news.parse_feed(data, 'RTHK Finance', 'media', technology_only=False, **kwargs)
        except TypeError:
            self.fail('The bank headline is still blocked by technology-only RSS filtering')
        self.assertEqual(len(rows), 1)
        self.assertEqual(news.parse_feed(data, 'RTHK Finance', 'media', **kwargs), [])


class WorkflowModeTests(unittest.TestCase):
    def run_mode(self, **environment):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recorder = root/'calls.json'
            python = root/'python'
            python.write_text('#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["CALL_FILE"]).write_text(json.dumps(sys.argv[1:]))\nprint("report command captured")\n')
            python.chmod(0o755)
            env = {**os.environ, 'PATH': str(root)+os.pathsep+os.environ['PATH'], 'CALL_FILE': str(recorder), **environment}
            result = subprocess.run(['bash', str(ROOT/'scripts/run-report.sh')], cwd=root, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(recorder.read_text())

    def test_scheduled_report_uses_market_news_even_with_700_input(self):
        self.assertEqual(self.run_mode(EVENT_NAME='schedule', TICKER='700'), ['-u', 'hk_market_briefing.py'])

    def test_telegram_stock_request_keeps_four_analyst_stock_path(self):
        self.assertEqual(self.run_mode(EVENT_NAME='workflow_dispatch', REPORT_SCOPE='stock', TICKER='9988'), ['-u', 'hk_adapter.py', '9988'])

    def test_explicit_market_request_runs_market_briefing(self):
        self.assertEqual(self.run_mode(EVENT_NAME='workflow_dispatch', REPORT_SCOPE='market', TICKER='700'), ['-u', 'hk_market_briefing.py'])


if __name__ == '__main__':
    unittest.main()
