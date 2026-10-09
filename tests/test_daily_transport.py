from contextlib import contextmanager
from datetime import datetime
import http.client
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch, Mock

from daily_budget import Budget, gateway, HKT
import daily_delivery
import daily_runner

NOW = datetime(2026, 10, 10, 6, 15, tzinfo=HKT)

class Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz else NOW.replace(tzinfo=None)

class Response:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, *args): return json.dumps(self.value).encode()

@contextmanager
def temporary_cwd():
    old = Path.cwd()
    with tempfile.TemporaryDirectory() as directory:
        os.chdir(directory)
        try: yield Path(directory)
        finally: os.chdir(old)

class DailyTransportTests(unittest.TestCase):
    def post(self, url, payload):
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
        conn.request('POST', parsed.path + '/chat/completions', json.dumps(payload), {'Content-Type':'application/json'})
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_gateway_forwards_once_clamps_output_and_blocks_exhausted_calls(self):
        with temporary_cwd() as root, patch('daily_budget.datetime', Frozen), patch.dict(os.environ, {'DEEPSEEK_API_KEY':'test'}):
            budget = Budget(root/'usage.json', NOW.date().isoformat(), max_calls=1)
            result = {'choices':[{'finish_reason':'stop','message':{'content':'ok'}}], 'usage':{'prompt_tokens':80,'completion_tokens':30}}
            with patch('daily_budget.urllib.request.urlopen', return_value=Response(result)) as upstream, gateway(budget) as url:
                self.assertEqual(self.post(url, {'model':'deepseek-chat','max_tokens':5000,'messages':[]})[0], 200)
                self.assertEqual(self.post(url, {'model':'deepseek-chat','messages':[]})[0], 422)
                self.assertEqual(upstream.call_count, 1)
                forwarded = json.loads(upstream.call_args.args[0].data)
                self.assertEqual(forwarded['max_tokens'],800)
            self.assertEqual(budget.snapshot()['actual_tokens'],110)

    def test_uncertain_upstream_error_remains_charged_and_is_not_retried(self):
        with temporary_cwd() as root, patch('daily_budget.datetime', Frozen), patch.dict(os.environ, {'DEEPSEEK_API_KEY':'test'}):
            budget = Budget(root/'usage.json', NOW.date().isoformat())
            with patch('daily_budget.urllib.request.urlopen', side_effect=TimeoutError('private')) as upstream, gateway(budget) as url:
                code, error = self.post(url, {'model':'deepseek-chat','messages':[]})
                self.assertEqual(code,422)
                self.assertNotIn('private',json.dumps(error))
                self.assertEqual(upstream.call_count,1)
            self.assertGreater(budget.snapshot()['charged_tokens'],0)
            self.assertEqual(budget.snapshot()['unconfirmed_calls'],1)

    def test_truncated_research_is_rejected_but_actual_cost_is_recorded(self):
        with temporary_cwd() as root, patch('daily_budget.datetime', Frozen), patch.dict(os.environ, {'DEEPSEEK_API_KEY':'test'}):
            budget = Budget(root/'usage.json', NOW.date().isoformat())
            result = {'choices':[{'finish_reason':'length'}], 'usage':{'prompt_tokens':20,'completion_tokens':800}}
            with patch('daily_budget.urllib.request.urlopen', return_value=Response(result)), gateway(budget) as url:
                self.assertEqual(self.post(url, {'model':'deepseek-chat','messages':[]})[0],422)
            self.assertEqual(budget.snapshot()['actual_tokens'],820)
            self.assertEqual(budget.snapshot()['unconfirmed_calls'],0)

    def test_gateway_late_calls_never_reach_deepseek(self):
        clock = Mock()
        clock.now.return_value = NOW.replace(hour=8)
        with temporary_cwd() as root, patch('daily_budget.datetime', clock):
            budget = Budget(root/'usage.json', NOW.date().isoformat())
            with patch('daily_budget.urllib.request.urlopen') as upstream, gateway(budget) as url:
                self.assertEqual(self.post(url, {'model':'deepseek-chat','messages':[]})[0],422)
                upstream.assert_not_called()
            self.assertEqual(budget.snapshot()['calls'],0)

    def test_delivery_sends_one_fallback_without_relabeling_old_research(self):
        with temporary_cwd() as root, patch('daily_delivery.datetime', Frozen), patch.dict(os.environ, {'DAILY_DELIVERY_CLAIMED':'true','TELEGRAM_BOT_TOKEN':'test','TELEGRAM_CHAT_ID':'test'}):
            (root/'morning_report').mkdir()
            (root/'morning_report/final_summary.txt').write_text('研究截至：2026-10-09\nold recommendation')
            with patch('daily_delivery.urllib.request.urlopen',return_value=Response({'ok':True,'result':{'message_id':123}})) as send:
                daily_delivery.main()
                self.assertEqual(send.call_count,1)
                payload = json.loads(send.call_args.args[0].data)
                self.assertNotIn('old recommendation',payload['text'])
                self.assertIn('等待',payload['text'])
                self.assertLessEqual(len(payload['text']),1200)
                self.assertTrue(send.call_args.args[0].full_url.endswith('/sendMessage'))
            self.assertEqual(json.loads((root/'delivery_receipt.json').read_text())['message_id'],123)

    def test_missing_claim_and_ambiguous_send_never_retry(self):
        with temporary_cwd(), patch('daily_delivery.datetime', Frozen), patch.dict(os.environ, {'DAILY_DELIVERY_CLAIMED':'false'},clear=True), patch('daily_delivery.urllib.request.urlopen') as send:
            with self.assertRaises(RuntimeError): daily_delivery.main()
            send.assert_not_called()
        with temporary_cwd(), patch('daily_delivery.datetime', Frozen), patch.dict(os.environ, {'DAILY_DELIVERY_CLAIMED':'true','TELEGRAM_BOT_TOKEN':'test','TELEGRAM_CHAT_ID':'test'}):
            with patch('daily_delivery.urllib.request.urlopen',side_effect=TimeoutError()) as send:
                with self.assertRaises(TimeoutError): daily_delivery.main()
                self.assertEqual(send.call_count,1)
                self.assertFalse(Path('delivery_receipt.json').exists())

    def test_timeout_kills_research_and_writes_current_waiting_report(self):
        process = Mock(pid=123)
        process.wait.side_effect = [subprocess.TimeoutExpired('bash',2700), 0]
        with temporary_cwd(), patch('daily_runner.datetime',Frozen), patch.dict(os.environ, {'DEEPSEEK_API_KEY':'test'}), patch('daily_runner.gateway') as gate, patch('daily_runner.subprocess.Popen',return_value=process) as spawn, patch('daily_runner.os.killpg') as kill:
            gate.return_value.__enter__.return_value = 'http://127.0.0.1:123/v1'
            daily_runner.run()
            kill.assert_called_once()
            self.assertIn('等待',Path('final_summary.txt').read_text())
            self.assertEqual(Path('daily_research_status.txt').read_text(),'incomplete')
            env=spawn.call_args.kwargs['env']
            self.assertEqual(env['TAHK_SHORTLIST_LIMIT'],'2')
            self.assertEqual(env['TRADINGAGENTS_LLM_BACKEND_URL'],env['OPENAI_API_BASE'])

    def test_daily_context_retains_existing_evidence(self):
        from daily_budget import attach_daily_context
        graph=types.SimpleNamespace(resolve_instrument_context=lambda *args:'Dated evidence; unknown margin')
        attach_daily_context(graph)
        context=graph.resolve_instrument_context('0700.HK')
        self.assertIn('Dated evidence; unknown margin',context)
        self.assertIn('never conceal missing evidence',context)

if __name__=='__main__': unittest.main()
