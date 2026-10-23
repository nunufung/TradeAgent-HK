"""One concise, current-day Telegram message, strictly before 08:00 HKT."""
from datetime import datetime, time
import json
import os
from pathlib import Path
import urllib.request
from zoneinfo import ZoneInfo

HKT = ZoneInfo('Asia/Hong_Kong')

def fallback_summary(now=None):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    return (f'TradeAgent-HK｜每日決策摘要\n研究截至：{now:%Y-%m-%d %H:%M HKT}\n\n'
            '今日結論：等待，不新增期權倉位。\n'
            '本次研究未能在預算或時限內完成，未形成可靠股票及期權推薦。\n'
            '執行原則：10:00 後才評估開倉；DTE 優先 21–45 日，|Delta|≤0.10，保證金／權利金≤10x。\n'
            '持倉管理：盈利達原收權利金 50–70% 優先止盈；虧損超過原收權利金 100% 必須處理。\n'
            '資料狀態：缺失資料未以舊報告或模型推測補足。\n'
            '交易點子：研究未完成。\n技術分析：研究未完成。\n新聞策略：研究未完成。\n'
            '策略回測：N/A，未完成資料覆核。\n組合風險：N/A，未完成持倉覆核。\n'
            '交易日誌：N/A，未完成交易記錄覆核。\n')

def validate_summary(text, *, now=None, recovery=False):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    if not recovery and now.time() >= time(8):
        raise ValueError('08:00 HKT deadline passed; no late morning report.')
    if f'研究截至：{now:%Y-%m-%d}' not in text or len(text) > 1200:
        raise ValueError('Report is stale or exceeds the concise report limit.')
    if recovery:
        return f'【手動補發｜{now:%Y-%m-%d %H:%M HKT}】\n原晨報未成功送達；本訊息並非準時晨報。\n\n' + text.strip()
    return text.strip()

def main():
    # Workflow uploads a durable day-specific delivery claim BEFORE invoking this.
    # Never retry an ambiguous Telegram send: that could deliver duplicate reports.
    if os.environ.get('DAILY_DELIVERY_CLAIMED') != 'true':
        raise RuntimeError('A durable daily delivery claim is required.')
    now = datetime.now(HKT)
    recovery = os.environ.get('DAILY_MANUAL_RECOVERY') == 'true'
    paths = list(Path('morning_report').rglob('final_summary.txt'))
    text = paths[0].read_text() if len(paths) == 1 else fallback_summary(now)
    try:
        text = validate_summary(text,now=now,recovery=recovery)
    except ValueError:
        if not recovery and now.time() >= time(8):
            raise
        text = validate_summary(fallback_summary(now),now=now,recovery=recovery)
    token, chat = os.environ['TELEGRAM_BOT_TOKEN'].strip(), os.environ['TELEGRAM_CHAT_ID'].strip()
    if not recovery and datetime.now(HKT).time() >= time(7, 59, 30):
        raise RuntimeError('Insufficient time for delivery before 08:00 HKT.')
    request = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',
        data=json.dumps({'chat_id':chat,'text':text,'disable_web_page_preview':True}).encode(),
        headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=20) as response:
        result=json.loads(response.read())
    if result.get('ok') is not True:
        raise RuntimeError('Telegram rejected the report.')
    Path('delivery_receipt.json').write_text(json.dumps({'date':now.date().isoformat(),'message_id':result['result']['message_id'],'sent_at':datetime.now(HKT).isoformat()}))
    print('One concise daily report sent.')

if __name__=='__main__':
    import sys
    sys.excepthook=lambda *_:print('Daily delivery stopped; sensitive details omitted.')
    main()

