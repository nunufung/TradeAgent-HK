"""Independent short-horizon option judgment from the existing four reports."""
from datetime import date, datetime
import json
import math
import re
from zoneinfo import ZoneInfo

HKT = ZoneInfo('Asia/Hong_Kong')
ROLES = ('market', 'social', 'news', 'fundamentals')
STRATEGIES = {'BULLISH': 'BULL_PUT_CREDIT', 'BEARISH': 'BEAR_CALL_CREDIT'}
LABELS = {'BULLISH': 'Bull Put Spread（賣Put＋買較低Put）',
          'BEARISH': 'Bear Call Spread（賣Call＋買較高Call）'}
CONTEXT = '''User-authorized short-term option policy, 2026-11-02:
Keep the existing stock rating and strict core-income scanner unchanged. Separately evaluate a 1–3 trading-day option thesis, preferably using 7–30 DTE defined-risk spreads. Hold on the stock's investment horizon does not veto a short-term option opportunity.
All four analysts must actually review the evidence, but do not require unanimous agreement. Each analyst should address near-term direction, opposing evidence and missing data. The final risk manager weighs the four independent findings: technicals, news and sentiment drive the short horizon; fundamentals remain relevant opposing evidence. DTE/Delta preferences, missing historical IV rank and long-term valuation are considerations, not automatic vetoes on a CONDITIONAL idea. Never invent a vote count or a numeric score.
Fresh executable two-leg quotes, realistic liquidity/fees, bounded loss, event/assignment review and account capacity remain requirements before entry, after 10:00 HKT. Do not authorize a naked call, guess contract terms, quote a fill or invent margin. Missing execution data must be disclosed, not confused with NO_EDGE. Do not force a daily trade.
The final Portfolio Manager response MUST include exactly one JSON object inside <option_review>...</option_review>, alongside its required stock rating. If using the structured PortfolioDecision schema, put this tagged object at the end of the investment_thesis STRING; do not add a schema field. The final tagged review is exempt from the short debate-response character target. Keys: bias (BULLISH, BEARISH or NO_EDGE), thesis, entry_trigger, invalidation, risk, confidence (high, medium or low). Use concise Traditional Chinese, at most 100 characters per text field. risk must include the strongest opposing evidence or uncertainty. NO_EDGE must explain why in thesis. Numeric triggers only if verified; otherwise state the observable condition and missing level. The proposed holding period is 1–3 trading days, not until expiry. No extra model call is needed.
'''


def attach_option_context(graph):
    original = graph.resolve_instrument_context
    def enriched(ticker, asset_type='stock', trade_date=None):
        return original(ticker, asset_type, trade_date) + '\n\n' + CONTEXT
    graph.resolve_instrument_context = enriched


def parse_review(text):
    if not isinstance(text, str):
        return None
    blocks = re.findall(r'<option_review>\s*(.*?)\s*</option_review>', text, re.S)
    if len(blocks) != 1 or len(blocks[0]) > 3000:
        return None
    try:
        raw = json.loads(blocks[0])
        if not isinstance(raw, dict) or raw.get('bias') not in (*STRATEGIES, 'NO_EDGE'):
            return None
        fields = ('thesis',) if raw['bias'] == 'NO_EDGE' else ('thesis', 'entry_trigger', 'invalidation', 'risk')
        if not all(isinstance(raw.get(k), str) and 0 < len(raw[k].strip()) <= 180 for k in fields):
            return None
        if raw.get('confidence') not in ('high', 'medium', 'low'):
            return None
        return {k: raw[k].strip() for k in ('bias', 'confidence', *fields)}
    except (ValueError, TypeError):
        return None


def build_reviews(payload, *, now=None):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    if payload.get('date') != now.date().isoformat() or set(payload.get('analyst_set', [])) != set(ROLES):
        return []
    rows = []
    for underlying, signal in payload.get('signals', {}).items():
        if not re.fullmatch(r'HK\.\d{5}', underlying) or not isinstance(signal, dict):
            continue
        if signal.get('analysis_complete') is not True or not all(
            signal.get('analysts', {}).get(role, {}).get('complete') is True
            and isinstance(signal.get('reports', {}).get(role), str)
            and bool(signal['reports'][role].strip()) for role in ROLES):
            continue
        review = parse_review(signal.get('decision'))
        if review:
            rows.append({**review, 'underlying': underlying, 'stock_rating': signal.get('rating', 'REVIEW'),
                         'strategy': STRATEGIES.get(review['bias']),
                         'status': 'NO_EDGE' if review['bias'] == 'NO_EDGE' else 'CONDITIONAL',
                         'execution_eligible': False})
    return sorted(rows, key=lambda r: (r['status'] == 'NO_EDGE', {'high': 0, 'medium': 1, 'low': 2}[r['confidence']]))


def contract_reference(audit, review, now):
    """Pair historical strikes only; settlement values cannot establish a fill."""
    try:
        if not audit or audit.get('status') != 'EOD_RESEARCH_ONLY' or not 0 <= (now.date() - date.fromisoformat(audit['as_of'])).days <= 7:
            return '行使價／到期日待配；優先7–30 DTE，Delta及IV按實際報價綜合評估。'
        side = 'PUT' if review['bias'] == 'BULLISH' else 'CALL'
        rows = []
        for row in audit.get('contracts', []):
            try:
                dte = (date.fromisoformat(row['expiry']) - now.date()).days
                numeric = [float(row[k]) for k in ('strike', 'spot_close', 'settlement_price', 'volume', 'open_interest')]
                strike, spot, settlement, volume, oi = numeric
                otm = strike < spot if side == 'PUT' else strike > spot
                if (row['underlying'] == review['underlying'] and row['option_type'] == side
                        and all(math.isfinite(x) and x > 0 for x in numeric)
                        and 7 <= dte <= 30 and otm and volume >= 1 and oi >= 100):
                    rows.append(row)
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
        for short in sorted(rows, key=lambda r: r['volume'], reverse=True):
            longs = [r for r in rows if r['expiry'] == short['expiry'] and
                     (r['strike'] < short['strike'] if side == 'PUT' else r['strike'] > short['strike'])]
            if longs:
                long = min(longs, key=lambda r: abs(r['strike'] - short['strike']))
                return (f"合約參考：{side} 賣{short['strike']:g}／買{long['strike']:g}｜{short['expiry']}；"
                        f"HKEX {audit['as_of']}收市結算{short['settlement_price']:g}／{long['settlement_price']:g}，非成交價；乘數及最大虧損待核。")
        return '行使價／到期日待配；未取得可配對的有效保護腿，不提出裸倉替代。'
    except (KeyError, TypeError, ValueError):
        return '行使價／到期日待配；公開合約資料未通過核實。'


def render_review_lines(result, *, public_option_audit=None, now=None):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    reviews = result.get('option_reviews', [])
    ideas = [r for r in reviews if r['status'] == 'CONDITIONAL'][:3]
    lines = ['短線期權綜合判斷：' + ('有條件式提議，持倉目標1–3交易日。' if ideas else '未見短線優勢，今日不勉強開倉。')]
    if not ideas:
        return lines + [r['underlying'] + '：' + r['thesis'] for r in reviews[:3]]
    for index, row in enumerate(ideas):
        label = '首選' if index == 0 else '備選'
        confidence = {'high': '較高', 'medium': '中等', 'low': '較低'}[row['confidence']]
        lines += [f"{label} {row['underlying']}｜{LABELS[row['bias']]}｜正股{row['stock_rating']}｜信心{confidence}（模型判斷）。",
                  '理由：' + row['thesis'], '觸發：' + row['entry_trigger'],
                  '取消／退出：' + row['invalidation'], '分歧／主風險：' + row['risk']]
        if index == 0:
            lines.append(contract_reference(public_option_audit, row, now))
    lines += ['執行：香港交易日10:00後核實兩腿Bid/Ask、流動性、費用、最大虧損、事件／交收及帳戶資金，才決定開倉；以上屬條件式研究。',
              '短線退場：淨收權利金盈利20–30%可止盈（參考）；論點失效或達預設風險額即退出，不持有至到期。止損不保證成交。',
              '原有收息策略仍按21–45 DTE及50–70%止盈獨立評估；未取得持倉成本，不能判定現有倉位退出。']
    return lines


def render_summary(result, *, public_option_audit=None, now=None):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    head = ['TradeAgent-HK｜每日決策摘要', f'研究截至：{now:%Y-%m-%d %H:%M HKT}',
            '以下股票的四份分析已完成；短線期權與正股評級分開判斷。']
    lines = render_review_lines(result, public_option_audit=public_option_audit, now=now)
    # Keep the first idea's full trigger, invalidation and risk ahead of alternatives.
    while len('\n'.join(head + lines)) + 1 > 1200 and any(line.startswith('備選') for line in lines):
        last = max(i for i, line in enumerate(lines) if line.startswith('備選'))
        del lines[last:last + 5]
    return '\n'.join(head + lines) + '\n'
