"""Exercise the real pinned analytics and the boundary that protects trading rules."""
import importlib.util
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

HKT = ZoneInfo('Asia/Hong_Kong')
NOW = datetime(2026, 10, 14, 10, 30, tzinfo=HKT)


def snapshot():
    bars = []
    start = NOW.date() - timedelta(days=150)
    for i in range(150):
        day = start + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        close = 100 + i * .05 + math.sin(i / 3)
        bars.append(dict(date=day.isoformat(), open=close - .1, high=close + 1,
                         low=close - 1, close=close, volume=100000 + i * 100))
    return dict(ticker='0700.HK', source='deterministic test fixture', bars=bars)


def option(**changes):
    result = dict(option_code='HK.TESTP', option_type='PUT', expiry='2026-11-13',
                  strike=90., spot=100., bid=2., ask=2.2, lot_size=500,
                  quote_time=NOW.isoformat(), iv=30., iv_unit='percent',
                  risk_free_rate=.03, dividend_yield=.02)
    result.update(changes)
    return result


class FinceptBridgeTests(unittest.TestCase):
    def bridge(self):
        self.assertIsNotNone(importlib.util.find_spec('fincept_bridge'),
                             'The approved Fincept analytics bridge is missing')
        import fincept_bridge
        return fincept_bridge

    def test_real_pinned_engine_computes_technicals_without_changing_input(self):
        bridge = self.bridge()
        data = snapshot()
        original = json.dumps(data)
        result = bridge.analyze_snapshot(data, now=NOW)
        self.assertEqual(result['status'], 'available', result)
        tech = result['technicals']
        self.assertTrue(0 <= tech['rsi_14'] <= 100)
        self.assertGreater(tech['sma_20'], 0)
        self.assertGreater(tech['realized_vol_20'], 0)
        self.assertEqual(tech['as_of'], '2026-10-13')
        self.assertEqual(result['upstream']['commit'], '0aa46db2a06b8d8d9f91f07090aa214ac02db5c2')
        self.assertEqual(json.dumps(data), original)

    def test_bad_stale_future_unsorted_or_insufficient_bars_are_unavailable(self):
        bridge = self.bridge()
        data = snapshot()
        bad = [[], data['bars'][:30], data['bars'][::-1],
               data['bars'] + [dict(data['bars'][-1], date='2026-10-15')],
               [dict(row, close=float('nan')) for row in data['bars']]]
        for bars in bad:
            with self.subTest(bars=len(bars)):
                result = bridge.analyze_snapshot(dict(data, bars=bars), now=NOW)
                self.assertEqual(result['technicals']['status'], 'unavailable')
                self.assertNotIn('rsi_14', result['technicals'])

    def test_greeks_use_explicit_units_and_short_position_signs(self):
        bridge = self.bridge()
        result = bridge.analyze_snapshot(dict(snapshot(), options=[option()]), now=NOW)
        item = result['options'][0]
        self.assertEqual(item['status'], 'available', item)
        model = item['model']
        self.assertEqual(model['name'], 'European Black-Scholes-Merton diagnostic')
        self.assertLess(model['option_greeks']['delta'], 0)
        self.assertGreater(model['short_one_contract_greeks']['delta'], 0)
        self.assertLess(model['short_one_contract_greeks']['gamma'], 0)
        self.assertLess(model['short_one_contract_greeks']['vega'], 0)
        self.assertAlmostEqual(model['short_one_contract_greeks']['delta'],
                               -500 * model['option_greeks']['delta'])
        self.assertEqual(model['iv_decimal'], .3)
        alternate = bridge.analyze_snapshot(dict(snapshot(), options=[option(iv=.3, iv_unit='decimal')]), now=NOW)
        self.assertEqual(model['price_per_share'], alternate['options'][0]['model']['price_per_share'])
        self.assertEqual(len(model['scenarios']), 3)
        self.assertLess(model['scenarios'][0]['pnl_one_short_contract'], 0)

    def test_missing_model_inputs_do_not_become_zero_rates_or_broker_greeks(self):
        bridge = self.bridge()
        row = option()
        del row['risk_free_rate']
        result = bridge.analyze_snapshot(dict(snapshot(), options=[row]), now=NOW)
        self.assertEqual(result['options'][0]['model']['status'], 'unavailable')
        self.assertNotIn('option_greeks', result['options'][0]['model'])
        self.assertEqual(result['options'][0]['payoff']['premium_one_contract'], 1000)
        for changes in [dict(iv_unit=None), dict(lot_size=0), dict(quote_time='2026-10-13T10:00:00+08:00'),
                        dict(expiry='2025-09-29'), dict(ask=1), dict(spot=float('inf'))]:
            with self.subTest(changes=changes):
                out = bridge.analyze_snapshot(dict(snapshot(), options=[option(**changes)]), now=NOW)
                self.assertEqual(out['options'][0]['status'], 'unavailable')

    def test_payoff_keeps_unlimited_call_loss_and_never_uses_sampled_range_as_max_loss(self):
        bridge = self.bridge()
        out = bridge.analyze_snapshot(dict(snapshot(), options=[option(option_type='CALL', strike=110)]), now=NOW)
        payoff = out['options'][0]['payoff']
        self.assertTrue(payoff['loss_unbounded'])
        self.assertNotIn('max_loss', payoff)
        self.assertEqual(payoff['scope'], 'hypothetical one short contract at expiry before costs')
        self.assertEqual(payoff['premium_one_contract'], 1000)
        self.assertTrue(any(p['pnl'] < 0 for p in payoff['curve']))

    def test_skew_uses_quoted_iv_at_one_expiry_and_never_backsolves_black76_from_spot(self):
        bridge = self.bridge()
        rows = [option(strike=95, iv=35), option(strike=100, iv=30),
                option(option_type='CALL', strike=100, iv=30),
                option(option_type='CALL', strike=105, iv=25)]
        out = bridge.analyze_snapshot(dict(snapshot(), options=rows), now=NOW)
        smile = out['volatility_by_expiry'][0]
        self.assertEqual(smile['status'], 'available')
        self.assertAlmostEqual(smile['atm_iv'], .3)
        self.assertAlmostEqual(smile['put_minus_call_skew'], .1)
        self.assertEqual(smile['method'], 'quoted IV only; nearest strikes around 5% OTM, not delta matched')

    def test_timeout_corruption_and_malformed_worker_output_are_safely_unavailable(self):
        bridge = self.bridge()
        with patch('fincept_bridge.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', .01)):
            self.assertEqual(bridge.analyze_snapshot(snapshot(), now=NOW)['status'], 'unavailable')
        with patch('fincept_bridge.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'bad JSON', '')):
            self.assertEqual(bridge.analyze_snapshot(snapshot(), now=NOW)['status'], 'unavailable')
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(bridge, 'VENDOR', Path(directory)):
                result = bridge.analyze_snapshot(snapshot(), now=NOW)
            self.assertEqual(result['status'], 'unavailable')

    def test_mixed_underlyings_cannot_manufacture_a_volatility_skew(self):
        bridge = self.bridge()
        rows = [option(underlying='HK.00700', strike=95, iv=35),
                option(underlying='HK.00005', strike=100, iv=30),
                option(underlying='HK.00388', option_type='CALL', strike=105, iv=25)]
        out = bridge.analyze_snapshot(dict(snapshot(), options=rows), now=NOW)
        self.assertEqual([row['status'] for row in out['options']], ['available', 'unavailable', 'unavailable'])
        self.assertTrue(all(row['status'] == 'unavailable' for row in out['volatility_by_expiry']))

    def test_disabled_enrichment_does_not_fetch_or_invoke_workers(self):
        bridge = self.bridge()
        class Graph:
            def resolve_instrument_context(self, *args): return 'original context'
        graph = Graph()
        with patch.dict('os.environ', {'TAHK_FINCEPT_ENABLED': '0'}), patch('fincept_bridge.subprocess.run') as run:
            result = bridge.attach_fincept_context(graph, '0700.HK', '2026-10-14')
        run.assert_not_called()
        self.assertEqual(result['status'], 'disabled')
        self.assertEqual(graph.resolve_instrument_context('0700.HK'), 'original context')

    def test_manual_cli_uses_local_json_without_market_network(self):
        bridge = self.bridge()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = snapshot()
            (root/'input.json').write_text(json.dumps(data))
            run = subprocess.run([sys.executable, 'scripts/run-fincept.py', '--input', str(root/'input.json'),
                                  '--output', str(root/'output.json'), '--now', NOW.isoformat()],
                                 text=True, capture_output=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads((root/'output.json').read_text())['status'], 'available')


if __name__ == '__main__':
    unittest.main()
