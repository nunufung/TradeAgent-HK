import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from book_skill_context import attach_book_context, load_book_context


class BookSkillTests(unittest.TestCase):
    def test_reviewed_skill_reaches_graph_and_preserves_original_news_and_identity(self):
        graph = types.SimpleNamespace(resolve_instrument_context=lambda *args: 'HK identity and dated RSS evidence')
        audit = attach_book_context(graph)
        text = graph.resolve_instrument_context('0700.HK', 'stock', '2026-10-08')
        self.assertIn('HK identity and dated RSS evidence', text)
        self.assertIn('Room for Error', text)
        self.assertIn('policy takes precedence', text)
        self.assertIn('Unknown account cash', text)
        self.assertNotIn('R/R >=3 creates tail', text)
        path = Path(__file__).resolve().parents[1] / 'skills' / audit[0]['path']
        self.assertEqual(audit[0]['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_missing_oversized_and_outside_skill_cannot_silently_proceed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, error in [('missing/SKILL.md', FileNotFoundError), ('../SKILL.md', ValueError)]:
                (root / 'runtime.json').write_text(json.dumps({'skills': [{'name': 'test', 'path': relative}]}))
                with self.assertRaises(error):
                    load_book_context(root)
            (root / 'test').mkdir()
            (root / 'test/SKILL.md').write_text('x' * 16001)
            (root / 'runtime.json').write_text(json.dumps({'skills': [{'name': 'test', 'path': 'test/SKILL.md'}]}))
            with self.assertRaisesRegex(ValueError, 'budget'):
                load_book_context(root)

    def test_daily_pipeline_propagates_book_context_and_records_its_fingerprint(self):
        import linked_stock_analysis as linked

        class Graph:
            def __init__(self, **kwargs):
                self.resolve_instrument_context = lambda *args: 'Original instrument'
                self.analysts = kwargs['selected_analysts']

            def propagate(self, ticker, date):
                self_test.assertEqual(tuple(self.analysts), linked.ANALYSTS)
                context = self.resolve_instrument_context(ticker, 'stock', date)
                self_test.assertIn('Room for Error', context)
                self_test.assertIn('Dated news context', context)
                return {key: 'Actual test analyst report' for key in
                        ('market_report', 'sentiment_report', 'news_report', 'fundamentals_report')}, 'Buy'

        self_test = self
        modules = {
            'tradingagents.default_config': types.SimpleNamespace(DEFAULT_CONFIG={}),
            'tradingagents.graph.trading_graph': types.SimpleNamespace(TradingAgentsGraph=Graph),
        }

        def attach_news(graph, batch):
            original = graph.resolve_instrument_context
            graph.resolve_instrument_context = lambda *args: original(*args) + '\nDated news context'

        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', modules), \
                patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'fake-test-key'}), \
                patch.object(linked, 'configure_free_news'), \
                patch.object(linked, 'attach_news_context', side_effect=attach_news), \
                patch.object(linked, 'write_news_audit'):
            root = Path(directory)
            payload = linked.analyze(['700'], signal_path=root/'signals.json', report_path=root/'report.md', news_batch={})
            signal = payload['signals']['HK.00700']
            self.assertTrue(signal['analysis_complete'])
            self.assertEqual(signal['allowed_option_types'], ['PUT'])
            self.assertEqual(signal['book_skills'], payload['book_skills'])
            self.assertIn('psychology-of-money', (root/'report.md').read_text())
            import importlib.util
            self.assertEqual(Path(importlib.util.find_spec('main').origin).parent,
                             Path(linked.__file__).resolve().parent)

    def test_summary_does_not_claim_legacy_research_used_a_book(self):
        from test_recommendations import signals, NOW
        from final_summary import render_final_summary
        payload = signals()
        self.assertNotIn('書籍風控：', render_final_summary(payload, now=NOW))
        payload['signals']['HK.00005']['book_skills'] = load_book_context()[1]
        self.assertIn('書籍風控：', render_final_summary(payload, now=NOW))


if __name__ == '__main__':
    unittest.main()
