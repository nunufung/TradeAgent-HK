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


def research_summary(value: object, limit: int = 180) -> str:
    """Extract a short source-backed conclusion, without generating new claims."""
    if not isinstance(value, str) or not value.strip():
        return '研究資料不足，未能形成可靠判斷。'
    text = value.strip()
    # Prefer the author's conclusion over introductions and company profiles.
    match = re.search(r'(?:Executive Summary|執行摘要|核心結論摘要|結論摘要)\*{0,2}\s*[:：]?\s*', text, re.I)
    if match:
        text = text[match.end():]
        text = re.split(r'\n\s*#{1,6}\s|\*\*Investment Thesis\*\*|\nInvestment Thesis\s*:', text, maxsplit=1, flags=re.I)[0]
    paragraphs = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', '|', '---')):
            continue
        if re.match(r'(Overall Sentiment|Confidence|Rating|分析日期|報告日期|資料截止|觀察期間|資料擷取時間)\s*[:：]', line, re.I):
            continue
        line = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', line)
        line = re.sub(r'[`*#]', '', line)
        line = re.sub(r'^[-•\d一二三四五六七八九十]+[、.)．\s]+', '', line)
        if re.search(r'get_\w+|company_match|direct_candidates|HTTPError|FRED_API_KEY|NO_DATA_AVAILABLE|\bhttps?://', line):
            # Implementation metadata belongs in the research source, not the brief.
            continue
        paragraphs.append(line)
    clean = re.sub(r'\s+', ' ', ' '.join(paragraphs)).strip()
    if not clean:
        return '有效研究內容不足；資料覆蓋及原始來源仍待核實。'
    sentences = re.split(r'(?<=[。！？])\s*', clean)
    selected = ''
    for sentence in sentences:
        if len(selected + sentence) > limit:
            break
        selected += sentence
        if selected and len(selected) >= 65:
            break
    return selected or clean[:limit].rstrip('，、； ') + '…'


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
                       'decision': _excerpt(signal.get('decision'), 1000),
                       'research_summary': {name: research_summary(signal.get('reports', {}).get(name)) for name in ANALYSTS},
                       'decision_summary': research_summary(signal.get('decision'), 220)})
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
    try:
        stamp = datetime.fromisoformat(result['generated_at']).astimezone(HKT).strftime('%Y-%m-%d %H:%M HKT')
    except (ValueError, TypeError):
        stamp = '研究時間未確認'
    lines = ['# 港股及期權每日研究簡報', f'研究截至：{stamp}',
             '## 決策摘要', f"今日結論：{result['action']}｜暫不新增期權倉位。",
             '主推合約：暫無；以下如列候選，僅供研究覆核。',
             f"決策依據：{result['reasons'][0]}" if result.get('reasons') else '決策依據：資料待核實。',
             '正股評級與期權交易分開評估；研究方向不構成開倉指令。',
             '## 期權評估']
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
        lines += ['## 主推期權：暫無', '尚未確認通過完整風控覆核的合約，因此不提供具體入場價格。']
    lines += ['## 股票研究｜四分析員推薦與期權紀律']
    ratings = {'Buy': '買入', 'Overweight': '增持', 'Hold': '持有／中性', 'Underweight': '減持', 'Sell': '賣出', 'REVIEW': '待覆核'}
    for stock in result['stocks']:
        code = stock['underlying']
        lines += [f"### {int(code.split('.')[1]):04d} {names.get(code, '')}｜{ratings.get(stock['rating'], stock['rating'])}（{stock['rating']}）",
                  f"研究狀態：{'同日四份分析齊備' if stock['complete'] else '研究未齊備，暫不形成交易方向'}。",
                  '綜合觀點：' + stock.get('decision_summary', research_summary(stock.get('decision')))]
        summaries = stock.get('research_summary', {})
        for name in ANALYSTS:
            lines.append(f"- {LABELS[name]}：{summaries.get(name, research_summary(stock.get('evidence', {}).get(name)))}")
        lines.append(f"期權研究方向：{stock['strategy']}。仍須獨立核實合約條件及帳戶風控，不能由正股評級直接推導開倉。")
    lines += ['## 執行計劃',
              '入場條件：香港交易日 10:00 後報價穩定；DTE 優先 21–45 日；|Delta| ≤ 0.10、買賣差價比例 ≤ 30%、未平倉合約 ≥ 100、成交量 ≥ 1、保證金／權利金 ≤ 10x，報價不超過 30 分鐘。全部數值條件通過後，仍須完成事件及帳戶風控覆核。',
              '取消條件：關鍵資料缺失、買賣差價過闊、保證金效率不合格、技術結構失效，或事件及資金風控未通過時，不新增倉位。',
              '策略條件：Short Put 行使價須低於重要支持位，並具備接貨能力；Short Call 須高於重要阻力位，並核實持股覆蓋或風險承受能力。',
              '止盈條件：盈利達原收權利金的 50–70% 時，優先平倉止盈。',
              '止蝕條件：虧損超過原收權利金的 100% 時，必須平倉、減倉或按守則轉倉，不以加倉攤平處理。',
              '到期管理：DTE <21 日優先評估平倉／減倉／Roll；<14 日提高警戒；<7 日通常不開新裸倉；<3 日沒有完整交收計劃應退出。',
              '轉倉條件：原判斷仍有效、新行使價更安全、新 DTE 回到 21–45 日、額外收入足以補償風險、總倉位不擴大，且保證金可控。',
              '## 資料說明',
              '研究方法：整合技術、情緒、新聞及基本面四分析員，並參考投資辯論與風控結論。主文為原始研究的精簡摘錄，未新增行情或交易判斷；詳細論證保留於原始研究報告。',
              '資料狀態：分析齊備不代表行情及論據已核實；正股價位與估值僅屬研究輸入。行情來源、交易日期及盤中／收市狀態須逐項覆核。',
              '尚待覆核：' + '；'.join(PENDING_RULES) + '。',
              '持倉管理：未取得當前持倉、開倉權利金及帳戶資金餘額，不能判定實際止盈、止蝕或轉倉是否已觸發。']
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

