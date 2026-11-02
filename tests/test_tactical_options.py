import copy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import types
import unittest
from zoneinfo import ZoneInfo

from test_recommendations import signals, NOW


def reviewed(rating='Hold', bias='BEARISH'):
    payload = signals(rating)
    review = {'bias': bias, 'thesis': '短線動能回落，長線估值仍有支持',
              'entry_trigger': '10:00後反彈受阻，兩腿報價穩定',
              'invalidation': '升穿已核實阻力即取消',
              'risk': '基本面偏多，反彈或IV上升可令價差虧損', 'confidence': 'medium'}
    payload['signals']['HK.00005']['decision'] += '\n<option_review>' + json.dumps(review, ensure_ascii=False) + '</option_review>'
    return payload


class TacticalOptionTests(unittest.TestCase):
    def test_hold_can_have_bearish_short_term_option_review(self):
        from market_recommendations import build_recommendations
        result = build_recommendations(reviewed(), now=NOW)
        idea = result['option_reviews'][0]
        self.assertEqual(result['stocks'][0]['rating'], 'Hold')
        self.assertEqual(idea['bias'], 'BEARISH')
        self.assertEqual(idea['status'], 'CONDITIONAL')
        self.assertEqual(idea['strategy'], 'BEAR_CALL_CREDIT')
        self.assertFalse(idea['execution_eligible'])

    def test_long_term_buy_does_not_veto_short_term_bearish_view(self):
        from market_recommendations import build_recommendations
        result = build_recommendations(reviewed('Buy'), now=NOW)
        self.assertEqual(result['stocks'][0]['allowed_option_types'], ['PUT'])
        self.assertEqual(result['option_reviews'][0]['strategy'], 'BEAR_CALL_CREDIT')

    def test_incomplete_old_or_missing_review_cannot_create_an_idea(self):
        from market_recommendations import build_recommendations
        old = reviewed(); old['date'] = '2026-10-06'
        incomplete = reviewed(); incomplete['signals']['HK.00005']['reports']['news'] = ''
        for payload in [old, incomplete, signals('Hold')]:
            with self.subTest(payload=payload):
                self.assertEqual(build_recommendations(payload, now=NOW)['option_reviews'], [])

    def test_malformed_ambiguous_or_unbounded_review_is_rejected(self):
        from option_review import parse_review
        for text in ['<option_review>{}</option_review>',
                     '<option_review>{bad json}</option_review>',
                     reviewed()['signals']['HK.00005']['decision'] * 2]:
            self.assertIsNone(parse_review(text))
        p = reviewed()
        p['signals']['HK.00005']['decision'] = p['signals']['HK.00005']['decision'].replace('BEARISH', 'NAKED_CALL')
        self.assertIsNone(parse_review(p['signals']['HK.00005']['decision']))

    def test_no_edge_is_a_real_review_not_a_forced_trade(self):
        from final_summary import render_final_summary
        text = render_final_summary(reviewed(bias='NO_EDGE'), now=NOW)
        self.assertIn('未見短線優勢', text)
        self.assertNotIn('Bear Call Spread', text)

    def test_tactical_summary_keeps_trigger_dissent_and_exit_plan(self):
        from final_summary import render_final_summary
        text = render_final_summary(reviewed(), now=NOW.replace(hour=7))
        for value in ['首選', 'Bear Call Spread', '1–3', '20–30%', '反彈受阻', '升穿', '基本面偏多', '條件式', '最大虧損']:
            self.assertIn(value, text)
        self.assertNotIn('無方向候選', text)
        self.assertLessEqual(len(text), 1200)

    def test_three_ideas_and_full_report_keep_the_review(self):
        from market_recommendations import write_recommendations
        p = reviewed()
        row = p['signals']['HK.00005']
        p['signals'] = {f'HK.{code:05d}': copy.deepcopy(row) for code in [5, 700, 388]}
        with tempfile.TemporaryDirectory() as directory:
            write_recommendations(p, directory=Path(directory), now=NOW)
            text = (Path(directory) / 'final_summary.txt').read_text()
            full = (Path(directory) / 'recommendations.md').read_text()
        self.assertEqual(text.count('備選'), 2)
        self.assertIn('短線期權綜合判斷', full)
        self.assertIn('基本面偏多', full)
        self.assertLessEqual(len(text), 1200)

    def test_context_reuses_four_reports_without_forcing_agreement(self):
        from option_review import attach_option_context
        graph = types.SimpleNamespace(resolve_instrument_context=lambda *args: 'Existing dated evidence')
        attach_option_context(graph)
        text = graph.resolve_instrument_context('0005.HK')
        for value in ['Existing dated evidence', 'option_review', 'NO_EDGE', 'Hold', '1–3', 'do not require unanimous']:
            self.assertIn(value, text)

    def test_public_contract_pair_is_historical_not_an_executable_quote(self):
        from final_summary import render_final_summary
        base = {'underlying': 'HK.00005', 'option_type': 'CALL', 'expiry': '2026-10-30',
                'spot_close': 130, 'strike': 140, 'settlement_price': 1, 'volume': 20, 'open_interest': 200}
        audit = {'status': 'EOD_RESEARCH_ONLY', 'as_of': '2026-10-06',
                 'contracts': [base, {**base, 'strike': 145, 'settlement_price': .5}]}
        text = render_final_summary(reviewed(), now=NOW, public_option_audit=audit)
        self.assertIn('140', text); self.assertIn('145', text)
        self.assertIn('2026-10-30', text); self.assertIn('收市', text)
        self.assertNotIn('最大虧損HK$', text)

    def test_stale_contracts_are_not_used_for_the_review(self):
        from final_summary import render_final_summary
        audit = {'status': 'EOD_RESEARCH_ONLY', 'as_of': '2026-09-01', 'contracts': [
            {'underlying': 'HK.00005', 'option_type': 'CALL', 'expiry': '2026-10-30',
             'spot_close': 130, 'strike': 98765, 'settlement_price': 1, 'volume': 20, 'open_interest': 200}]}
        text = render_final_summary(reviewed(), now=NOW, public_option_audit=audit)
        self.assertNotIn('98765', text)
        self.assertIn('行使價／到期日待配', text)

    def test_saved_full_report_and_summary_share_the_historical_pair(self):
        from market_recommendations import write_recommendations
        base = {'underlying': 'HK.00005', 'option_type': 'CALL', 'expiry': '2026-10-30',
                'spot_close': 130, 'strike': 140, 'settlement_price': 1, 'volume': 20, 'open_interest': 200}
        audit = {'status': 'EOD_RESEARCH_ONLY', 'as_of': '2026-10-06',
                 'contracts': [base, {**base, 'strike': 145, 'settlement_price': .5}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'public_option_data.json').write_text(json.dumps(audit))
            write_recommendations(reviewed(), directory=root, now=NOW)
            for path in ['final_summary.txt', 'recommendations.md']:
                text = (root/path).read_text()
                self.assertIn('賣140／買145', text, path)
                self.assertIn('2026-10-30', text, path)

    def test_stock_summary_does_not_display_the_internal_review_json(self):
        from market_recommendations import research_summary
        text = research_summary(reviewed()['signals']['HK.00005']['decision'])
        self.assertNotIn('option_review', text)
        self.assertNotIn('entry_trigger', text)
        self.assertIn('保持審慎', text)


if __name__ == '__main__':
    unittest.main()
