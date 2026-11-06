"""User-authorized delayed research must run once and remain honestly dated."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from daily_budget import HKT, Budget, gateway
import daily_delivery
import daily_runner
import test_daily_transport as transport
from test_daily_transport import Response, temporary_cwd


class LateRecoveryTests(unittest.TestCase):
    def test_late_research_gets_a_bounded_session_and_requires_expert_review(self):
        now = datetime(2026, 11, 6, 15, 10, tzinfo=HKT)
        clock = Mock()
        clock.now.return_value = now
        clock.combine = datetime.combine
        with temporary_cwd() as root, patch.dict(os.environ, {'DAILY_ALLOW_LATE': 'true', 'DEEPSEEK_API_KEY': 'test'}), patch('daily_runner.datetime', clock), patch('daily_runner.refresh_public_options', return_value=None), patch('daily_runner.gateway') as gate, patch('daily_runner.subprocess.Popen') as spawn, patch('daily_runner.build_reviews', return_value=[{'reviewed': True}]), patch('agents.opportunity_selector.generate'):
            (root/'final_summary.txt').write_text('研究截至：2026-11-06 15:10 HKT\n股票：條件式提議')
            (root/'stock_signals.json').write_text('{}')
            gate.return_value.__enter__.return_value = 'http://localhost:1234/v1'
            spawn.return_value.wait.return_value = 0
            daily_runner.run()
            spawn.return_value.wait.assert_called_once_with(timeout=2700)
            self.assertEqual(gate.call_args.kwargs['deadline'], now + timedelta(minutes=45))
            audit = json.loads((root/'daily_research_status.json').read_text())
            self.assertEqual(audit['status'], 'complete')
            self.assertTrue(audit['late_recovery'])

    def test_late_gateway_uses_session_deadline_and_still_stops_after_it(self):
        now = datetime(2026, 11, 6, 15, 10, tzinfo=HKT)
        clock = Mock()
        clock.now.return_value = now
        with temporary_cwd() as root, patch('daily_budget.datetime', clock), patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test'}):
            budget = Budget(root/'usage.json', '2026-11-06')
            response = Response({'choices': [{'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 10}})
            with patch('daily_budget.urllib.request.urlopen', return_value=response) as upstream, gateway(budget, deadline=now + timedelta(minutes=45)) as url:
                post = transport.DailyTransportTests().post
                self.assertEqual(post(url, {'model': 'deepseek-chat', 'messages': []})[0], 200)
                clock.now.return_value = now + timedelta(minutes=45)
                self.assertEqual(post(url, {'model': 'deepseek-chat', 'messages': []})[0], 422)
                upstream.assert_called_once()

    def test_late_delivery_sends_once_labels_delay_and_saves_receipt(self):
        now = datetime(2026, 11, 6, 15, 55, tzinfo=HKT)
        clock = Mock()
        clock.now.return_value = now
        with temporary_cwd() as root, patch('daily_delivery.datetime', clock), patch.dict(os.environ, {'DAILY_ALLOW_LATE': 'true', 'DAILY_MANUAL_RECOVERY': 'false', 'DAILY_DELIVERY_CLAIMED': 'true', 'TELEGRAM_BOT_TOKEN': 'test', 'TELEGRAM_CHAT_ID': 'test'}):
            (root/'morning_report').mkdir()
            (root/'morning_report/final_summary.txt').write_text('研究截至：2026-11-06 15:50 HKT\n股票：有條件提議')
            with patch('daily_delivery.urllib.request.urlopen', return_value=Response({'ok': True, 'result': {'message_id': 321}})) as send:
                daily_delivery.main()
                send.assert_called_once()
                text = json.loads(send.call_args.args[0].data)['text']
                self.assertIn('延遲補發', text)
                self.assertIn('15:50', text)
                self.assertIn('有條件提議', text)
            receipt = json.loads((root/'delivery_receipt.json').read_text())
            self.assertEqual(receipt['message_id'], 321)
            self.assertTrue(receipt['delayed'])

    def test_late_permission_does_not_allow_yesterday_or_preopen(self):
        now = datetime(2026, 11, 6, 15, 55, tzinfo=HKT)
        with self.assertRaises(ValueError):
            daily_delivery.validate_summary('研究截至：2026-11-05\n舊推薦', now=now, allow_late=True)
        with self.assertRaises(ValueError):
            daily_delivery.validate_summary('研究截至：2026-11-06', now=now.replace(hour=9), allow_late=True)

    def test_recovery_cannot_run_into_the_next_calendar_day(self):
        from daily_budget import research_deadline
        now = datetime(2026, 11, 6, 23, 40, tzinfo=HKT)
        end = research_deadline(now, allow_late=True)
        self.assertEqual(end.date(), now.date())
        self.assertEqual((end.hour, end.minute), (23, 50))

    def test_production_workflow_late_slots_start_research_and_deliver(self):
        import shutil
        import subprocess
        import textwrap
        if not shutil.which('node'):
            self.skipTest('Node is required to execute the real workflow scripts')
        source = Path('.github/workflows/hk-daily.yml').read_text()
        for step_name in ["Inspect today's saved research and budget", 'Check deadline, daily delivery claim and current report']:
            step = source.split('      - name: ' + step_name, 1)[1]
            script = textwrap.dedent(step.split('          script: |\n', 1)[1].split('\n      - ', 1)[0])
            for clock, expected in [('09:59', 'true'), ('15:10', 'false')]:
                harness = """
const outputs = {};
const core = {setOutput:(k,v)=>outputs[k]=v, info:()=>{}, setFailed:v=>outputs.error=v};
const Intl = {DateTimeFormat:function(_,o){return {format:()=>o.hour?CLOCK:'2026-11-06'};}};
const github = {paginate:async()=>[],rest:{actions:{listArtifactsForRepo:()=>{}}}};
const context = {repo:{owner:'test',repo:'test'},eventName:'schedule'};
process.env.TELEGRAM_BOT_TOKEN='test';process.env.TELEGRAM_CHAT_ID='test';
process.env.DAILY_MANUAL_RECOVERY='false';process.env.DAILY_ALLOW_LATE='true';
await (async()=>{BODY})();console.log(JSON.stringify(outputs));
""".replace('CLOCK', json.dumps(clock)).replace('BODY', script)
                result = subprocess.run(['node','--input-type=module'], input=harness, text=True, capture_output=True, check=True)
                outputs = json.loads(result.stdout)
                self.assertEqual(outputs['skip'], expected, (step_name, clock))
                self.assertNotIn('error', outputs)
        self.assertIn("group: hk-daily-${{ inputs.ticker != '' && 'stock' || 'daily' }}", source)
        self.assertIn("if: inputs.ticker == '' && !inputs.recover_daily", source)
        self.assertIn("if: always() && inputs.ticker == '' && needs.report.outputs.request_accepted != 'false'", source)

    def test_expired_push_request_cannot_start_research_or_delivery(self):
        import shutil
        import subprocess
        import textwrap
        if not shutil.which('node'):
            self.skipTest('Node is required to execute the real workflow script')
        source = Path('.github/workflows/hk-daily.yml').read_text()
        step = source.split("      - name: Inspect today's saved research and budget", 1)[1]
        script = textwrap.dedent(step.split('          script: |\n', 1)[1].split('\n      - ', 1)[0])
        harness = """
const outputs={};const core={setOutput:(k,v)=>outputs[k]=v,info:()=>{}};
const Intl={DateTimeFormat:function(_,o){return {format:()=>o.hour?'15:10':'2026-11-06'};}};
const github={rest:{repos:{getContent:async()=>({data:{content:Buffer.from(JSON.stringify({date:'2026-11-05'})).toString('base64')}})}}};
const context={eventName:'push',repo:{},sha:'test'};
await (async()=>{BODY})();console.log(JSON.stringify(outputs));
""".replace('BODY',script)
        result=subprocess.run(['node','--input-type=module'],input=harness,text=True,capture_output=True,check=True)
        self.assertEqual(json.loads(result.stdout)['request_accepted'], 'false')
        self.assertEqual(json.loads(result.stdout)['skip'], 'true')

    def test_structured_analyst_can_finish_above_the_old_1600_token_cap(self):
        now = datetime(2026, 11, 6, 15, 10, tzinfo=HKT)
        clock = Mock()
        clock.now.return_value = now
        with temporary_cwd() as root, patch('daily_budget.datetime', clock), patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test'}):
            budget = Budget(root/'usage.json', '2026-11-06')
            result = Response({'choices': [{'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 2500}})
            with patch('daily_budget.urllib.request.urlopen', return_value=result) as upstream, gateway(budget, deadline=now + timedelta(minutes=45)) as url:
                self.assertEqual(transport.DailyTransportTests().post(url, {'model': 'deepseek-chat', 'max_tokens': 4096, 'messages': []})[0], 200)
                self.assertEqual(json.loads(upstream.call_args.args[0].data)['max_tokens'], 4096)
            self.assertEqual(budget.snapshot()['actual_tokens'], 2600)

    def test_repair_updates_original_message_and_rejects_a_stale_receipt(self):
        now = datetime(2026, 11, 6, 16, 30, tzinfo=HKT)
        clock = Mock()
        clock.now.return_value = now
        env = {'DAILY_ALLOW_LATE': 'true', 'DAILY_MANUAL_RECOVERY': 'false', 'DAILY_DELIVERY_CLAIMED': 'true', 'DAILY_UPDATE_EXISTING': 'true', 'TELEGRAM_BOT_TOKEN': 'test', 'TELEGRAM_CHAT_ID': 'test'}
        with temporary_cwd() as root, patch('daily_delivery.datetime', clock), patch.dict(os.environ, env):
            (root/'morning_report').mkdir()
            (root/'morning_report/final_summary.txt').write_text('研究截至：2026-11-06 16:25 HKT\n股票：條件式提議')
            (root/'prior_delivery').mkdir()
            prior = root/'prior_delivery/delivery_receipt.json'
            prior.write_text(json.dumps({'date': '2026-11-06', 'message_id': 321}))
            with patch('daily_delivery.urllib.request.urlopen', return_value=Response({'ok': True, 'result': {'message_id': 321}})) as send:
                daily_delivery.main()
                send.assert_called_once()
                request = send.call_args.args[0]
                self.assertTrue(request.full_url.endswith('/editMessageText'))
                self.assertEqual(json.loads(request.data)['message_id'], 321)
                self.assertTrue(json.loads((root/'delivery_receipt.json').read_text())['updated_existing'])
            prior.write_text(json.dumps({'date': '2026-11-05', 'message_id': 321}))
            with patch('daily_delivery.urllib.request.urlopen') as send:
                with self.assertRaises(ValueError):
                    daily_delivery.main()
                send.assert_not_called()
