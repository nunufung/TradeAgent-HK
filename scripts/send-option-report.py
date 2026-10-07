"""Send the linked report without logging Telegram URLs, credentials or response bodies."""
import json
import os
from pathlib import Path
import sys

import requests

sys.excepthook = lambda *_: print('Telegram delivery failed; sensitive details omitted.')
token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
chat = os.getenv('TELEGRAM_CHAT_ID', '').strip()
if not token or not chat:
    raise SystemExit('Telegram credentials are missing.')
result = json.loads(Path('recommendations.json').read_text())
caption = f"TradeAgent-HK 四分析員／Futu 期權更新｜今日：{result['action']}\n" + '\n'.join(result['reasons'][:2])
files = sorted(Path('option_pdf').glob('*.pdf'))
if files:
    for path in files:
        with path.open('rb') as document:
            response = requests.post(f'https://api.telegram.org/bot{token}/sendDocument',
                                     data={'chat_id': chat, 'caption': caption[:1000]},
                                     files={'document': (path.name, document, 'application/pdf')}, timeout=60)
        if response.status_code != 200 or not response.json().get('ok'):
            raise SystemExit('Telegram PDF delivery failed; sensitive response omitted.')
    print('Four-analyst option PDF sent to Telegram.')
else:
    print('Option PDF unavailable; the separate final-summary step will send concise text.')
