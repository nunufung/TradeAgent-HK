import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime

import daily_delivery
import telegram_stock_bot as bot

class RecoveryTests(unittest.TestCase):
    def test_explicit_stock_request_validates_and_never_polls(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'DIRECT_TICKER':'01810','GITHUB_OUTPUT':tmp+'/out'}), patch.object(bot, '_api', side_effect=AssertionError('must not poll')):
            self.assertEqual(bot.prepare(), 0)
            self.assertEqual(Path(tmp+'/out').read_text(), 'kind=stock\nticker=1810\nupdate_id=\n')

    def test_blank_dispatch_preserves_pending_request_path(self):
        with patch.dict(os.environ, {'DIRECT_TICKER':''}), patch.object(bot, 'poll', return_value=0):
            self.assertEqual(bot.prepare(), 0)

    def test_invalid_dispatch_cannot_become_shell_code(self):
        for ticker in ('0', '1810; env', '/stock 1810', '123456'):
            with self.subTest(ticker=ticker), patch.dict(os.environ, {'DIRECT_TICKER':ticker}):
                with self.assertRaises(ValueError): bot.prepare()

    def test_manual_recovery_labels_current_day_report_after_deadline(self):
        now = datetime(2026,10,23,14,0,tzinfo=daily_delivery.HKT)
        text = daily_delivery.validate_summary('研究截至：2026-10-23 07:27 HKT\n今日結論：等待', now=now, recovery=True)
        self.assertIn('手動補發', text)
        self.assertIn('07:27', text)

    def test_manual_recovery_still_rejects_stale_research(self):
        now = datetime(2026,10,23,14,0,tzinfo=daily_delivery.HKT)
        with self.assertRaises(ValueError):
            daily_delivery.validate_summary('研究截至：2026-10-22 07:27 HKT',now=now,recovery=True)

if __name__ == '__main__': unittest.main()
