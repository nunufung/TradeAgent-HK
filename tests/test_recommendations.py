import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from market_recommendations import select_shortlist, build_recommendations, write_recommendations

HKT = ZoneInfo('Asia/Hong_Kong')
NOW = datetime(2026, 10, 7, 10, 30, tzinfo=HKT)


def signals(rating='Buy', complete=True):
    return {'date': '2026-10-07', 'analyst_set': ['market', 'social', 'news', 'fundamentals'],
            'signals': {'HK.00005': {'rating': rating, 'analysis_complete': complete,
            'allowed_option_types': ['CALL'],  # Deliberately wrong; derive direction from rating.
            'analysts': {name: {'complete': complete} for name in ('market', 'social', 'news', 'fundamentals')},
            'reports': {'market': '支持位待核實', 'social': '情緒偏正面', 'news': '公司新聞', 'fundamentals': '估值有支持'},
            'decision': '保持審慎'}}}


class RecommendationTests(unittest.TestCase):
    def test_shortlist_balances_groups_and_is_not_fixed_tencent(self):
        stocks = [{'code': '0005', 'group': 'bluechip'}, {'code': '0388', 'group': 'bluechip'},
                  {'code': '0700', 'group': 'technology'}, {'code': '1024', 'group': 'technology'}]
        audit = {'watchlist': stocks, 'selected': [{'direct_codes': ['0005']}, {'direct_codes': ['0388']}, {'direct_codes': ['1024']}]}
        chosen = select_shortlist(audit, now=NOW)
        self.assertEqual(len(chosen), 3)
        self.assertIn('HK.01024', chosen)
        self.assertNotIn('HK.00700', chosen)

    def test_before_ten_is_wait_and_never_invents_contract(self):
        result = build_recommendations(signals(), now=NOW.replace(hour=7))
        self.assertEqual(result['action'], '等待')
        self.assertIsNone(result['main_option'])
        self.assertEqual(result['stocks'][0]['strategy'], 'Short Put（條件式）')
        self.assertIn('10:00', ' '.join(result['reasons']))

    def test_missing_or_old_analyst_blocks_direction(self):
        for payload in (signals(complete=False), {**signals(), 'date': '2026-10-06'}):
            self.assertEqual(build_recommendations(payload, now=NOW)['stocks'][0]['strategy'], '不做')

    def test_neutral_means_no_trade_not_daily_forced_buy(self):
        result = build_recommendations(signals('Hold'), now=NOW)
        self.assertEqual(result['stocks'][0]['strategy'], '不做')
        self.assertEqual(result['action'], '不做')

    def test_quote_candidates_do_not_prove_iv_support_events_or_cash(self):
        # Even a plausible quote cannot be called fully compliant without risk evidence.
        quote = {'generated_at': NOW.isoformat(), 'candidates': [{'underlying': 'HK.00005', 'option_code': 'HK.TEST', 'bid': 2, 'ask': 2.2}], 'errors': []}
        result = build_recommendations(signals(), option_audit=quote, now=NOW)
        self.assertNotEqual(result['action'], '做')
        self.assertIn('完整守則', ' '.join(result['reasons']))

    def test_render_has_actual_four_analyst_evidence_and_exit_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            write_recommendations(signals(), directory=Path(temp), now=NOW)
            text = (Path(temp)/'recommendations.md').read_text()
            for expected in ['技術', '情緒', '新聞', '基本面', '50–70%', '100%', '21', '45', '估值有支持']:
                self.assertIn(expected, text)
            self.assertEqual(json.loads((Path(temp)/'recommendations.json').read_text())['action'], '等待')

class RecommendationPDFTests(unittest.TestCase):
    def test_recommendations_and_four_actual_excerpts_survive_pdf(self):
        import generate_pdf as pdf
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'report_market.md').write_text('# 港股藍籌及科技股市場晨報 | 2026-10-07\n\n**Executive Summary**: 市場新聞及研究推薦。')
            (root/'market_briefing.json').write_text(json.dumps({'watchlist_count': 23, 'selected_count': 0}))
            write_recommendations(signals(), directory=root, now=NOW)
            report = pdf.parse_report(str(root/'report_market.md'))
            pdf.build_pdf([report], str(root/'report.pdf'))
            text = '\n'.join(page.extract_text() for page in PdfReader(root/'report.pdf').pages)
            for expected in ['四分析員推薦與期權紀律', '技術', '情緒', '新聞', '基本面', 'Short Put', '估值有支持', '等待']:
                self.assertIn(expected, text)
            self.assertNotIn('\x00', text)


class EntryWindowTests(unittest.TestCase):
    def test_lunch_after_close_and_weekend_are_not_entry_windows(self):
        from main import _is_open_window
        for value in [NOW.replace(hour=9), NOW.replace(hour=12), NOW.replace(hour=16), NOW.replace(day=10)]:
            self.assertFalse(_is_open_window(value))
        self.assertTrue(_is_open_window(NOW))
        self.assertTrue(_is_open_window(NOW.replace(hour=14)))

    def test_nan_and_infinite_market_numbers_do_not_pass(self):
        from agents.screening_agent import ScreeningAgent
        from test_option_screen import RULES, candidate
        agent = ScreeningAgent(RULES)
        for field in ['bid', 'ask', 'strike', 'spot', 'lot_size']:
            for value in [float('nan'), float('inf')]:
                self.assertEqual(agent.screen([candidate(**{field: value})]), [])

class BroadNewsContextTests(unittest.TestCase):
    def test_verified_bluechip_news_reaches_stock_analysts_without_tech_only_alias(self):
        from free_tech_news import select_articles
        from linked_stock_analysis import load_market_news
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'market_candidates.json'
            hsbc = {'title': '匯豐業務更新', 'summary': 'RSS 實際摘錄', 'direct_codes': ['0005'],
                    'published_at': '2026-10-07T01:00:00+00:00', 'url': 'https://example.com/hsbc', 'source': 'RTHK', 'source_type': 'media'}
            rejected = {**hsbc, 'title': '未核實來源'}
            p.write_text(json.dumps({'fetched_at': NOW.isoformat(), 'sources': [], 'candidates': [hsbc], 'articles': [rejected]}))
            batch = load_market_news(p)
            self.assertEqual(batch['articles'], [hsbc])
            selected = select_articles(batch, '0005.HK', '2026-10-07', '2026-10-07')
            self.assertTrue(selected[0]['company_match'])
            self.assertEqual(selected[0]['title'], '匯豐業務更新')

class LiveQuoteDecisionTests(unittest.TestCase):
    def test_two_numerically_qualified_quotes_produce_one_wait_candidate(self):
        from unittest.mock import patch
        from test_option_screen import candidate
        quote_time = NOW.strftime('%Y-%m-%d %H:%M:%S')
        rows = [candidate(underlying='HK.00005', option_code='HK.TEST1', expiry='2026-11-06', quote_time=quote_time),
                candidate(underlying='HK.00005', option_code='HK.TEST2', expiry='2026-11-06', quote_time=quote_time)]
        with patch('agents.screening_agent.datetime') as clock:
            clock.strptime.side_effect = datetime.strptime
            clock.now.return_value = NOW
            result = build_recommendations(signals(), option_audit={'generated_at': NOW.isoformat(), 'candidates': rows, 'errors': []}, now=NOW)
        self.assertEqual(result['action'], '等待')
        self.assertEqual(result['main_option']['option_code'], 'HK.TEST1')
        self.assertFalse(result['risk_review_complete'])
        self.assertIn('完整守則', ' '.join(result['reasons']))

    def test_stale_scan_cannot_supply_even_a_research_contract(self):
        audit = {'generated_at': NOW.replace(hour=9).isoformat(), 'candidates': [], 'errors': []}
        result = build_recommendations(signals(), option_audit=audit, now=NOW)
        self.assertEqual(result['action'], '等待')
        self.assertIsNone(result['main_option'])
        self.assertIn('舊報價', ' '.join(result['reasons']))

class SharedStockReportTests(unittest.TestCase):
    def test_real_state_extraction_requires_all_four_reports(self):
        from linked_stock_analysis import signal_from_state
        state = {'market_report': '市場論證', 'sentiment_report': '情緒論證',
                 'news_report': '新聞論證', 'fundamentals_report': '基本面論證',
                 'final_trade_decision': '正股綜合論證'}
        signal = signal_from_state(state, 'BUY', '0005.HK')
        self.assertEqual(signal['allowed_option_types'], ['PUT'])
        self.assertEqual(signal['reports']['fundamentals'], '基本面論證')
        self.assertEqual(signal['decision'], '正股綜合論證')
        state.pop('news_report')
        self.assertEqual(signal_from_state(state, 'BUY', '0005.HK')['allowed_option_types'], [])

    def test_single_stock_pdf_keeps_its_recommendation_section(self):
        import generate_pdf as pdf
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'report_0005.md').write_text('# 0005.HK 2026-10-07\n\n評級：Buy\n\n研究論證。')
            write_recommendations(signals(), directory=root, now=NOW)
            report = pdf.parse_report(str(root/'report_0005.md'))
            self.assertIsNone(report.market_metadata)
            pdf.build_pdf([report], str(root/'report.pdf'))
            text = '\n'.join(page.extract_text() for page in PdfReader(root/'report.pdf').pages)
            self.assertIn('四分析員推薦與期權紀律', text)
            self.assertIn('估值有支持', text)
            self.assertIn('Short Put', text)
