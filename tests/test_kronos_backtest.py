import unittest
from kronos_backtest import metrics

class ForecastMetricsTests(unittest.TestCase):
    def test_paired_errors_exclude_invalid_but_disclose_rejections(self):
        rows=[{'valid':True,'actual':.1,'predicted':.05,'zero':0.,'trend':.02},
              {'valid':True,'actual':-.2,'predicted':-.1,'zero':0.,'trend':.02},
              {'valid':False,'actual':.3,'predicted':100,'zero':0.,'trend':0.}]
        r=metrics(rows)
        self.assertEqual((r['attempted'],r['valid'],r['rejected']),(3,2,1))
        self.assertAlmostEqual(r['predicted']['mae'],.075)
        self.assertAlmostEqual(r['zero']['mae'],.15)
        self.assertEqual(r['predicted']['direction_correct'],2)
        self.assertEqual(r['trend']['direction_correct'],1)
        self.assertAlmostEqual(r['zero_mae_all_attempts'],.2)

    def test_zero_targets_excluded_from_direction_denominator(self):
        r=metrics([{'valid':True,'actual':0.,'predicted':.1,'zero':0.,'trend':0.}])
        self.assertEqual(r['predicted']['direction_n'],0)
        self.assertEqual(metrics([{'valid':False}])['valid'],0)
