"""Bounded, read-only Fincept analytics. Estimates never change execution gates."""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

HKT = ZoneInfo('Asia/Hong_Kong')
ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / 'third_party' / 'fincept'
COMMIT = '0aa46db2a06b8d8d9f91f07090aa214ac02db5c2'
UPSTREAM = {'repository': 'https://github.com/Fincept-Corporation/FinceptTerminal',
            'version': 'v4.5.1', 'commit': COMMIT}


def unavailable(reason: str) -> dict:
    return {'status': 'unavailable', 'reason': reason}


def verify_vendor() -> None:
    """Verify all unmodified upstream bytes before importing any vendor code."""
    manifest = json.loads((VENDOR / 'manifest.json').read_text())
    if manifest['commit'] != COMMIT or len(manifest['files']) != 12:
        raise ValueError('Unrecognized vendor manifest')
    for entry in manifest['files']:
        path = (VENDOR / entry['path']).resolve()
        if VENDOR.resolve() not in path.parents or path.is_symlink():
            raise ValueError('Invalid vendor path')
        raw = path.read_bytes()
        digest = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if digest != entry['git_blob_sha']:
            raise ValueError('Vendor integrity check failed')


def _run_worker(mode: str, payload: dict, timeout: float) -> dict:
    verify_vendor()
    raw = json.dumps(payload, allow_nan=False)
    if len(raw.encode()) > 120_000:
        raise ValueError('Analytics input too large')
    # No shell, remote code, API credentials or document instructions in the worker.
    env = {k: v for k, v in os.environ.items()
           if not re.search(r'KEY|TOKEN|SECRET|PASSWORD', k, re.I)}
    result = subprocess.run([sys.executable, str(ROOT / 'fincept_worker.py'), mode],
                            input=raw, capture_output=True, text=True,
                            timeout=min(max(timeout, .01), 15), env=env, cwd=ROOT)
    if result.returncode or len(result.stdout.encode()) > 120_000:
        raise ValueError('Analytics worker failed')
    data = json.loads(result.stdout, parse_constant=lambda _: None)
    if not isinstance(data, dict) or data.get('status') not in {'available', 'unavailable'}:
        raise ValueError('Invalid analytics response')
    return data


def _finite(value, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError('Expected a number')
    number = float(value)
    if not math.isfinite(number) or (minimum is not None and number < minimum) or (maximum is not None and number > maximum):
        raise ValueError('Number outside valid bounds')
    return number


def _bars(raw, now: datetime) -> list[dict]:
    if not isinstance(raw, list) or not 80 <= len(raw) <= 300:
        raise ValueError('Need 80–300 daily OHLCV bars')
    out, previous = [], None
    for row in raw:
        day = date.fromisoformat(row['date'])
        if day >= now.date() or (previous is not None and day <= previous):
            raise ValueError('Bars must be ordered completed sessions')
        bar = {'date': day.isoformat(), **{key: _finite(row[key], minimum=.000001)
                                         for key in ('open', 'high', 'low', 'close')}}
        bar['volume'] = _finite(row['volume'], minimum=0)
        if not bar['low'] <= min(bar['open'], bar['close']) <= max(bar['open'], bar['close']) <= bar['high']:
            raise ValueError('Inconsistent OHLC')
        out.append(bar)
        previous = day
    if (now.date() - previous).days > 7:
        raise ValueError('Last completed bar is stale')
    return out


def _ticker(raw: str) -> str:
    if not isinstance(raw, str):
        raise ValueError('Hong Kong ticker required')
    text = raw.upper().removeprefix('HK.').removesuffix('.HK')
    if not re.fullmatch(r'\d{1,5}', text) or int(text) <= 0:
        raise ValueError('Invalid Hong Kong ticker')
    return f'{int(text):04d}.HK'


def _option(row: dict, now: datetime, ticker: str) -> dict:
    if not isinstance(row, dict) or row.get('option_type') not in {'PUT', 'CALL'}:
        raise ValueError('Invalid option type')
    if row.get('underlying') is not None and _ticker(row['underlying']) != ticker:
        raise ValueError('Cannot combine different underlyings')
    expiry = date.fromisoformat(row['expiry'])
    dte = (expiry - now.date()).days
    if not 1 <= dte <= 730:
        raise ValueError('Expired or unsupported expiry')
    stamp = datetime.fromisoformat(row['quote_time'])
    # Manual snapshots use the same documented HKT convention as OpenD.
    stamp = stamp.replace(tzinfo=HKT) if stamp.tzinfo is None else stamp.astimezone(HKT)
    if stamp.date() != now.date() or not -1 <= (now - stamp).total_seconds() / 60 <= 30:
        raise ValueError('Quote is stale or future dated')
    if 'dte' in row and _finite(row['dte']) != dte:
        raise ValueError('Expiry and DTE disagree')
    values = {key: _finite(row[key], minimum=.000001) for key in ('spot', 'strike', 'bid', 'ask', 'lot_size')}
    if values['ask'] < values['bid'] or not values['lot_size'].is_integer():
        raise ValueError('Invalid spread or multiplier')
    if row.get('iv_unit') not in {'percent', 'decimal'}:
        raise ValueError('IV units are required')
    iv = _finite(row['iv'], minimum=.000001) / (100 if row['iv_unit'] == 'percent' else 1)
    if iv > 5:
        raise ValueError('IV outside model bounds')
    out = {**values, 'underlying': ticker, 'option_type': row['option_type'], 'expiry': expiry.isoformat(),
           'dte': dte, 'iv': iv, 'quote_time': stamp.isoformat()}
    code = str(row.get('option_code', ''))
    out['option_code'] = code if re.fullmatch(r'[A-Za-z0-9._-]{1,40}', code) else 'unspecified'
    if row.get('risk_free_rate') is not None and row.get('dividend_yield') is not None:
        out['risk_free_rate'] = _finite(row['risk_free_rate'], minimum=-.2, maximum=1)
        out['dividend_yield'] = _finite(row['dividend_yield'], minimum=0, maximum=1)
    return out


def analyze_snapshot(snapshot: dict, *, now: datetime | None = None, timeout: float = 10) -> dict:
    """Analyze manual JSON or broker observations without inventing missing inputs."""
    now = (now or datetime.now(HKT)).astimezone(HKT)
    result = {'status': 'unavailable', 'generated_at': now.isoformat(), 'upstream': UPSTREAM,
              'technicals': unavailable('OHLCV missing or invalid'), 'options': [],
              'volatility_by_expiry': [], 'research_only': True}
    if not isinstance(snapshot, dict):
        return result
    try:
        ticker = _ticker(snapshot['ticker'])
    except (KeyError, TypeError, ValueError):
        result['reason'] = 'One explicit Hong Kong underlying is required per snapshot'
        return result
    result['ticker'] = ticker
    request = {'bars': [], 'options': []}
    try:
        request['bars'] = _bars(snapshot.get('bars'), now)
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    raw_options = snapshot.get('options', [])
    if not isinstance(raw_options, list) or len(raw_options) > 12:
        result['reason'] = 'At most 12 option observations per snapshot'
        return result
    for index, row in enumerate(raw_options):
        try:
            request['options'].append({**_option(row, now, ticker), 'input_index': index})
        except (KeyError, TypeError, ValueError, OverflowError):
            result['options'].append({'input_index': index, **unavailable('Quote, expiry, units or multiplier invalid')})
    if not request['bars'] and not request['options']:
        return result
    try:
        data = _run_worker('analyze', request, timeout)
        result['technicals'] = data.get('technicals', result['technicals'])
        result['options'] = sorted(result['options'] + data.get('options', []), key=lambda item: item['input_index'])
        result['volatility_by_expiry'] = data.get('volatility_by_expiry', [])
        result['status'] = data['status']
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError):
        result['reason'] = 'Fincept unavailable: dependency, integrity, output or timeout failure'
        result['options'] = [{'input_index': i, **unavailable('Analytics worker unavailable')}
                             for i in range(len(raw_options))]
    source = snapshot.get('source')
    if isinstance(source, str):
        result['source'] = source[:120]  # audit only; excluded from LLM context
    return result


def collect_stock_analytics(ticker: str, trade_date: str, *, timeout: float = 12) -> dict:
    """One bounded public daily-history fetch; never fetch an HK options chain."""
    if not re.fullmatch(r'\d{4,5}\.HK', ticker) or trade_date != datetime.now(HKT).date().isoformat():
        return unavailable('Invalid ticker or research date')
    try:
        data = _run_worker('history', {'ticker': ticker, 'trade_date': trade_date}, timeout)
        if data['status'] != 'available':
            return unavailable('Public daily history unavailable')
        return analyze_snapshot(data, timeout=10)
    except (OSError, TypeError, KeyError, ValueError, subprocess.SubprocessError):
        return unavailable('Public daily history unavailable within time limit')


def technical_summary(data: dict, *, now: datetime | None = None) -> str:
    """Bounded numeric context; no source text or vendor instructions enter prompts."""
    now = (now or datetime.now(HKT)).astimezone(HKT)
    tech = data.get('technicals', {})
    try:
        if data.get('status') != 'available' or tech.get('status') != 'available':
            return '量化補充：日線資料不足，未作估算。'
        rsi, vol = _finite(tech['rsi_14'], minimum=0, maximum=100), _finite(tech['realized_vol_20'], minimum=0)
        day = date.fromisoformat(tech['as_of'])
        generated = datetime.fromisoformat(data['generated_at']).astimezone(HKT)
        if generated.date() != now.date() or (generated - now).total_seconds() > 60 or not 1 <= (now.date() - day).days <= 7:
            return '量化補充：日線資料已過時或日期未核實，未沿用舊數值。'
        return f'量化補充：RSI14 {rsi:.1f}；20日年化實現波幅 {vol:.1%}（截至 {day:%m-%d}；非預測）。'
    except (KeyError, TypeError, ValueError, OverflowError):
        return '量化補充：日線資料不足，未作估算。'


def attach_fincept_context(graph, ticker: str, trade_date: str) -> dict:
    """Enrich the existing four analysts, with no additional model calls."""
    if os.getenv('TAHK_FINCEPT_ENABLED', '0') != '1':
        return {'status': 'disabled'}
    data = collect_stock_analytics(ticker, trade_date)
    note = technical_summary(data)
    original = graph.resolve_instrument_context

    def enriched(symbol, asset_type='stock', trade_date=None):
        return original(symbol, asset_type, trade_date) + '\n\n' + note + (
            '\nFincept quantitative research is supplementary. Realized volatility is historical, '
            'not forecast IV or an option edge. Keep all project entry and exit gates.')

    graph.resolve_instrument_context = enriched
    return data
