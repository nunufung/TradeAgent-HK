"""Local DeepSeek gateway: reserve spend before forwarding, persist only usage."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import urllib.request
from zoneinfo import ZoneInfo

HKT = ZoneInfo('Asia/Hong_Kong')

class BudgetExceeded(RuntimeError):
    pass

class Budget:
    def __init__(self, path: Path, day: str, *, max_calls=48, max_tokens=100000,
                 max_output=800, max_input_bytes=60000):
        self.path, self.day = path, day
        self.max_calls, self.max_tokens = max_calls, max_tokens
        self.max_output, self.max_input_bytes = max_output, max_input_bytes
        self.lock = threading.Lock()
        self.state = {'date':day,'calls':0,'charged_tokens':0,'actual_tokens':0,
                      'prompt_tokens':0,'completion_tokens':0,'cache_hit_tokens':0,
                      'unconfirmed_calls':0,'entries':[]}
        if path.is_file():
            saved = json.loads(path.read_text())
            if saved.get('date') == day:
                self.state = saved
        self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2))
        temporary.replace(self.path)

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def reserve(self, payload: dict):
        if payload.get('model') != 'deepseek-chat' or payload.get('stream'):
            raise BudgetExceeded('Daily mode only allows non-streaming deepseek-chat.')
        output = int(payload.get('max_tokens', self.max_output))
        if output < 1:
            raise BudgetExceeded('Invalid output limit.')
        payload['max_tokens'] = min(output, self.max_output)
        # Bytes are a deliberately conservative token bound, not a token estimate.
        # Include tool schemas and request structure; never truncate evidence.
        raw = json.dumps(payload, ensure_ascii=False).encode()
        if len(raw) > self.max_input_bytes:
            raise BudgetExceeded('Daily request input is too large.')
        reserve = len(raw) + 512 + payload['max_tokens']
        with self.lock:
            if self.state['calls'] >= self.max_calls or self.state['charged_tokens'] + reserve > self.max_tokens:
                raise BudgetExceeded('Daily request or token budget exhausted.')
            self.state['calls'] += 1
            self.state['charged_tokens'] += reserve
            self.state['unconfirmed_calls'] += 1
            ticket = len(self.state['entries'])
            self.state['entries'].append({'call':self.state['calls'],'reserved':reserve,'status':'reserved'})
            self._save()  # Durable before an API call, including uncertain failures.
            return ticket

    def finish(self, ticket, usage):
        with self.lock:
            row = self.state['entries'][ticket]
            if row['status'] != 'reserved':
                return
            if isinstance(usage, dict) and all(isinstance(usage.get(k), int) and usage[k] >= 0 for k in ('prompt_tokens','completion_tokens')):
                prompt, output = usage['prompt_tokens'], usage['completion_tokens']
                actual = prompt + output
                self.state['charged_tokens'] += max(actual, 0) - row['reserved']
                self.state['actual_tokens'] += actual
                self.state['prompt_tokens'] += prompt
                self.state['completion_tokens'] += output
                self.state['cache_hit_tokens'] += max(0, int(usage.get('prompt_cache_hit_tokens') or 0))
                self.state['unconfirmed_calls'] -= 1
                row.update(status='measured', prompt_tokens=prompt, completion_tokens=output)
            else:
                row['status'] = 'uncertain'  # Keep the full reserved charge.
            self._save()

def apply_daily_profile(config: dict, backend: str):
    config.update(llm_provider='openai', deep_think_provider='openai', quick_think_provider='openai',
                  backend_url=backend, deep_think_backend_url=backend, quick_think_backend_url=backend,
                  deep_think_llm='deepseek-chat', quick_think_llm='deepseek-chat',
                  max_tokens=800, llm_max_retries=0, max_tool_rounds=2, max_recur_limit=64,
                  max_debate_rounds=1, max_risk_discuss_rounds=1,
                  news_article_limit=5, global_news_article_limit=3, global_news_lookback_days=2)

@contextmanager
def gateway(budget: Budget):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log headers, prompts or keys.

        def reply(self, code, body):
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            ticket = None
            try:
                now = datetime.now(HKT)
                if now.date().isoformat() != budget.day or now.time() >= time(8):
                    raise BudgetExceeded('Morning research cutoff reached.')
                if self.path not in ('/chat/completions','/v1/chat/completions'):
                    raise BudgetExceeded('Unsupported API route.')
                size = int(self.headers.get('Content-Length','0'))
                if not 0 < size <= budget.max_input_bytes:
                    raise BudgetExceeded('Invalid request size.')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise BudgetExceeded('Invalid request.')
                ticket = budget.reserve(payload)
                key = os.environ.get('DEEPSEEK_API_KEY','').strip()
                if not key:
                    raise ValueError('Missing credentials')
                request = urllib.request.Request('https://api.deepseek.com/chat/completions',
                    data=json.dumps(payload).encode(), headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
                with urllib.request.urlopen(request, timeout=90) as response:
                    body = response.read(2_000_000)
                result = json.loads(body)
                budget.finish(ticket,result.get('usage'))
                if any(c.get('finish_reason') == 'length' for c in result.get('choices',[])):
                    raise BudgetExceeded('Truncated research cannot be treated as complete.')
                self.reply(200,body)
            except Exception as exc:
                if ticket is not None:
                    budget.finish(ticket,None)
                # 4xx deliberately prevents SDK retries; uncertain API calls stay charged.
                self.reply(422,json.dumps({'error':{'message':'Daily API request stopped: '+type(exc).__name__, 'type':'daily_budget'}}).encode())

    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1'
    finally:
        server.shutdown()
        server.server_close()


def attach_daily_context(graph):
    """Request concise independent reports before generation, without replacing evidence."""
    original = graph.resolve_instrument_context
    instruction = ('Daily research budget: respond in concise Traditional Chinese. '
                   'Each analyst report should use at most 180 Chinese characters, covering conclusion, '
                   'key evidence and missing data. Debate and risk responses should use at most 120 Chinese characters. '
                   'Retain required final rating/schema and all risk gates. Do not repeat company introductions, '
                   'tool traces or full tables; never conceal missing evidence to meet the length target.')

    def enriched(ticker, asset_type='stock', trade_date=None):
        return original(ticker, asset_type, trade_date) + '\n\n' + instruction

    graph.resolve_instrument_context = enriched
