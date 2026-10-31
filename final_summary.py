"""One short, rule-gated Telegram conclusion from the existing four-agent research."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import urllib.request
from zoneinfo import ZoneInfo

HKT = ZoneInfo('Asia/Hong_Kong')
RANK = {'Buy': 0, 'Overweight': 1, 'Hold': 2, 'Underweight': 3, 'Sell': 4}


def _reason(stock: dict) -> str:
    # Quote an existing qualitative thesis, never invent another analyst decision.
    decision = stock.get('decision', '')
    match = re.search(r'Investment Thesis\*{0,2}\s*[:：]?\s*(.+)', decision, re.I)
    if match:
        for sentence in re.split(r'[。；！？]', match.group(1)):
            sentence = re.sub(r'[*#`]', '', sentence).strip()
            sentence = re.sub(r'^[一二三四五六七八九十]+[、．.]\s*', '', sentence)
            relevant = re.search(r'走勢|動能|趨勢|估值|基本面|財務|資產負債|現金流|資訊缺口|技術面|支撐|阻力|新聞|業績|盈利|收入|催化|風險', sentence)
            if relevant and 8 <= len(sentence) <= 40 and not re.search(r'\d|https?://|HK\$|買入|買進|卖出|賣出|開倉|持倉|三方|分析師|研究計畫|交易員|決定方向|是否|待裁決', sentence):
                return '綜合論點：' + sentence + '。'
    rating = stock.get('rating')
    if rating in {'Buy', 'Overweight'}:
        return '綜合偏多，優先研究；入場及風控仍須核實。'
    if rating == 'Hold':
        return '綜合評級中性，先觀望。'
    return '綜合偏淡，暫不增持。' if rating == 'Underweight' else '綜合偏淡，避免新增多頭。'


def render_final_summary(payload: dict, *, market_audit: dict | None = None,
                         option_audit: dict | None = None, now: datetime | None = None,
                         workflow_audit: dict | None = None, overnight_audit: dict | None = None, kronos_line: str | None = None, fincept_line: str | None = None) -> str:
    from market_recommendations import build_recommendations, _in_entry_window
    now = (now or datetime.now(HKT)).astimezone(HKT)
    result = build_recommendations(payload, option_audit=option_audit, now=now)
    from overnight_call import build as build_overnight, brief as overnight_brief
    if overnight_audit is None:
        from trading_workflows import load_inputs
        inputs, _ = load_inputs()
        overnight_audit = build_overnight(inputs, now=now)
    overnight_line = overnight_brief(overnight_audit)
    market = market_audit or {}
    if not market.get('watchlist'):
        path = Path(__file__).with_name('market_watchlist.json')
        market = json.loads(path.read_text()) if path.is_file() else {}
        market['watchlist'] = market.get('stocks', [])
    names = {f"HK.{int(row['code']):05d}": row.get('name', '') for row in market.get('watchlist', [])}
    stamp = payload.get('date', '未提供日期')
    try:
        generated = datetime.fromisoformat(payload['generated_at']).astimezone(HKT)
        stamp = generated.strftime('%Y-%m-%d %H:%M HKT')
    except (KeyError, TypeError, ValueError):
        stamp += ' HKT（未提供時間）'
    eligible = sorted([row for row in result['stocks'] if row['complete'] and row['rating'] in RANK], key=lambda row: RANK[row['rating']])
    bullish = [row for row in eligible if row['rating'] in {'Buy', 'Overweight'}]
    # Both directions matter for options; a bullish stock must not hide a call candidate.
    chosen = eligible[:3]

    plans = []
    for row in chosen:
        code = row['underlying']
        if row['allowed_option_types'] == ['PUT']:
            plans.append(f"{code}：Short Put；行使價須低於已核實支持，跌穿支持取消。")
        elif row['allowed_option_types'] == ['CALL']:
            plans.append(f"{code}：Short Call；行使價須高於已核實阻力，突破取消；先核對持股覆蓋／風險。")
    plan_lines = ['期權研究候選（方向，非開倉指令）：'] + plans if plans else [
        '期權研究候選：未有同日四分析員完整研究及明確方向；不強行配合約。']
    opt = result['main_option']
    if option_audit is None:
        blocker = '資料缺口：缺期權鏈；行使價、到期日、Bid/Ask、IV、Delta、成交量／OI及保證金未取得，不能判定無機會。'
    elif opt:
        blocker = '待核實：支持／阻力、相對IV、事件及帳戶資金；數值合格未代表可開倉。'
    else:
        blocker = '合約篩選：' + result['reasons'][0][:100]
        if not _in_entry_window(now):
            blocker += '；盤前合約尚未完成即時覆核，不代表市場無機會。'
    plan_lines += [blocker, '入場準備：21–45 DTE、|Delta|≤0.10；10:00後覆核報價、事件、支持／阻力及資金，才判斷開倉。']

    def label(row):
        code = row['underlying']
        return f"{int(code.split('.')[1]):04d} {names.get(code, '')}".strip()

    lines = ['TradeAgent-HK｜每日決策摘要', f'研究截至：{stamp}｜四分析員及風控整合，屬研究意見。', '']
    if kronos_line:
        lines.append(kronos_line)
    if fincept_line:
        lines.append(fincept_line)
    extra = '（交易時段外）' if result['action'] == '等待' and not _in_entry_window(now) else ''
    status = ('無方向候選' if not any(row['allowed_option_types'] for row in result['stocks']) else
              '資料不足（缺期權鏈）' if option_audit is None else
              '主候選待核' if opt else '合約待覆核／未合格')
    lines.append(f"期權：{status}{extra}，目前不開新倉。")
    lines += plan_lines
    lines.append('持倉處理：先檢查止盈／止蝕及DTE；未取得當前持倉、成本及平倉報價，不能判定持有、減倉或平倉。')
    lines.append('')
    if any(stock.get('book_skills') for stock in payload.get('signals', {}).values()):
        lines.append('書籍風控：已加入 Psychology of Money 原則；期權硬性守則優先。')
    if bullish:
        lines.append('正股：優先研究 ' + '、'.join(label(row) for row in chosen) + '。')
    elif eligible:
        lines.append('正股：今日沒有新增買入推薦；以下為觀望／風險重點。')
    else:
        lines.append('正股：未有同日四分析員完整研究，暫不推薦。')
    for stock in chosen:
        lines.append(f"• {label(stock)}（{stock['rating']}）：{_reason(stock)}")
    if any(row['allowed_option_types'] == ['PUT'] for row in chosen):
        lines.append('條件式期權方向：偏多股票研究 Short Put（賣 Put）。')
    if any(row['allowed_option_types'] == ['CALL'] for row in chosen):
        lines.append('期權研究方向：Short Call；正股減持評級不構成開倉指令，須核實持股覆蓋及合約風控。')
    lines.append('')
    if opt:
        strategy = 'Short Put' if opt['option_type'] == 'PUT' else 'Short Call'
        premium = float(opt['bid']) * float(opt['lot_size'])
        ratio = float(opt['short_required_im']) / premium
        lines += [f"唯一主候選（未通過完整守則）：{opt['underlying']} {strategy}｜{opt['option_code']}｜行使價 {opt['strike']}｜到期 {opt['expiry']}（{opt['dte']} DTE）",
                  f"Bid/Ask {opt['bid']}/{opt['ask']}｜Delta {opt['delta']}｜Margin/Premium {ratio:.1f}x｜報價 {opt['quote_time']} HKT",
                  f"IV {opt['iv']}｜成交量 {opt.get('volume', opt.get('vol', '待核'))}｜OI {opt.get('open_interest', opt.get('oi', '待核'))}；低Delta不代表損失有限，須核對Gamma／Vega。",
                  '數值閘門通過；支持／阻力、相對 IV、事件日曆及帳戶資金風控仍待核實。']
    else:
        reason = '缺期權鏈，未能選定實際合約。' if option_audit is None else result['reasons'][0][:75]
        lines.append('主推合約：暫無。' + reason)
    lines.append('原策略守則：21–45 DTE、|Delta|≤0.10、Margin/Premium≤10x；如開倉，盈利達原 Premium 50–70% 止盈，虧損>原 Premium 100%須平倉／減倉／合規 Roll。')
    lines.append(overnight_line)
    if workflow_audit is not None:
        from trading_workflows import brief_lines
        workflow_lines = brief_lines(workflow_audit)
        combined = '\n'.join(lines + [''] + workflow_lines) + '\n'
        if len(combined) <= 1200:
            return combined
        # Keep the action, contract identifier, gates and all six modules within
        # the delivery limit. Full evidence remains in recommendations.md.
        compact = [lines[0], lines[1], f"期權：{status}{extra}；目前不開新倉。"] + plan_lines
        compact.append('持倉處理：缺當前持倉、成本及平倉報價，未能判定退出觸發。')
        if opt:
            compact.append(f"主候選（待核）：{str(opt['option_code'])[:40]}｜{opt['strike']}｜{opt['expiry']}｜{opt['dte']} DTE")
        else:
            compact.append('主推合約：暫無；詳見上述資料缺口／篩選原因。')
        if kronos_line:
            compact.append(kronos_line)
        if fincept_line:
            compact.append(fincept_line)
        compact += [line[:42] + ('…' if len(line) > 42 else '') for line in workflow_lines] + [lines[-2], overnight_line]
        return '\n'.join(compact) + '\n'
    return '\n'.join(lines) + '\n'


def send_text(text: str, *, token: str | None = None, chat: str | None = None) -> None:
    token = token if token is not None else os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    chat = chat if chat is not None else os.getenv('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat:
        raise RuntimeError('Telegram credentials are missing.')
    if not text.strip() or len(text.encode('utf-16-le')) // 2 > 3900:
        raise RuntimeError('Final summary is empty or too long; refusing a truncated conclusion.')
    try:
        request = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',
                                         data=json.dumps({'chat_id': chat, 'text': text, 'disable_web_page_preview': True}).encode(),
                                         headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read(100_000))
        if result.get('ok') is not True:
            raise ValueError('Telegram rejected message')
    except Exception:
        raise RuntimeError('Telegram delivery failed; sensitive details omitted.') from None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', default='.')
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args()
    root = Path(args.directory)
    payload = json.loads((root/'stock_signals.json').read_text())
    market = json.loads((root/'market_briefing.json').read_text()) if (root/'market_briefing.json').is_file() else None
    options = json.loads((root/'option_screen.json').read_text()) if (root/'option_screen.json').is_file() else None
    from trading_workflows import load_inputs, build_workflows
    from market_recommendations import build_recommendations
    inputs, status = load_inputs()
    workflows = build_workflows(payload, build_recommendations(payload, option_audit=options), inputs=inputs, input_status=status)
    from kronos_report import brief
    from fincept_report import brief as fincept_brief
    text = render_final_summary(payload, market_audit=market, option_audit=options, workflow_audit=workflows, kronos_line=brief(root/'kronos_forecast.json'), fincept_line=fincept_brief(root/'fincept_forecast.json'))
    if args.send:
        send_text(text)
        print('Final text summary sent to Telegram.')
    else:
        print(text, end='')


if __name__ == '__main__':
    import sys
    sys.excepthook = lambda exc_type, *_: print(f'Final summary failed ({exc_type.__name__}); sensitive details omitted.')
    main()


