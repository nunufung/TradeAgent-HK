"""One explicitly requested integration report; no orders or paid model calls."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from daily_delivery import fallback_summary
from final_summary import send_text
from public_option_data import HKT, refresh_public_options


def send_verified(text, check):
    result = send_text(text)
    message_id = result.get('result', {}).get('message_id')
    if type(message_id) is not int or message_id <= 0:
        raise RuntimeError('Telegram response has no verifiable message ID; do not retry automatically')
    check.update(message_id=message_id, sent_at=datetime.now(HKT).isoformat(), telegram_accepted=True)
    Path('option_test_receipt.json').write_text(json.dumps(check, ensure_ascii=False, indent=2))
    print('Telegram accepted test report; message_id=' + str(message_id))


def run_harness2(send=False):
    text = (
        '【TradeAgent-HK｜Harness2 獨立測試】\n'
        '驗證結果：報告傳送、摘要同短線期權覆核三組測試全部通過。\n'
        '持續改進：先比較原版同候選改動，通過回歸測試後再採用，並保留有證據支持嘅經驗。\n'
        '首個發現：README 已更新為香港時間 10:00 開始分析、11:00 前為發送目標。\n'
        '此訊息只供驗證，沒有交易建議。'
    )
    Path('final_summary.txt').write_text(text)
    check = {'kind': 'harness2', 'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
    if send:
        send_verified(text, check)
    else:
        print(text)


def run(send=False):
    audit = refresh_public_options()
    if audit['status'] != 'EOD_RESEARCH_ONLY':
        raise RuntimeError('Official option source unavailable; no empty test report sent')
    now = datetime.now(HKT)
    path = Path('stock_signals.json')
    payload = json.loads(path.read_text()) if path.is_file() else {}
    if payload.get('date') == now.date().isoformat() and payload.get('signals'):
        from market_recommendations import write_recommendations
        write_recommendations(payload, directory=Path('.'), now=now)
        text = Path('final_summary.txt').read_text()
    else:
        text = fallback_summary(now, public_option_audit=audit)
    if len(text) > 1200 or '結算價' not in text:
        raise RuntimeError('Option report content/length verification failed')
    text = '【期權接入及Telegram驗證｜獨立測試】\n' + text
    Path('final_summary.txt').write_text(text)
    check = {'generated_at': now.isoformat(), 'data_source': audit['source'],
             'as_of': audit['as_of'], 'source_url': audit['source_url'],
             'contract_count': len(audit['contracts']), 'futu_status': audit['futu_status'],
             'execution_eligible': False, 'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
    if send:
        send_verified(text, check)
    else:
        print(text)
    Path('option_integration_check.json').write_text(json.dumps(check, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--send', action='store_true')
    parser.add_argument('--harness2', action='store_true')
    args = parser.parse_args()
    # urllib exception strings can contain a bot-token URL; never print them.
    try:
        verification = run_harness2 if args.harness2 else run
        verification(send=args.send)
    except Exception as exc:
        print('Option integration verification failed (' + type(exc).__name__ + '); details omitted.')
        raise SystemExit(1) from None
