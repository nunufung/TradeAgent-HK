import copy
from datetime import datetime
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from test_fincept_bridge import NOW, snapshot, option
from test_recommendations import signals


class IntegrationTests(unittest.TestCase):
    def analytics(self):
        from fincept_bridge import analyze_snapshot
        return analyze_snapshot(snapshot(), now=NOW)

    def payload(self, analytics):
        data = signals()
        data['date'] = NOW.date().isoformat()
        data['generated_at'] = NOW.isoformat()
        data['signals']['HK.00005']['fincept'] = analytics
        return data

    def test_all_four_analysts_receive_bounded_context_without_changing_rating(self):
        from fincept_bridge import attach_fincept_context
        class Graph:
            def resolve_instrument_context(self, *args): return 'existing book and news'
        graph = Graph()
        analytics = self.analytics()
        with patch.dict('os.environ', {'TAHK_FINCEPT_ENABLED': '1'}), patch('fincept_bridge.collect_stock_analytics', return_value=analytics), patch('fincept_bridge.datetime', wraps=datetime) as clock:
            clock.now.return_value = NOW
            out = attach_fincept_context(graph, '0700.HK', NOW.date().isoformat())
        text = graph.resolve_instrument_context('0700.HK', 'stock', NOW.date().isoformat())
        self.assertIn('existing book and news', text)
        self.assertIn('RSI14', text)
        self.assertLess(len(text.encode()), 700)
        self.assertEqual(out, analytics)

    def test_linked_analysis_records_real_fincept_evidence_for_existing_analysts(self):
        import linked_stock_analysis as linked
        check = self
        class Graph:
            def __init__(self, **kwargs):
                check.assertEqual(tuple(kwargs['selected_analysts']), linked.ANALYSTS)
                self.resolve_instrument_context = lambda *args: 'original instrument context'
            def propagate(self, ticker, day):
                text = self.resolve_instrument_context(ticker, 'stock', day)
                check.assertIn('RSI14', text)
                check.assertIn('original instrument context', text)
                return {key: 'Independent report' for key in ('market_report', 'sentiment_report', 'news_report', 'fundamentals_report')}, 'Buy'
        modules = {'tradingagents.default_config': types.SimpleNamespace(DEFAULT_CONFIG={}),
                   'tradingagents.graph.trading_graph': types.SimpleNamespace(TradingAgentsGraph=Graph)}
        analytics = self.analytics()
        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', modules), \
             patch.dict('os.environ', {'TAHK_FINCEPT_ENABLED': '1', 'DEEPSEEK_API_KEY': 'fixture-only'}), \
             patch('fincept_bridge.collect_stock_analytics', return_value=analytics), \
             patch('fincept_bridge.datetime', wraps=datetime) as clock, \
             patch.object(linked, 'configure_free_news'), patch.object(linked, 'attach_news_context'), \
             patch.object(linked, 'write_news_audit'):
            clock.now.return_value = NOW
            root = Path(directory)
            result = linked.analyze(['700'], signal_path=root/'signals.json', report_path=root/'report.md', news_batch={})
        signal = result['signals']['HK.00700']
        self.assertEqual(signal['fincept']['technicals']['status'], 'available')
        self.assertEqual(signal['rating'], 'Buy')
        self.assertTrue(signal['analysis_complete'])
        self.assertEqual(signal['allowed_option_types'], ['PUT'])

    def test_evidence_reaches_detailed_and_short_reports_without_opening_entry_gate(self):
        from market_recommendations import write_recommendations
        from final_summary import render_final_summary
        data = self.payload(self.analytics())
        data['signals']['HK.00005']['fincept']['generated_at'] = NOW.replace(hour=8).isoformat()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = write_recommendations(data, directory=root, now=NOW.replace(hour=8))
            detail = (root/'recommendations.md').read_text()
            text = (root/'final_summary.txt').read_text()
        self.assertIn('RSI14', detail)
        self.assertIn('RSI14', text)
        self.assertLessEqual(len(text), 1200)
        self.assertEqual(out['action'], '等待')
        self.assertFalse(out['risk_review_complete'])
        self.assertEqual(out['stocks'][0]['rating'], 'Buy')
        self.assertIn('21–45', text)

    def test_stale_analytics_are_not_presented_as_current_even_in_same_day_signal(self):
        from final_summary import render_final_summary
        analytics = self.analytics()
        analytics['generated_at'] = '2026-10-01T10:30:00+08:00'
        text = render_final_summary(self.payload(analytics), now=NOW)
        self.assertNotIn('RSI14', text)

    def test_option_payoff_audit_does_not_replace_broker_delta_or_margin(self):
        from market_recommendations import write_recommendations
        from test_option_screen import candidate
        data = self.payload(self.analytics())
        row = candidate(underlying='HK.00005', expiry='2026-11-13',
                        iv_unit='percent', quote_time=NOW.strftime('%Y-%m-%d %H:%M:%S'))
        raw = copy.deepcopy(row)
        audit = {'generated_at': NOW.isoformat(), 'candidates': [row], 'errors': []}
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'TAHK_FINCEPT_ENABLED': '1'}):
            with patch('agents.screening_agent.datetime') as clock:
                from datetime import datetime
                clock.strptime.side_effect = datetime.strptime
                clock.now.return_value = NOW
                result = write_recommendations(data, directory=Path(directory), option_audit=audit, now=NOW)
            saved = json.loads((Path(directory)/'fincept_analytics.json').read_text())
        self.assertEqual(result['action'], '等待')
        self.assertFalse(result['risk_review_complete'])
        self.assertEqual(result['main_option']['delta'], raw['delta'])
        self.assertEqual(row, raw)
        model = saved['main_option']['options'][0]
        self.assertEqual(model['payoff']['status'] if 'status' in model['payoff'] else model['status'], 'available')
        self.assertEqual(model['model']['status'], 'unavailable')

    def test_workflow_uses_same_underlying_expiry_observations_for_real_skew(self):
        from market_recommendations import option_analytics_snapshot
        from fincept_bridge import analyze_snapshot
        primary = dict(option(), underlying='HK.00700')
        rows = [dict(option(strike=strike, iv=iv, option_type=side, option_code=f'HK.TEST{index}'), underlying='HK.00700')
                for index, (strike, iv, side) in enumerate([(95, 35, 'PUT'), (100, 30, 'PUT'),
                                                          (100, 30, 'CALL'), (105, 25, 'CALL')])]
        rows += [dict(option(strike=95, iv=90), underlying='HK.00005')]
        packet = option_analytics_snapshot(primary, {'observations': rows})
        self.assertLessEqual(len(packet['options']), 12)
        self.assertEqual({row['underlying'] for row in packet['options']}, {'HK.00700'})
        out = analyze_snapshot(packet, now=NOW)
        self.assertEqual(out['volatility_by_expiry'][0]['status'], 'available')
        self.assertAlmostEqual(out['volatility_by_expiry'][0]['put_minus_call_skew'], .1)

    def test_report_does_not_claim_payoff_scenarios_when_worker_failed(self):
        from market_recommendations import build_recommendations, render_recommendations
        result = build_recommendations(self.payload(self.analytics()), now=NOW)
        result['fincept_option'] = {'status': 'unavailable', 'options': []}
        text = render_recommendations(result)
        self.assertNotIn('已保存單張候選的到期損益情景', text)
        self.assertIn('量化期權補充未完成', text)

    def test_real_scan_retains_unfiltered_quotes_without_extra_broker_calls(self):
        import pandas as pd
        import main
        class Quotes:
            calls = 0
            def get_option_expiration_date(self, **kwargs):
                return 0, pd.DataFrame({'strike_time': ['2026-11-13']})
            def get_option_chain(self, **kwargs):
                return 0, pd.DataFrame([dict(code=f'HK.OBS{i}', option_type=side,
                    strike_price=strike, lot_size=500) for i, (side, strike)
                    in enumerate([('PUT', 95), ('PUT', 100), ('CALL', 105)])])
            def get_market_snapshot(self, codes):
                self.calls += 1
                return 0, pd.DataFrame([dict(code=code, bid_price=2, ask_price=2.2,
                    option_delta=float('nan'), option_implied_volatility=30,
                    volume=10, option_open_interest=100, last_price=100,
                    update_time=NOW.strftime('%Y-%m-%d %H:%M:%S')) for code in codes])
            def close(self): pass
        quotes = Quotes()
        sdk = types.SimpleNamespace(OpenQuoteContext=lambda **kwargs: quotes,
            OpenSecTradeContext=None, RET_OK=0, OrderType=None, TrdEnv=None,
            TrdMarket=None, SecurityFirm=None)
        observations = []
        with patch.dict('sys.modules', {'futu': sdk}), patch.object(main, '_hkt_today', return_value=NOW.date()), patch('main.time.sleep'):
            candidates, _ = main.scan(['HK.00700'], 'localhost', 11111, require_margin=False,
                stock_signals={'HK.00700': {'allowed_option_types': ['PUT']}},
                analytics_observations=observations)
        self.assertEqual(candidates, [])  # Missing broker delta/margin still blocks entry.
        self.assertEqual(len(observations), 3)
        self.assertEqual({row['option_type'] for row in observations}, {'PUT', 'CALL'})
        self.assertTrue(all(row['iv_unit'] == 'percent' for row in observations))
        self.assertEqual(quotes.calls, 2)  # Existing option snapshot + underlying snapshot only.


if __name__ == '__main__':
    unittest.main()
