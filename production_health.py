"""Audit TradeAgent-HK morning using durable GitHub artifact evidence.

Observer only: no API keys, trade orders, Telegram sends, or paid LLM calls.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

HKT = ZoneInfo('Asia/Hong_Kong')


def read_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return None


def evaluate(manifest: dict, base: Path):
    day = manifest['date']
    flags = manifest.get('artifacts') or {}
    errors, warnings = [], []
    receipt = read_json(base / 'receipt' / 'delivery_receipt.json')
    valid_receipt = (
        bool(flags.get('delivery_receipt'))
        and isinstance(receipt, dict)
        and receipt.get('date') == day
        and type(receipt.get('message_id')) is int
        and receipt['message_id'] > 0
        and isinstance(receipt.get('sent_at'), str)
    )
    if valid_receipt:
        try:
            sent = datetime.fromisoformat(receipt['sent_at'])
            valid_receipt = (sent.tzinfo is not None and sent.astimezone(HKT).date().isoformat() == day)
        except ValueError:
            valid_receipt = False
    if not valid_receipt:
        errors.append('No valid same-day Telegram API delivery receipt. A green Actions run is not proof of delivery.')
        if flags.get('delivery_claim'):
            warnings.append('A delivery claim exists without validated receipt; do not auto-retry an ambiguous send.')

    status_file = base / 'morning_report' / 'daily_research_status.txt'
    research = status_file.read_text(encoding='utf-8').strip() if status_file.is_file() else 'unknown'
    if research != 'complete':
        errors.append('Morning research was not confirmed complete (status: ' + research[:32] + ').')

    ledger = read_json(base / 'ledger' / 'daily_token_usage.json')
    api = {'provider_configured': 'DeepSeek', 'model_configured': 'deepseek-chat',
           'measured_calls': None, 'actual_tokens': None, 'prompt_tokens': None,
           'completion_tokens': None, 'cache_hit_tokens': None, 'unconfirmed_calls': None}
    if isinstance(ledger, dict) and ledger.get('date') == day:
        for key, destination in [('calls', 'measured_calls'), ('actual_tokens', 'actual_tokens'),
                                 ('prompt_tokens', 'prompt_tokens'), ('completion_tokens', 'completion_tokens'),
                                 ('cache_hit_tokens', 'cache_hit_tokens'), ('unconfirmed_calls', 'unconfirmed_calls')]:
            if type(ledger.get(key)) is int and ledger[key] >= 0:
                api[destination] = ledger[key]
        if api['unconfirmed_calls']:
            warnings.append('Some DeepSeek calls have uncertain usage; ledger reserves remain charged.')
    else:
        warnings.append('No validated same-day DeepSeek usage ledger available.')

    futu = manifest.get('futu_latest')
    futu_status = 'unverified'
    if isinstance(futu, dict):
        futu_status = 'latest_run_' + str(futu.get('conclusion') or futu.get('status') or 'unknown')
        if futu.get('conclusion') == 'success':
            try:
                last = datetime.fromisoformat(str(futu['created_at']).replace('Z', '+00:00'))
                checked = datetime.fromisoformat(manifest['checked_at_utc'].replace('Z', '+00:00'))
                if last.tzinfo and checked.tzinfo and 0 <= (checked - last).total_seconds() <= 7 * 86400:
                    futu_status = 'recent_smoke_test_passed'
                else:
                    futu_status = 'stale_smoke_test'
            except (KeyError, ValueError, TypeError):
                futu_status = 'undated_smoke_test'
    if futu_status != 'recent_smoke_test_passed':
        warnings.append('Futu OpenD connectivity not verified by a recent successful Mac smoke test.')

    return {
        'date_hkt': day,
        'checked_at_utc': manifest['checked_at_utc'],
        'overall': 'FAILED' if errors else ('WARNING' if warnings else 'PASS'),
        'telegram': 'api_acknowledged' if valid_receipt else 'unconfirmed',
        'telegram_message_id': receipt['message_id'] if valid_receipt else None,
        'research': research,
        'deepseek': api,
        'futu_opend': futu_status,
        'errors': errors,
        'warnings': warnings,
        'limits': 'Telegram receipt confirms API acceptance, not device notification/read status; Futu last smoke test is not continuous quote access.',
    }


def format_markdown(result: dict):
    d = result['deepseek']
    lines = [f"# TradeAgent-HK Production Health — {result['date_hkt']} HKT",
             f"**Audit result: {result['overall']}**",
             f"- Telegram: {result['telegram']} (API receipt message ID: {result['telegram_message_id'] or 'N/A'})",
             f"- Morning research: {result['research']}",
             f"- Daily LLM configured: {d['provider_configured']} / {d['model_configured']}",
             f"- API calls: {d['measured_calls']}; measured tokens: {d['actual_tokens']}; cache-hit tokens: {d['cache_hit_tokens']}; uncertain calls: {d['unconfirmed_calls']}",
             f"- Futu OpenD: {result['futu_opend']}"]
    lines += ['', '## Errors'] + ([f'- {x}' for x in result['errors']] or ['- None'])
    lines += ['', '## Warnings'] + ([f'- {x}' for x in result['warnings']] or ['- None'])
    lines += ['', result['limits']]
    return '\n'.join(lines) + '\n'


def main():
    root = Path(os.environ.get('TAHK_HEALTH_INPUT', 'audit_inputs'))
    manifest = read_json(root / 'manifest.json')
    if not isinstance(manifest, dict) or not manifest.get('date') or not manifest.get('checked_at_utc'):
        raise SystemExit('Missing audit manifest: no health claim can be made.')
    result = evaluate(manifest, root)
    Path('production_health.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    md = format_markdown(result)
    Path('production_health.md').write_text(md, encoding='utf-8')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as handle:
            handle.write(md)
    print(md)
    return 1 if result['overall'] == 'FAILED' else 0


if __name__ == '__main__':
    sys.exit(main())
