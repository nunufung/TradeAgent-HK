"""FinRL research contract; historical simulations never open option gates."""
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

import finrl_research as research


def history(days=100):
    rows = []
    for i, day in enumerate(pd.bdate_range('2024-01-01', periods=days)):
        for j, ticker in enumerate(('0700', '1810')):
            price = 30 + j * 10 + i * .05 + np.sin(i / 3)
            rows.append(dict(date=day.date().isoformat(), tic=ticker,
                             open=price, high=price+2, low=price-2,
                             close=price+1, volume=10000+i))
    return pd.DataFrame(rows)


class DataTests(unittest.TestCase):
    def test_hk_symbols_lagged_features_and_execution_price(self):
        panel = research.prepare_panel(history())
        self.assertEqual(sorted(panel.tic.unique()), ['0700.HK', '1810.HK'])
        self.assertTrue(np.isfinite(panel[research.FEATURES].to_numpy()).all())
        raw = history().query("tic == '0700'").reset_index(drop=True)
        row = panel[panel.tic == '0700.HK'].iloc[0]
        i = raw.index[raw.date == row.date][0]
        self.assertAlmostEqual(row.close, raw.iloc[i].open)
        self.assertAlmostEqual(row.return_1, raw.close.pct_change().iloc[i-1])

    def test_current_close_and_future_cannot_change_current_features(self):
        raw = history()
        first = research.prepare_panel(raw)
        changed = raw.copy()
        changed.loc[changed.date >= '2024-03-01', ['high', 'close']] *= 2
        second = research.prepare_panel(changed)
        pd.testing.assert_frame_equal(first[first.date <= '2024-03-01'],
                                      second[second.date <= '2024-03-01'])

    def test_duplicate_missing_nonfinite_and_unknown_symbols_fail(self):
        raw = history()
        bads = [pd.concat([raw, raw.iloc[:1]]), raw.iloc[1:].copy()]
        for field, value in [('open', 0), ('close', np.inf), ('tic', 'AAPL'), ('volume', -1)]:
            bad = raw.copy(); bad.loc[0, field] = value; bads.append(bad)
        for bad in bads:
            with self.subTest(first=bad.iloc[0].to_dict()):
                with self.assertRaises(ValueError): research.prepare_panel(bad)

    def test_adjustment_roundoff_does_not_reject_valid_price_bars(self):
        raw = history()
        raw.loc[20, 'high'] = raw.loc[20, 'close'] - 4e-15
        panel = research.prepare_panel(raw)
        self.assertGreater(len(panel), 0)
        raw.loc[20, 'high'] = raw.loc[20, 'close'] - .001
        with self.assertRaisesRegex(ValueError, 'Inconsistent OHLC'):
            research.prepare_panel(raw)

    def test_chronological_disjoint_splits_reset_finrl_day_index(self):
        splits = research.split_panel(research.prepare_panel(history()))
        train, validation, test = splits
        self.assertLess(train.date.max(), validation.date.min())
        self.assertLess(validation.date.max(), test.date.min())
        for frame in splits:
            self.assertEqual(frame.index.min(), 0)
            self.assertEqual(len(frame.loc[0]), 2)
        with self.assertRaises(ValueError): research.split_panel(train.iloc[:4])

    def test_metrics_and_costed_buy_hold(self):
        m = research.performance([100, 110, 88, 105])
        self.assertAlmostEqual(m['net_return'], .05)
        self.assertAlmostEqual(m['max_drawdown'], .2)
        frame = pd.DataFrame({'date':['2024-01-01']*2+['2024-01-02']*2,
                              'tic':['0700.HK','1810.HK']*2, 'close':[10,20,10,20]})
        curve = research.buy_hold(frame, initial_cash=1000, cost=.01)
        self.assertEqual(curve[0], 1000)
        self.assertLess(curve[-1], 1000)
        self.assertGreater(curve[-1], 970)
        for invalid in ([0,1], [100, float('nan')], [100]):
            with self.assertRaises(ValueError): research.performance(invalid)

    def test_pinned_environment_and_missing_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError, 'submodule'):
                research.load_finrl_environment(Path(d))

    def test_source_matches_upstream_git_blob_and_tampering_is_rejected(self):
        path = research.FINRL_ROOT / research.ENV_PATH
        if not path.is_file():
            self.skipTest('Pinned FinRL checkout required')
        import hashlib
        raw = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        self.assertEqual(blob, research.LOCK['environment_git_blob'])
        with tempfile.TemporaryDirectory() as d:
            changed = Path(d) / research.ENV_PATH
            changed.parent.mkdir(parents=True)
            changed.write_bytes(raw + b'\n')
            with self.assertRaisesRegex(RuntimeError, 'differs'):
                research.load_finrl_environment(Path(d))


class RuntimeTests(unittest.TestCase):
    def test_training_ends_at_last_real_transition_without_duplicate_reward(self):
        try:
            import stable_baselines3
        except ImportError:
            self.skipTest('Optional FinRL dependencies not installed')
        if not (research.FINRL_ROOT / research.ENV_PATH).is_file():
            self.skipTest('Pinned FinRL checkout required')
        train, _, _ = research.split_panel(research.prepare_panel(history()))
        env = research.make_env(train, 100000, .002)
        env.reset()
        for i in range(train.date.nunique()-1):
            _, _, terminated, truncated, _ = env.step(np.zeros(2))
        self.assertTrue(terminated or truncated)

    def test_actual_finrl_train_select_and_heldout_evaluate(self):
        try:
            import stable_baselines3
        except ImportError:
            self.skipTest('Install requirements-finrl.txt for real training smoke test')
        if not (research.FINRL_ROOT / research.ENV_PATH).is_file():
            self.skipTest('Initialize the pinned external/finrl submodule')
        import torch
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as d:
            result = research.run_research(history(), Path(d), algorithms=['a2c', 'ppo'],
                                           timesteps=64, data_source='synthetic test fixture')
            self.assertEqual(result['status'], 'research_only')
            self.assertFalse(result['execution_eligible'])
            self.assertEqual(result['allowed_option_types'], [])
            self.assertEqual(set(result['validation']), {'a2c', 'ppo'})
            self.assertLess(result['periods']['validation']['end'], result['periods']['test']['start'])
            self.assertIn('equal_weight_buy_hold', result['test'])
            self.assertEqual(result['extra_llm_calls'], 0)
            self.assertEqual(result['data_source'], 'synthetic test fixture')
            self.assertTrue((Path(d)/'finrl_result.json').is_file())
            self.assertIn('simulation', (Path(d)/'finrl_report.md').read_text())
            self.assertTrue((Path(d)/'models'/f"{result['selected_model']}.zip").is_file())
            self.assertTrue((Path(d)/'equity.csv').is_file())
            bundle = __import__('json').loads((Path(d)/'finrl_research_input.json').read_text())
            from trading_workflows import build_workflows, HKT
            from datetime import datetime
            audit = build_workflows({}, {'stocks':[]}, inputs=bundle, input_status='provided',
                                    now=datetime.now(HKT))
            self.assertEqual(audit['modules'][3]['status'], 'computed_from_supplied_data')
            self.assertIn('FinRL', audit['modules'][3]['summary'])
            self.assertTrue(all(m['status']=='blocked' for m in audit['modules'][:3]))

    def test_bad_finrl_result_cannot_make_a_backtest_claim(self):
        from trading_workflows import build_workflows
        for data in ({}, {'status':'research_only','test':{'selected_policy':{'net_return':float('nan')}}}):
            audit = build_workflows({}, {'stocks':[]}, inputs={'finrl':data}, input_status='provided')
            self.assertEqual(audit['modules'][3]['status'], 'blocked')

