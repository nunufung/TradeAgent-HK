"""Run the automatic morning research inside one bounded DeepSeek session."""
from datetime import datetime, time
import os
from pathlib import Path
import signal
import subprocess
from daily_budget import Budget, gateway, HKT
from daily_delivery import fallback_summary, validate_summary
from public_option_data import refresh_public_options


def run():
    now = datetime.now(HKT)
    public_options = refresh_public_options(now=now)
    ledger = Path('daily_token_usage.json')
    budget = Budget(ledger, now.date().isoformat())
    deadline = datetime.combine(now.date(), time(7, 15), HKT)
    seconds = min(45 * 60, int((deadline - now).total_seconds()))
    status = 'incomplete'
    if seconds > 0 and os.environ.get('DEEPSEEK_API_KEY'):
        with gateway(budget) as backend:
            env = dict(os.environ, TAHK_BUDGETED_DAILY='1', TAHK_SHORTLIST_LIMIT='2',
                       TRADINGAGENTS_LLM_BACKEND_URL=backend, OPENAI_API_BASE=backend,
                       EVENT_NAME='schedule', REPORT_SCOPE='market')
            process = subprocess.Popen(['bash', 'scripts/run-report.sh'], env=env, start_new_session=True)
            try:
                if process.wait(timeout=seconds) == 0:
                    text = Path('final_summary.txt').read_text()
                    validate_summary(text, now=datetime.now(HKT))
                    status = 'complete'
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
        Path('final_summary.txt').write_text(fallback_summary(now=datetime.now(HKT), public_option_audit=public_options))
    # Independent research-only option scan; never authorizes a live trade.
    # Missing manual/verified chain leaves an explicit NO_CHAIN_DATA audit artifact.
    try:
        from agents.opportunity_selector import generate
        generate()
    except (OSError, ValueError, TypeError) as exc:
        print('Opportunity scan unavailable:', type(exc).__name__)
    Path('daily_research_status.txt').write_text(status)
    print('Daily research status:', status, '; usage ledger recorded.')


if __name__ == '__main__':
    run()
