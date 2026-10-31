"""Official HKEX end-of-day option research. Never an executable quote feed."""
from datetime import date, datetime, timedelta
import html
import json
import math
from pathlib import Path
import re
import time
import urllib.request
from zoneinfo import ZoneInfo

HKT = ZoneInfo('Asia/Hong_Kong')
WATCHLIST = {'HK.00005', 'HK.02388', 'HK.02318', 'HK.00388', 'HK.00700',
             'HK.09988', 'HK.01810', 'HK.01024', 'HK.09999', 'HK.01299', 'HK.03690'}
MONTHS = {name: i for i, name in enumerate(
    ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'), 1)}


def _day(text):
    match = re.fullmatch(r'(\d{1,2})\s*([A-Z]{3})\s*(\d{2}|\d{4})', text)
    if not match:
        raise ValueError('Invalid report date')
    day, month, year = match.groups()
    return date(int(year) + (2000 if len(year) == 2 else 0), MONTHS[month], int(day))


def parse_report(raw, *, now=None):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    text = html.unescape(re.sub(r'<[^>]*>', '', raw))
    stamp = re.search(r'STOCK OPTIONS DAILY MARKET REPORT AS AT (\d{1,2} [A-Z]{3} \d{4})', text)
    if not stamp:
        raise ValueError('Not a stock option report')
    as_of = _day(stamp[1])
    if not 0 <= (now.date() - as_of).days <= 7:
        raise ValueError('Report stale or in the future')
    codes = {}
    for line in text.splitlines():
        match = re.match(r'^([A-Z0-9]{3})\s+(.+?)\s+\((\d{5})\)\s+[\d,]+\s', line)
        if match and 'ADJ' not in match[2]:
            codes[match[1]] = ('HK.' + match[3], match[2].strip())
    current, class_code, spot, rows = None, None, None, []
    for line in text.splitlines():
        heading = re.match(r'^CLASS ([A-Z0-9]{3}) - .+?CLOSING PRICE HK\$\s*([\d.]+)', line)
        if line.startswith('CLASS '):
            current, spot = None, None
        if heading:
            current, spot = codes.get(heading[1]), float(heading[2])
            class_code = heading[1]
            continue
        parts = line.split()
        if not current or len(parts) != 12 or not re.fullmatch(r'\d{2}[A-Z]{3}\d{2}', parts[0]) or parts[2] not in ('P', 'C'):
            continue
        try:
            expiry = _day(parts[0])
            strike, settlement, iv = (float(parts[i].replace(',', '')) for i in (1, 6, 8))
            volume, oi = (int(parts[i].replace(',', '')) for i in (9, 10))
            if not all(math.isfinite(x) and x >= 0 for x in (strike, settlement, iv, volume, oi, spot)) or strike <= 0 or spot <= 0:
                continue
        except (ValueError, KeyError):
            continue
        rows.append({'underlying': current[0], 'name': current[1], 'hkats_class': class_code,
                     'expiry': expiry.isoformat(), 'strike': strike, 'option_type': 'PUT' if parts[2] == 'P' else 'CALL',
                     'spot_close': spot, 'settlement_price': settlement, 'hkex_report_iv_pct': iv,
                     'volume': volume, 'open_interest': oi})
    if not rows:
        raise ValueError('Report contains no recognized option rows')
    return {'source': 'HKEX official daily market report', 'status': 'EOD_RESEARCH_ONLY',
            'as_of': as_of.isoformat(), 'retrieved_at': now.isoformat(), 'contracts': rows,
            'execution_eligible': False, 'futu_status': 'not_connected_in_cloud'}


def fetch_latest(*, now=None):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    started = time.monotonic()
    # Morning reports use the last completed session, never invent today's close.
    first = now.date() if now.hour >= 17 else now.date() - timedelta(days=1)
    for offset in range(7):
        day = first - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        if time.monotonic() - started > 45:
            break
        url = f'https://www.hkex.com.hk/eng/stat/dmstat/dayrpt/dqe{day:%y%m%d}.htm'
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'TradeAgent-HK research/1.0'})
            with urllib.request.urlopen(request, timeout=12) as response:
                raw = response.read(14_000_001)
            if len(raw) > 14_000_000:
                raise ValueError('Report too large')
            audit = parse_report(raw.decode('latin-1'), now=now)
            if audit['as_of'] != day.isoformat():
                raise ValueError('Report date does not match requested session')
            audit['source_url'] = url
            return audit
        except (OSError, ValueError):
            continue
    raise RuntimeError('Official HKEX option report unavailable within freshness limit')


def refresh_public_options(*, now=None, destination='public_option_data.json'):
    try:
        audit = fetch_latest(now=now)
    except (OSError, ValueError, RuntimeError):
        audit = {'status': 'UNAVAILABLE', 'contracts': [], 'execution_eligible': False,
                 'futu_status': 'not_connected_in_cloud'}
    Path(destination).write_text(json.dumps(audit, ensure_ascii=False, allow_nan=False))
    print('Public options:', audit['status'], '; contracts:', len(audit['contracts']))
    return audit


def brief_lines(audit, *, now=None, underlyings=None):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    try:
        if audit.get('status') != 'EOD_RESEARCH_ONLY' or not 0 <= (now.date() - date.fromisoformat(audit['as_of'])).days <= 7:
            raise ValueError('No fresh public report')
    except (KeyError, TypeError, ValueError):
        return ['公開期權：未取得合適合約／有效日報；不能把缺資料解讀為無交易機會。']
    allowed = set(underlyings) if underlyings else WATCHLIST
    grouped = {}
    for row in audit['contracts']:
        dte = (date.fromisoformat(row['expiry']) - now.date()).days
        otm = row['strike'] < row['spot_close'] if row['option_type'] == 'PUT' else row['strike'] > row['spot_close']
        if row['underlying'] in allowed and 21 <= dte <= 45 and otm and row['volume'] > 0 and row['open_interest'] >= 100 and row['settlement_price'] > 0:
            key = (row['underlying'], row['option_type'])
            if key not in grouped or row['volume'] > grouped[key]['volume']:
                grouped[key] = {**row, 'dte': dte}
    ranked = sorted(grouped.values(), key=lambda x: x['volume'], reverse=True)
    chosen, seen = [], set()
    # Include both sides for research; volume is not a directional trade signal.
    for side in ('PUT', 'CALL'):
        row = next((r for r in ranked if r['option_type'] == side), None)
        if row:
            chosen.append(row)
            seen.add(row['underlying'])
    for row in ranked:
        if row['underlying'] not in seen:
            chosen.append(row)
            seen.add(row['underlying'])
    chosen = (chosen + [row for row in ranked if row not in chosen])[:3]
    lines = [f"公開期權｜HKEX {audit['as_of']} 收市資料，非即時。",
             '合約研究樣本（按成交量，未完成方向及風控）：']
    for row in chosen:
        lines.append(f"{row['underlying']} {row['option_type']} {row['strike']:g}｜{row['expiry']}（{row['dte']}DTE）｜結算價{row['settlement_price']:g}/股｜IV{row['hkex_report_iv_pct']:g}%｜成交{row['volume']}／OI{row['open_interest']}")
    if not chosen:
        lines.append('未取得合適合約：觀察名單內未有21–45 DTE、價外及成交／OI合格樣本。')
    lines.append('結算價非可成交權利金；缺即時Bid/Ask、Delta、保證金、事件及資金覆核，樣本不代表通過開倉守則。')
    return lines


def load_public_options(directory=Path('.')):
    try:
        return json.loads((Path(directory) / 'public_option_data.json').read_text())
    except (OSError, ValueError):
        return None


if __name__ == '__main__':
    refresh_public_options()
