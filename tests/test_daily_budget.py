import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

class DailyBudgetTests(unittest.TestCase):
    def test_budget_reserves_parallel_calls_and_never_overruns(self):
        from daily_budget import Budget, BudgetExceeded
        with tempfile.TemporaryDirectory() as temp:
            b = Budget(Path(temp)/'usage.json', '2026-10-10', max_calls=2, max_tokens=2000, max_output=100)
            def reserve(_):
                try:
                    return b.reserve({'model':'deepseek-chat','messages':[{'role':'user','content':'x'}]})
                except BudgetExceeded:
                    return None
            results = list(ThreadPoolExecutor(4).map(reserve, range(4)))
            self.assertEqual(sum(x is not None for x in results), 2)
            self.assertLessEqual(b.snapshot()['charged_tokens'], 2000)
            self.assertEqual(b.snapshot()['calls'], 2)

    def test_actual_usage_is_saved_and_restored_without_prompt_or_secret(self):
        from daily_budget import Budget
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'usage.json'
            b = Budget(path, '2026-10-10')
            ticket = b.reserve({'model':'deepseek-chat','messages':[{'role':'user','content':'private-input'}]})
            b.finish(ticket, {'prompt_tokens':50,'completion_tokens':20,'prompt_cache_hit_tokens':10})
            saved = json.loads(path.read_text())
            self.assertEqual(saved['actual_tokens'],70)
            self.assertEqual(saved['cache_hit_tokens'],10)
            self.assertNotIn('private-input',path.read_text())
            self.assertEqual(Budget(path,'2026-10-10').snapshot()['calls'],1)

    def test_non_deepseek_reasoner_streams_and_oversized_inputs_are_blocked(self):
        from daily_budget import Budget, BudgetExceeded
        with tempfile.TemporaryDirectory() as temp:
            b=Budget(Path(temp)/'usage.json','2026-10-10',max_input_bytes=1000)
            for p in [{'model':'gpt-4','messages':[]}, {'model':'deepseek-reasoner','messages':[]},
                      {'model':'deepseek-chat','stream':True,'messages':[]},
                      {'model':'deepseek-chat','messages':[{'content':'x'*2000}]}]:
                with self.assertRaises(BudgetExceeded): b.reserve(p)
            self.assertEqual(b.snapshot()['calls'],0)

    def test_delivery_is_concise_and_refuses_old_or_late_report(self):
        from daily_delivery import validate_summary
        now=datetime(2026,10,10,8,15,tzinfo=ZoneInfo('Asia/Hong_Kong'))
        self.assertEqual(validate_summary('研究截至：2026-10-10 06:30 HKT\n期權：等待',now=now),'研究截至：2026-10-10 06:30 HKT\n期權：等待')
        for text,clock in [('研究截至：2026-10-09',now),('x'*1500,now),('研究截至：2026-10-10',now.replace(hour=9))]:
            with self.assertRaises(ValueError):validate_summary(text,now=clock)

    def test_daily_profile_preserves_actual_four_analysts_and_limits_generation(self):
        from daily_budget import apply_daily_profile
        c={'deep_think_llm':'deepseek-reasoner','max_tool_rounds':20}
        apply_daily_profile(c,'http://127.0.0.1:1234/v1')
        self.assertEqual(c['deep_think_llm'],'deepseek-chat')
        self.assertEqual(c['quick_think_llm'],'deepseek-chat')
        self.assertEqual(c['max_tool_rounds'],2)
        self.assertEqual(c['llm_max_retries'],0)
        self.assertEqual(c['max_tokens'],800)

if __name__=='__main__':unittest.main()
