"""Isolated worker for verified local Fincept Python scripts. JSON on stdin/stdout."""
from datetime import date, timedelta
import importlib.util
import json
import math
from pathlib import Path
import sys

VENDOR = Path(__file__).resolve().parent / 'third_party' / 'fincept'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, VENDOR / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def technicals(bars):
    if not bars:
        return {'status': 'unavailable', 'reason': 'Daily OHLCV not supplied'}
    module = load('fincept_technicals', 'compute_technicals.py')
    result = json.loads(module.compute_all_technicals(json.dumps(bars)))
    if result.get('success') is not True:
        return {'status': 'unavailable', 'reason': 'Upstream technical computation failed'}
    import pandas as pd
    frame = pd.DataFrame(bars)
    vol = float(frame.close.pct_change(fill_method=None).iloc[-20:].std(ddof=1) * math.sqrt(252))
    latest = result['data'][-1]
    keys = {'rsi_14': 'rsi', 'sma_20': 'sma_20', 'macd': 'macd', 'atr_14': 'atr'}
    out = {key: float(latest[source]) for key, source in keys.items()}
    if not all(math.isfinite(value) for value in [vol, *out.values()]):
        return {'status': 'unavailable', 'reason': 'Indicator warmup incomplete'}
    return {'status': 'available', **out, 'realized_vol_20': vol, 'as_of': bars[-1]['date'],
            'observations': len(bars), 'volatility_convention': '20 close-to-close returns; sample std; sqrt(252)',
            'price_convention': 'OHLCV as supplied; public fetch uses adjusted daily bars'}


def option_model(row, module):
    if 'risk_free_rate' not in row or 'dividend_yield' not in row:
        return {'status': 'unavailable', 'reason': 'Explicit decimal risk_free_rate and dividend_yield required'}
    if not module.HAS_SCIPY:
        return {'status': 'unavailable', 'reason': 'SciPy dependency unavailable'}
    s, k, t, r, iv, q = (row['spot'], row['strike'], row['dte'] / 365,
                          row['risk_free_rate'], row['iv'], row['dividend_yield'])
    typ = row['option_type'].lower()
    price = module.black_scholes_price(s, k, t, r, iv, q, typ)
    greeks = module.black_scholes_greeks(s, k, t, r, iv, q, typ)
    scenarios = []
    for shock, vol_shift in [(-.10, .05), (0., 0.), (.10, .05)]:
        value = module.black_scholes_price(s * (1 + shock), k, max(row['dte'] - 1, 0) / 365,
                                           r, iv + vol_shift, q, typ)
        scenarios.append({'spot_change': shock, 'iv_change': vol_shift, 'days_elapsed': 1,
                          'pnl_one_short_contract': round((row['bid'] - value) * row['lot_size'], 2)})
    return {'status': 'available', 'name': 'European Black-Scholes-Merton diagnostic',
            'price_per_share': price, 'iv_decimal': iv, 'risk_free_rate': r, 'dividend_yield': q,
            'option_greeks': greeks,
            'short_one_contract_greeks': {key: -row['lot_size'] * value for key, value in greeks.items()},
            'units': {'delta': 'per HKD 1 spot', 'gamma': 'per HKD 1 spot squared',
                      'vega': 'per 1 percentage point IV', 'theta': 'per calendar day',
                      'rho': 'per 1 percentage point rate'},
            'scenarios': scenarios,
            'limitations': 'European model with continuous yield; no early exercise, discrete dividends, jumps or costs. '
                           'Hypothetical one short contract sold at supplied bid; not a live valuation or verified fill. '
                           'Never substitutes for broker Greeks or entry eligibility.'}


def analyze(data):
    try:
        tech = technicals(data['bars'])
    except (ImportError, ValueError, KeyError, TypeError, IndexError):
        tech = {'status': 'unavailable', 'reason': 'Technical dependency or computation unavailable'}
    result = {'technicals': tech, 'options': [], 'volatility_by_expiry': []}
    rows = data['options']
    if rows:
        pricing = load('fincept_pricing', 'derivatives_pricing.py')
        chart = load('fincept_payoff', 'Analytics/options/strategy_chart.py')
        smile = load('fincept_smile', 'Analytics/options/iv_smile.py')
        for row in rows:
            payoff = chart.compute({'spot': row['spot'], 'days_to_expiry': row['dte'],
                'spot_range': {'min': row['spot'] * .5, 'max': row['spot'] * 1.5, 'points': 51},
                'legs': [{'type': row['option_type'], 'side': 'SELL', 'qty': 1,
                          'lot_size': row['lot_size'], 'strike': row['strike'], 'premium': row['bid']}]})
            result['options'].append({'status': 'available', 'input_index': row['input_index'],
                'option_code': row['option_code'], 'quote_time': row['quote_time'],
                'model': option_model(row, pricing), 'payoff': {
                    'scope': 'hypothetical one short contract at expiry before costs',
                    'premium_one_contract': payoff['net_premium'], 'curve': payoff['payoff'],
                    'minimum_sampled_pnl': payoff['max_loss'], 'loss_unbounded': row['option_type'] == 'CALL',
                    'limitations': 'Sampled prices are not maximum loss; no assignment timing, financing or transaction costs.'}})
        for underlying, expiry in sorted({(row['underlying'], row['expiry']) for row in rows}):
            group = [row for row in rows if row['expiry'] == expiry and row['underlying'] == underlying]
            if len({row['spot'] for row in group}) != 1:
                result['volatility_by_expiry'].append({'expiry': expiry, 'status': 'unavailable', 'reason': 'Inconsistent underlying spot'})
                continue
            chain = {}
            for row in group:
                chain.setdefault(row['strike'], {'strike': row['strike']})['pe_iv' if row['option_type'] == 'PUT' else 'ce_iv'] = row['iv']
            raw = smile.compute({'spot': group[0]['spot'], 'expiry': expiry, 'days_to_expiry': group[0]['dte'],
                                 'iv_is_decimal': True, 'chain': list(chain.values())})
            result['volatility_by_expiry'].append({'underlying': underlying, 'expiry': expiry,
                'status': 'available' if raw.get('skew') is not None else 'unavailable',
                'atm_iv': raw.get('atm_iv'), 'put_minus_call_skew': raw.get('skew'),
                'method': 'quoted IV only; nearest strikes around 5% OTM, not delta matched'})
    result['status'] = 'available' if result['technicals']['status'] == 'available' or result['options'] else 'unavailable'
    return result


def history(data):
    import yfinance as yf
    end = date.fromisoformat(data['trade_date'])
    frame = yf.Ticker(data['ticker']).history(start=(end - timedelta(days=400)).isoformat(),
        end=end.isoformat(), interval='1d', auto_adjust=True, timeout=5, raise_errors=True)
    bars = [{'date': index.date().isoformat(), **{key.lower(): float(row[key])
              for key in ('Open', 'High', 'Low', 'Close', 'Volume')}} for index, row in frame.tail(260).iterrows()
            if index.date() < end]
    return {'status': 'available', 'ticker': data['ticker'], 'source': 'Yahoo Finance via yfinance; adjusted completed daily bars', 'bars': bars}


if __name__ == '__main__':
    try:
        data = json.loads(sys.stdin.read(120_001))
        output = {'analyze': analyze, 'history': history}[sys.argv[1]](data)
        print(json.dumps(output, allow_nan=False))
    except Exception:
        print(json.dumps({'status': 'unavailable', 'reason': 'Analytics or public history unavailable'}))
