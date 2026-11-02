"""Run the automatic morning research inside one bounded DeepSeek session."""
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
from daily_budget import Budget, gateway, HKT, RESEARCH_START, RESEARCH_CUTOFF
from daily_delivery import fallback_summary, validate_summary
from public_option_data import refresh_public_options
from option_review import build_reviews


def run():
    now = datetime.now(HKT)
    before_start = now.time() < RESEARCH_START
    public_options = None if before_start else refresh_public_options(now=now)
    now = datetime.now(HKT)
    ledger = Path('daily_token_usage.json')
    budget = Budget(ledger, now.date().isoformat())
    deadline = datetime.combine(now.date(), RESEARCH_CUTOFF, HKT)
    seconds = min(45 * 60, int((deadline - now).total_seconds()))
    status = 'incomplete'
    reviewed_underlyings = 0
    reason = 'BEFORE_RESEARCH_START' if before_start else 'STARTED_AFTER_CUTOFF' if seconds <= 0 else 'INSUFFICIENT_RESEARCH_WINDOW' if seconds < 300 else 'MISSING_API_KEY'
    if not before_start and seconds >= 300 and os.environ.get('DEEPSEEK_API_KEY'):
        reason = 'RESEARCH_INCOMPLETE'
        with gateway(budget) as backend:
            env = dict(os.environ, TAHK_BUDGETED_DAILY='1', TAHK_SHORTLIST_LIMIT='1' if seconds < 1200 else '2',
                       TRADINGAGENTS_LLM_BACKEND_URL=backend, OPENAI_API_BASE=backend,
                       EVENT_NAME='schedule', REPORT_SCOPE='market')
            process = subprocess.Popen(['bash', 'scripts/run-report.sh'], env=env, start_new_session=True)
            try:
                if process.wait(timeout=seconds) == 0:
                    text = Path('final_summary.txt').read_text()
                    validate_summary(text, now=datetime.now(HKT))
                    payload = json.loads(Path('stock_signals.json').read_text())
                    reviewed_underlyings = len(build_reviews(payload, now=datetime.now(HKT)))
                    if reviewed_underlyings:
                        status = 'complete'
                        reason = 'COMPLETE'
                    else:
                        reason = 'TACTICAL_REVIEW_INCOMPLETE'
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            except (OSError, ValueError):
                pass
    if status != 'complete':
        Path('final_summary.txt').write_text(fallback_summary(now=datetime.now(HKT), public_option_audit=public_options, reason=reason))
    # Independent research-only option scan; never authorizes a live trade.
    # Missing manual/verified chain leaves an explicit NO_CHAIN_DATA audit artifact.
    try:
        from agents.opportunity_selector import generate
        if not before_start:
            generate()
    except (OSError, ValueError, TypeError) as exc:
        print('Opportunity scan unavailable:', type(exc).__name__)
    Path('daily_research_status.txt').write_text(status)
    Path('daily_research_status.json').write_text(json.dumps({
        'date': now.date().isoformat(), 'started_at': now.isoformat(), 'status': status,
        'reason': reason, 'api_calls': budget.snapshot()['calls'],
        'reviewed_underlyings': reviewed_underlyings,
        'research_deadline': deadline.isoformat()}, ensure_ascii=False))
    print('Daily research status:', status, '; usage ledger recorded.')


if __name__ == '__main__':
    run()

