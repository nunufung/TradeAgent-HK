"""Independent surge-day short-call research; no orders or extra model calls."""
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo

from trading_workflows import number, timestamp

HKT = ZoneInfo('Asia/Hong_Kong')
STRATEGY = 'SURGE_OVERNIGHT_SHORT_CALL'
POLICY = ('急升隔夜Call（候選研究）：Delta<0.10，翌日按原權利金20–30%止盈；'
          '止蝕／時間退出待定，不開新倉。')


def build(inputs, *, now=None):
    now = (now or datetime.now(HKT)).astimezone(HKT)
    result = {'strategy': STRATEGY, 'generated_at': now.isoformat(),
              'status': 'NO_MANUAL_DATA', 'execution_eligible': False,
              'take_profit_pct': [20, 30], 'stop_loss_pct': None,
              'time_exit_hkt': None, 'surge_threshold_pct': 5,
              'candidates': [], 'rejected': 0,
              'limitations': '未回測；急升5%屬暫定研究門檻；止蝕、翌日退出時間及倉位上限待定。'}
    data = inputs.get('overnight_call') if isinstance(inputs, dict) else None
    if data is None:
        return result
    try:
        if not isinstance(data, dict):
            raise ValueError('invalid strategy input')
        threshold = number(data.get('surge_threshold_pct', 5))
        rows = data.get('candidates', [])
        if not 0 < threshold <= 100 or not isinstance(rows, list) or len(rows) > 100:
            raise ValueError('invalid strategy input')
        result['surge_threshold_pct'] = threshold
        result['limitations'] = (f'未回測；急升{threshold:g}%屬研究門檻；'
                                '止蝕、翌日退出時間及倉位上限待定。')
    except (ValueError, TypeError, OverflowError):
        result['status'] = 'INVALID_MANUAL_DATA'
        return result
    # Morning reports cannot confirm a same-day surge or authorize an overnight entry.
    from market_recommendations import _in_entry_window
    if not _in_entry_window(now):
        result['status'] = 'WAIT_SESSION'
        return result
    for row in rows:
        try:
            if not isinstance(row, dict):
                raise ValueError('invalid row')
            underlying, code = row['underlying'], row['option_code']
            if (not isinstance(underlying, str) or not re.fullmatch(r'HK\.\d{5}', underlying)
                    or int(underlying[3:]) == 0 or not isinstance(code, str)
                    or not re.fullmatch(r'[A-Za-z0-9._-]{1,40}', code)):
                raise ValueError('contract identity')
            if (row.get('verified') is not True or not isinstance(row.get('source'), str)
                    or not row['source'].strip()):
                raise ValueError('unverified quote')
            quoted = timestamp(row['quote_time'], now)
            if quoted.date() != now.date() or (now - quoted).total_seconds() > 1800:
                raise ValueError('stale quote')
            delta = number(row['delta'])
            if row.get('option_type') != 'CALL' or not 0 < delta < .10:
                raise ValueError('not a low delta call')
            gain = number(row['stock_change_pct'])
            if gain < threshold:
                raise ValueError('no surge signal')
            spot, strike = number(row['spot']), number(row['strike'])
            bid, ask = number(row['bid']), number(row['ask'])
            if not 0 < spot < strike or not 0 < bid <= ask:
                raise ValueError('invalid price')
            if (ask - bid) / ((ask + bid) / 2) > .20:
                raise ValueError('spread exceeds 20 percent of midpoint')
            lot = number(row['lot_size'])
            oi, volume = number(row['open_interest']), number(row['volume'])
            if lot <= 0 or not lot.is_integer() or oi < 100 or volume < 1 or not oi.is_integer() or not volume.is_integer():
                raise ValueError('invalid liquidity or multiplier')
            expiry = date.fromisoformat(row['expiry'])
            dte = (expiry - now.date()).days
            if dte <= 0:
                raise ValueError('expired or expiry day')
            margin = number(row['initial_margin'])
            if margin <= 0 or margin / (bid * lot) > 10:
                raise ValueError('margin/premium exceeds 10x')
            if (row.get('event_risk') is not False or
                    any(row.get(key) is not True for key in
                        ('iv_reviewed', 'account_risk_reviewed', 'assignment_reviewed'))):
                raise ValueError('risk review missing')
            result['candidates'].append({
                'underlying': underlying, 'option_code': code, 'expiry': expiry.isoformat(),
                'dte': dte, 'strike': strike, 'delta': delta, 'bid': bid, 'ask': ask,
                'stock_change_pct': gain, 'quote_time': quoted.isoformat(),
                'buyback_reference_20pct': round(bid * .8, 6),
                'buyback_reference_30pct': round(bid * .7, 6),
                'stop_loss_pct': None, 'time_exit_hkt': None,
                'execution_eligible': False,
                'risk_note': '裸賣Call理論損失無上限；覆蓋及帳戶承受力須人工覆核。',
                'price_note': '按Bid估算，非實際開倉價；成交後按實收權利金重算並扣費。'})
        except (KeyError, ValueError, TypeError, OverflowError):
            result['rejected'] += 1
    # Preserve supplied order; no unvalidated scoring or forced daily pick.
    result['candidates'] = result['candidates'][:3]
    result['status'] = 'RESEARCH_CANDIDATE' if result['candidates'] else 'NO_ELIGIBLE_CANDIDATE'
    return result


def brief(audit):
    rows = audit.get('candidates', [])
    if rows:
        row = rows[0]
        return (f"急升隔夜Call（候選研究，非開倉）：{row['underlying']} {row['option_code']}｜"
                f"K {row['strike']:g}｜{row['expiry']}｜Delta {row['delta']:g}；翌日20–30%止盈，"
                f"買回參考{row['buyback_reference_20pct']:g}–{row['buyback_reference_30pct']:g}（按Bid，須依實收重算）；止蝕／時間退出待定。")
    statuses = {'NO_MANUAL_DATA': '缺手動行情', 'INVALID_MANUAL_DATA': '手動資料無效',
                'WAIT_SESSION': '盤前／非交易時段，待當日急升及新報價',
                'NO_ELIGIBLE_CANDIDATE': '暫無合格手動候選'}
    return POLICY + statuses.get(audit.get('status'), '資料待核') + '。'
