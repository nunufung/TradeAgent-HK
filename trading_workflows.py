"""Six daily research modules, reusing analyst evidence without extra API calls.

Optional private inputs are processed locally and never inserted into LLM context.
No orders, data fetching, simulation fabrication or raw account logs.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

HKT = ZoneInfo('Asia/Hong_Kong')
RUNTIME = Path(__file__).parent / 'skills/analyze-hk-trading-workflows/references/daily-runtime.md'
LABELS = ('交易點子', '技術分析', '新聞策略', '策略回測', '組合風險', '交易日誌')


def attach_workflow_context(graph):
    raw = RUNTIME.read_bytes()
    if len(raw) > 3500:
        raise ValueError('Workflow context exceeds bounded input size')
    original = graph.resolve_instrument_context
    def enriched(ticker, asset_type='stock', trade_date=None):
        return original(ticker, asset_type, trade_date) + '\n\n' + raw.decode()
    graph.resolve_instrument_context = enriched
    return {'name': 'analyze-hk-trading-workflows', 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def load_inputs():
    """Explicit opt-in JSON only; never discover or persist private source files."""
    raw = os.environ.get('TAHK_RESEARCH_INPUT_JSON', '')
    path = os.environ.get('TAHK_RESEARCH_INPUT_PATH', '')
    try:
        if not raw and path:
            p = Path(path)
            if p.stat().st_size > 40000:
                raise ValueError('Oversized')
            raw = p.read_text(encoding='utf-8')
        if not raw:
            return {}, 'missing'
        if len(raw.encode()) > 40000:
            raise ValueError('Oversized')
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get('schema_version') != 1:
            raise ValueError('Invalid schema')
        return data, 'provided'
    except (OSError, ValueError, TypeError):
        return {}, 'invalid'  # Never log raw input, private paths or exceptions.


def number(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or abs(value) > 1e15
            or (value != 0 and abs(value) < 1e-12)):
        raise ValueError('Finite monetary value within supported range required')
    return float(value)


def timestamp(value, now):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None or stamp > now:
        raise ValueError('Timestamp must have timezone and not be in the future')
    return stamp.astimezone(HKT)


def closed_trades(rows, now):
    if not isinstance(rows, list) or not rows or len(rows) > 1000:
        raise ValueError('Missing trades')
    valid, ids = [], set()
    for row in rows:
        if not isinstance(row, dict) or row.get('status') != 'closed':
            raise ValueError('Only completed trades accepted')
        trade_id = str(row['id'])
        if not trade_id or trade_id in ids:
            raise ValueError('Duplicate trade')
        ids.add(trade_id)
        entry, exit_ = timestamp(row['entry_at'], now), timestamp(row['exit_at'], now)
        if exit_ < entry:
            raise ValueError('Invalid trade dates')
        pnl, capital = number(row['net_pnl']), number(row['capital_at_risk'])
        if capital <= 0:
            raise ValueError('Positive return denominator required')
        valid.append({**row, '_exit': exit_, '_pnl': pnl, '_return': pnl / capital})
    return sorted(valid, key=lambda row: row['_exit'])


def trade_metrics(trades):
    profits = sum(max(0, row['_pnl']) for row in trades)
    losses = -sum(min(0, row['_pnl']) for row in trades)
    return {'count': len(trades), 'win_rate': sum(row['_pnl'] > 0 for row in trades) / len(trades),
            'breakeven_count': sum(row['_pnl'] == 0 for row in trades),
            'profit_factor': profits / losses if losses else None,
            'mean_net_return': sum(row['_return'] for row in trades) / len(trades)}


def backtest(data, now):
    # Summarize an existing run. Do not imply that accepting a file validates a strategy.
    required = ('strategy', 'universe', 'period', 'cost_model', 'execution_model',
                'data_source', 'out_of_sample', 'benchmark', 'instrument_type')
    if not all(isinstance(data.get(k), str) and data[k].strip() for k in required):
        raise ValueError('Backtest methodology missing')
    if data.get('costs_included') is not True or data.get('equity_marked_to_market') is not True:
        raise ValueError('Costs and marked-to-market equity required')
    if data['instrument_type'] not in ('stock', 'option'):
        raise ValueError('Unknown instrument')
    if data['instrument_type'] == 'option' and not all(data.get(k) is True for k in ('historical_option_quotes', 'contract_terms_checked')):
        raise ValueError('Option historical evidence required')
    trades = closed_trades(data['trades'], now)
    equity = data['equity']
    if not isinstance(equity, list) or not 2 <= len(equity) <= 5000:
        raise ValueError('Equity history required')
    peak, drawdown, previous = 0., 0., None
    for row in equity:
        stamp, value = timestamp(row['at'], now), number(row['value'])
        if previous is not None and stamp <= previous:
            raise ValueError('Equity dates must be strictly increasing')
        if previous is None and value <= 0:
            raise ValueError('Initial equity must be positive')
        if previous is None and stamp > min(timestamp(t['entry_at'], now) for t in trades):
            raise ValueError('Equity must cover trade entries')
        peak = max(peak, value)
        drawdown = max(drawdown, (peak - value) / peak)
        previous = stamp
    if previous < trades[-1]['_exit']:
        raise ValueError('Equity must cover trade exits')
    result = trade_metrics(trades)
    result['max_drawdown'] = drawdown
    pf = 'N/A' if result['profit_factor'] is None else f"{result['profit_factor']:.2f}"
    return (f"已提供回測{len(trades)}筆：勝率{result['win_rate']:.0%}、PF {pf}、回撤{drawdown:.1%}、均報{result['mean_net_return']:.1%}；未獨立驗證。", result)


def portfolio(data, now):
    if timestamp(data['as_of'], now).date() != now.date() or data.get('complete') is not True:
        raise ValueError('Current complete portfolio required')
    nav, cash = number(data['nav_hkd']), number(data['cash_hkd'])
    holdings = data['holdings']
    if nav <= 0 or not isinstance(holdings, list) or len(holdings) > 200:
        raise ValueError('Portfolio values missing')
    values, issuer = [], Counter()
    for row in holdings:
        if row['asset_type'] not in ('stock', 'option') or not row.get('underlying'):
            raise ValueError('Unknown holding')
        value = number(row['market_value_hkd'])
        values.append(value)
        issuer[row['underlying']] += value
    if abs(cash + sum(values) - nav) > max(1, nav * .001):
        raise ValueError('NAV does not reconcile')
    # Net market values are NOT option risk exposures. Do not report them as such.
    if any(row['asset_type'] == 'option' for row in holdings):
        return '有期權：須完整重估、Greeks及保證金壓測；跌市20%損益N/A。', {'holdings_count': len(holdings), 'stress_pnl': None}
    concentration = max((abs(value) for value in issuer.values()), default=0) / nav
    gross = sum(abs(v) for v in values) / nav
    # Explicit stock-only parallel shock; not a forecast of market-beta response.
    shock_pct = -0.2 * sum(values) / nav
    return (f"最大發行人淨值比{concentration:.0%}；總曝險{gross:.0%}；全股票同跌20%假設淨值變動{shock_pct:.1%}，非大市預測。",
            {'largest_issuer_nav_ratio': concentration, 'gross_nav_ratio': gross,
             'parallel_stock_shock_nav_return': shock_pct})


def journal(data, now):
    if timestamp(data['as_of'], now).date() != now.date():
        raise ValueError('Current journal snapshot required')
    if data.get('costs_included') is not True:
        raise ValueError('Net costs required')
    trades = closed_trades(data['trades'], now)[-20:]
    known = {'late_exit': ('到退出條件即處理', '下次檢查逾期退出次數'),
             'oversize': ('下單前核對預設倉位上限', '下次檢查超額次數'),
             'unplanned_entry': ('先記錄入場及失效條件', '下次檢查無計劃入場次數')}
    counts = Counter()
    for row in trades:
        violations = row.get('rule_violations', [])
        if not isinstance(violations, list) or any(v not in known for v in violations):
            raise ValueError('Invalid documented violation')
        counts.update(set(violations))
    rules = [{'trigger': key, 'action': action, 'metric': metric,
              'observed_count': counts[key], 'provisional': not bool(counts[key])}
             for key, (action, metric) in known.items()]
    metrics = trade_metrics(trades)
    metrics['rules'] = rules
    metrics['missed_opportunities'] = 'N/A: contemporaneous signals not supplied'
    metrics['behavioral_bias'] = 'Not inferred from P/L alone'
    return (f"最近{len(trades)}筆；已記錄違規{sum(counts.values())}次；三項紀律：準時退出、控倉、先訂計劃（無違規證據者屬暫定）。", metrics)


def build_workflows(payload, recommendations, *, inputs=None, input_status='missing', now=None):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    inputs = inputs or {}
    stocks = [r for r in recommendations.get('stocks', []) if r['complete']]
    rank = {'Buy': 0, 'Overweight': 1, 'Hold': 2, 'Underweight': 3, 'Sell': 4, 'REVIEW': 5}
    stocks.sort(key=lambda row: rank.get(row['rating'], 5))
    modules = []
    for i, domain in enumerate((None, 'market', 'news')):
        evidence = []
        for row in stocks[:5]:
            source = row['decision_summary'] if domain is None else row['research_summary'][domain]
            evidence.append({'underlying': row['underlying'], 'excerpt': source,
                             'source': f"stock_signals.json:signals.{row['underlying']}." + ('decision' if domain is None else f'reports.{domain}')})
        summary = '缺同日完整四分析員研究；等待。'
        if evidence:
            if domain is None:
                summary = '研究候選：' + '、'.join(r['underlying'] + ' ' + r['rating'] for r in stocks[:5]) + '；價位待核。'
            else:
                summary = evidence[0]['underlying'] + ' 原研究摘錄：' + evidence[0]['excerpt']
        modules.append({'name': LABELS[i], 'status': 'research_only' if evidence else 'blocked',
                        'summary': summary, 'evidence': evidence,
                        'limitation': '原分析員研究摘錄；非獨立行情驗證，未補造價位或波動區間。'})
    for name, key, fn, missing in (
        (LABELS[3], 'backtest', backtest, '缺歷史回測成交、淨值及方法；勝率/PF/回撤/均報N/A。'),
        (LABELS[4], 'portfolio', portfolio, '缺當日完整持倉及資金；集中度與跌市20%損益N/A。'),
        (LABELS[5], 'journal', journal, '缺最近20筆完整交易；錯誤、偏誤及個人化規則待核。')):
        module = {'name': name, 'status': 'blocked', 'summary': missing}
        if input_status == 'invalid':
            module['summary'] = '私人輸入格式無效；' + missing
        elif key in inputs:
            try:
                summary, metrics = fn(inputs[key], now)
                json.dumps(metrics, allow_nan=False)  # Reject non-finite derived metrics per module.
                module.update(status='computed_from_supplied_data', summary=summary, metrics=metrics)
            except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
                module['summary'] = '輸入缺失、過期或不完整；' + missing
        modules.append(module)
    return {'generated_at': now.isoformat(), 'modules': modules,
            'extra_model_calls': 0, 'input_status': input_status}


def brief_lines(audit):
    lines = []
    for module in audit['modules']:
        text = ' '.join(module['summary'].split())
        # Label incomplete excerpts so no truncated source is mistaken for a full conclusion.
        text = text if len(text) <= 72 else text[:65] + '…（節錄）'
        lines.append(module['name'] + '：' + text)
    return lines


def render_workflows(audit):
    lines = ['## 六項研究流程', '研究時間：' + audit['generated_at']]
    for module in audit['modules']:
        lines += ['### ' + module['name'], '狀態：' + module['status'], module['summary']]
        for evidence in module.get('evidence', []):
            lines.append(evidence['underlying'] + '：' + evidence['excerpt'] + '\n來源：' + evidence['source'])
        if module.get('limitation'):
            lines.append(module['limitation'])
        for rule in module.get('metrics', {}).get('rules', []):
            lines.append(('暫定規則：' if rule['provisional'] else '記錄支持規則：') + rule['action'] + '；' + rule['metric'])
    return '\n\n'.join(lines) + '\n'
