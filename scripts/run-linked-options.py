"""Reuse same-day cloud analysis or build a fresh shortlist, then read local OpenD."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linked_stock_analysis import analyze, _futu_code, load_market_news
from market_recommendations import select_shortlist, write_recommendations

HKT = ZoneInfo('Asia/Hong_Kong')
FILES = ('market_briefing.json', 'market_candidates.json', 'report_market.md', 'news_market.md',
         'stock_signals.json', 'stock_analysis.md')


def usable_cache(directory: Path, now: datetime) -> bool:
    try:
        payload = json.loads((directory/'stock_signals.json').read_text())
        market = json.loads((directory/'market_briefing.json').read_text())
        generated = datetime.fromisoformat(payload['generated_at']).astimezone(HKT)
        return (payload.get('date') == market.get('date') == now.date().isoformat()
                and generated <= now and 0 < len(payload.get('signals', {})) <= 3
                and all((directory/name).is_file() for name in FILES))
    except (OSError, KeyError, ValueError, TypeError):
        return False


def run() -> None:
    now = datetime.now(HKT)
    raw = os.getenv('TICKERS_INPUT', '').strip()
    cache = Path('market_cache')
    # Previous self-hosted working directory must not supply a stale option quote.
    for filename in ('option_screen.json', 'option_screen.md', 'recommendations.json', 'recommendations.md'):
        Path(filename).unlink(missing_ok=True)
    if not raw and usable_cache(cache, now):
        for name in FILES:
            shutil.copyfile(cache/name, name)
        payload = json.loads(Path('stock_signals.json').read_text())
        tickers = list(payload['signals'])
        print('Using today\'s completed cloud four-analyst research; refreshing OpenD quotes locally.')
    else:
        subprocess.run([sys.executable, 'hk_market_briefing.py'], check=True)
        market = json.loads(Path('market_briefing.json').read_text())
        tickers = [_futu_code(code) for code in raw.split(',')] if raw else select_shortlist(market, now=now)
        if not tickers:
            raise ValueError('No stock shortlist is available')
        payload = analyze(tickers, signal_path=Path('stock_signals.json'), report_path=Path('stock_analysis.md'), news_batch=load_market_news(Path('market_candidates.json')))
    subprocess.run([sys.executable, 'main.py', *tickers, '--stock-signals', 'stock_signals.json',
                    '--output', 'option_screen.md', '--json-output', 'option_screen.json'], check=False)
    # A failed scan emits a safe error audit, so the PDF can explicitly say WAIT.
    if not Path('option_screen.json').is_file():
        raise RuntimeError('Option scan audit missing; refusing to reuse any old quote')
    options = json.loads(Path('option_screen.json').read_text())
    market = json.loads(Path('market_briefing.json').read_text())
    write_recommendations(payload, option_audit=options, market_audit=market)
    fonts = [os.getenv('TAHK_CJK_FONT', ''), '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
             '/Library/Fonts/Arial Unicode.ttf', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf']
    font = next((path for path in fonts if path and Path(path).is_file()), None)
    if not font:
        print('Embedded CJK font not found: PDF unavailable; Telegram will send the explicit recommendation text.')
        return
    subprocess.run([sys.executable, 'generate_pdf.py', '--inputs', 'report_market.md', '--output-dir', 'option_pdf'],
                   env={**os.environ, 'TAHK_CJK_FONT': font}, check=True)


if __name__ == '__main__':
    sys.excepthook = lambda exc_type, *_: print(f'Linked option update failed ({exc_type.__name__}); sensitive details omitted.')
    run()
