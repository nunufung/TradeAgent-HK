"""Four actual analyst reports + conservative option-rule decisions (read-only)."""
from __future__ import annotations

import argparse
from datetime import datetime, time
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from linked_stock_analysis import ANALYSTS, allowed_option_types

HKT = ZoneInfo('Asia/Hong_Kong')
LABELS = {'market': '技術／市場', 'social': '情緒', 'news': '新聞', 'fundamentals': '基本面'}
PENDING_RULES = [
    '重要支持／阻力與行使價安全邊際未經行情驗證',
    'IV 相對歷史高低及 Premium 吸引力未完成核實',
    '到期前業績、政策、重大公告及長假期日曆未完整查核',
    '帳戶現金、接貨能力、保證金 buffer／Call 持股覆蓋未確認',
]


def select_shortlist(audit: dict, *, limit: int = 3, now: datetime | None = None) -> list[str]:
    """Reserve one blue chip and one tech stock, then prioritize actual company news."""
    now = (now or datetime.now(HKT)).astimezone(HKT)
    stocks = audit.get('watchlist', [])
    stocks = [row for row in stocks if re.fullmatch(r'\d{4,5}', str(row.get('code', ''))) and int(row['code']) > 0]
    counts = {row['code']: sum(row['code'] in story.get('direct_codes', []) for story in audit.get('selected', [])) for row in stocks}
    # Rotate ties on quiet news days; never default every briefing to 700.
    codes = sorted(counts)
    rotation = now.date().toordinal() % max(1, len(codes))
    codes = codes[rotation:] + codes[:rotation]
    order = {code: index for index, code in enumerate(codes)}
    ranked = sorted(stocks, key=lambda row: (-counts[row['code']], order[row['code']]))
    chosen = []
    for group in ('bluechip', 'technology'):
        row = next((row for row in ranked if row.get('group') == group), None)
        if row is not None and len(chosen) < limit:
            chosen.append(row['code'])
    for row in ranked:
        if len(chosen) >= limit:
            break
        if row['code'] not in chosen:
            chosen.append(row['code'])
    return [f'HK.{int(code):05d}' for code in chosen]


def _excerpt(value: object, limit: int = 450) -> str:
    if not isinstance(value, str) or not value.strip():
        return '報告缺失，禁止以此開啟方向閘門。'
    text = re.sub(r'\s+', ' ', value).strip()
    return text[:limit] + ('…（完整論證見 stock_analysis.md）' if len(text) > limit else '')


def _in_entry_window(now: datetime) -> bool:
    return now.weekday() < 5 and (time(10) <= now.time() < time(12) or time(13) <= now.time() < time(16))


def build_recommendations(payload: dict, *, option_audit: dict | None = None,
                          now: datetime | None = None) -> dict:
    now = (now or datetime.now(HKT)).astimezone(HKT)
    same_day = payload.get('date') == now.date().isoformat()
    stocks = []
    for underlying, signal in payload.get('signals', {}).items():
        if not re.fullmatch(r'HK\.\d{5}', underlying) or not isinstance(signal, dict):
            continue
        complete = same_day and set(payload.get('analyst_set', [])) == set(ANALYSTS) and signal.get('analysis_complete') is True and all(
            signal.get('analysts', {}).get(name, {}).get('complete') is True
            and isinstance(signal.get('reports', {}).get(name), str)
            and bool(signal['reports'][name].strip()) for name in ANALYSTS)
        rating = signal.get('rating', 'REVIEW')
        sides = allowed_option_types(rating, complete)
        strategy = ('Short Put（條件式）' if sides == ['PUT'] else
                    'Short Call（條件式，須確認覆蓋或風險承受）' if sides == ['CALL'] else '不做')
        stocks.append({'underlying': underlying, 'rating': rating, 'complete': complete,
                       'strategy': strategy, 'allowed_option_types': sides,
                       'evidence': {name: _excerpt(signal.get('reports', {}).get(name)) for name in ANALYSTS},
                       'decision': _excerpt(signal.get('decision'), 1000)})
    directional = [row for row in stocks if row['allowed_option_types']]
    reasons, main_option = [], None
    if not directional:
        action = '不做'
        reasons.append('沒有同日、四份完整分析及明確方向通過正股閘門；不強行選期權。')
    elif not _in_entry_window(now):
        action = '等待'
        reasons.append('只在香港交易日 10:00 後正常交易時段考慮；晨報只提供研究方向，不能開倉。交易日／半日市仍須核實。')
    elif option_audit is None:
        action = '等待'
        reasons.append('尚未收到 Mac OpenD 的即時 Bid/Ask、Delta、IV、OI、成交量及實際初始保證金；等待 Futu 更新。')
    else:
        try:
            generated = datetime.fromisoformat(option_audit['generated_at']).astimezone(HKT)
            age = (now - generated).total_seconds() / 60
            fresh = generated.date() == now.date() and -1 <= age <= 30
        except (KeyError, TypeError, ValueError):
            fresh = False
        if not fresh:
            action = '等待'
            reasons.append('Futu 掃描缺失或超過三十分鐘；不能沿用舊報價作開倉推薦。')
        else:
            from agents.screening_agent import ScreeningAgent
            from main import SCREENING_RULES
            allowed = {row['underlying']: set(row['allowed_option_types']) for row in stocks}
            candidates = ScreeningAgent(SCREENING_RULES).screen(option_audit.get('candidates', []), allowed_option_types=allowed)
            if candidates:
                # One research candidate, never call a partial screen fully compliant.
                main_option = candidates[0]
                action = '等待'
                reasons.append('最多列一張主候選；行情與保證金數值閘門通過，但完整守則仍未核實，未達「做」條件。')
            elif option_audit.get('errors'):
                action = '等待'
                reasons.append('OpenD／保證金／行情資料有缺口，不能把查詢失敗等同市場無機會。')
            else:
                action = '不做'
                reasons.append('沒有合約通過正股方向及實際行情／保證金硬性條件。')
    if directional:
        reasons.append('完整守則須另完成以下查核，不能只憑模型評級或數值篩選開倉。')
        reasons.extend(PENDING_RULES)
    return {'generated_at': now.isoformat(), 'analysis_date': payload.get('date'),
            'action': action, 'stocks': stocks, 'main_option': main_option, 'reasons': reasons,
            'risk_review_complete': False, 'rule_source': '02-HKEX-Options-Trading-Rules.docx'}


def render_recommendations(result: dict, *, market_audit: dict | None = None) -> str:
    audit = market_audit or {}
    names = {f"HK.{int(row['code']):05d}": row.get('name', '') for row in audit.get('watchlist', [])}
    lines = ['# 四分析員推薦與期權紀律', f"分析時間：{result['generated_at']}（香港時間）",
             f"## 今日結論：{result['action']}",
             '評級來自實際 TradingAgents 四分析員、投資辯論及風控整合；以下摘錄是各分析員原文，未將新聞篩選器冒充四分析員。',
             '正股評級屬研究意見；模型文字及所述價位須核對原始行情。四份報告齊備不等於所有資料均已驗證。']
    lines.extend(f'- {reason}' for reason in result['reasons'])
    for stock in result['stocks']:
        code = stock['underlying']
        lines += [f"## {code} {names.get(code, '')}｜{stock['rating']}",
                  f"策略建議：{stock['strategy']}；四分析員同日齊備：{'是' if stock['complete'] else '否'}。"]
        for name in ANALYSTS:
            lines.append(f"{LABELS[name]}分析員原文摘錄：{stock['evidence'][name]}")
        lines += [f"綜合決策原文摘錄：{stock['decision']}"]
    opt = result['main_option']
    if opt:
        premium = float(opt['bid']) * float(opt['lot_size'])
        mid = (float(opt['bid']) + float(opt['ask'])) / 2
        ratio = float(opt['short_required_im']) / premium
        lines += ['## 唯一主候選（等待完整風控覆核，尚未推薦開倉）',
                  f"{opt['underlying']} {opt['option_type']}｜合約 {opt['option_code']}｜行使價 {opt['strike']}｜到期 {opt['expiry']}｜{opt['dte']} DTE",
                  f"正股 {opt['spot']}｜Bid/Ask {opt['bid']}/{opt['ask']}｜Mid {mid:.3f}｜Delta {opt['delta']}｜IV {opt['iv']}%",
                  f"Volume {opt['volume']}｜OI {opt['open_interest']}｜報價時間 {opt['quote_time']} HKT",
                  f"每張 Gross Premium（按 Bid，未扣費用）HK${premium:,.2f}｜初始保證金 HK${opt['short_required_im']:,.2f}｜Margin/Premium {ratio:.2f}x",
                  'Bid 只作保守收入參考，不能保證成交；重新核實即時報價及完整風控後才訂限價。']
    else:
        lines += ['## 主推期權：暫無', '未有合格且完成完整風控覆核的即時合約，不填虛構行使價、Premium 或目標價。']
    lines += ['## 開倉與退出守則',
              '每日最多一張主推；DTE 優先 21–45 日；保留現有 |Delta| ≤ 0.10、Spread ≤ 30%、OI ≥ 100、Volume ≥ 1、Margin/Premium ≤ 10x、報價 ≤ 30 分鐘的數值閘門。數值閘門不代替完整守則。',
              'Short Put 必須低於重要支持位並有接貨能力；Short Call 必須高於重要阻力位並確認持股覆蓋或風險能力。',
              '開倉後盈利達原收 Premium 的 50–70% 必須止盈；虧損超過原收 Premium 的 100% 必須平倉、減倉或在守則內 Roll。',
              'DTE <21 日優先檢查平倉／減倉／Roll；<14 日提高警戒；<7 日通常不開新裸倉；<3 日沒有完整交收計劃應退出。',
              'Roll 須原判斷仍有效、新行使價更安全、新 DTE 21–45 日、額外收入補償風險、總倉位不擴大及保證金可控。',
              '尚未取得當前持倉、開倉 Premium 及帳戶 buffer，不能對實際倉位聲稱已達止盈／止蝕／Roll；此處為條件規則。']
    return '\n\n'.join(lines) + '\n'


def write_recommendations(payload: dict, *, directory: Path = Path('.'), option_audit: dict | None = None,
                          market_audit: dict | None = None, now: datetime | None = None) -> dict:
    result = build_recommendations(payload, option_audit=option_audit, now=now)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'recommendations.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (directory/'recommendations.md').write_text(render_recommendations(result, market_audit=market_audit), encoding='utf-8')
    from final_summary import render_final_summary
    (directory/'final_summary.txt').write_text(render_final_summary(payload, market_audit=market_audit, option_audit=option_audit, now=now), encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--select', action='store_true')
    parser.add_argument('--market', default='market_briefing.json')
    parser.add_argument('--signals', default='stock_signals.json')
    parser.add_argument('--options', default='option_screen.json')
    args = parser.parse_args()
    market = json.loads(Path(args.market).read_text()) if Path(args.market).is_file() else {}
    if args.select:
        codes = select_shortlist(market)
        if not codes:
            raise SystemExit('No valid market shortlist; refusing a fixed ticker fallback.')
        print('\n'.join(codes))
        return
    payload = json.loads(Path(args.signals).read_text())
    options = json.loads(Path(args.options).read_text()) if Path(args.options).is_file() else None
    result = write_recommendations(payload, option_audit=options, market_audit=market)
    print(f"Recommendation report ready: {len(result['stocks'])} stocks; action={result['action']}")


if __name__ == '__main__':
    import sys
    sys.excepthook = lambda exc_type, *_: print(f'Recommendations unavailable ({exc_type.__name__}); sensitive details omitted.')
    main()
