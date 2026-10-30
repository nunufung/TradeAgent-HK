"""Timestamped, read-only market data. Public fallback never masquerades as Futu."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import math
import re
import time


def normalize_code(raw: str) -> str:
    match = re.fullmatch(r'(?:HK\.)?([0-9]{1,5})(?:\.HK)?', str(raw).strip().upper())
    if not match or not 1 <= int(match[1]) <= 99999:
        raise ValueError('請輸入有效港股代號，例如 700 或 HK.00700。')
    return f'HK.{int(match[1]):05d}'


def finite(value, positive=False):
    try:
        number = float(value)
        return number if math.isfinite(number) and (not positive or number > 0) else None
    except (TypeError, ValueError):
        return None


def sanitize_quote(raw: dict, expected: str) -> dict:
    if raw.get('code') != expected or not finite(raw.get('price'), positive=True):
        raise ValueError('Invalid quote identity or price')
    at = datetime.fromisoformat(str(raw.get('quote_at', '')).replace('Z', '+00:00'))
    if at.tzinfo is None or (at-datetime.now(timezone.utc)).total_seconds() > 300:
        raise ValueError('Invalid quote timestamp')
    retrieved = datetime.fromisoformat(str(raw.get('retrieved_at') or datetime.now(timezone.utc).isoformat()).replace('Z','+00:00'))
    if retrieved.tzinfo is None or (retrieved-datetime.now(timezone.utc)).total_seconds()>300:
        raise ValueError('Invalid retrieval timestamp')
    candles = []
    for row in raw.get('candles', [])[-150:]:
        close = finite(row.get('close'), positive=True)
        day = str(row.get('date', ''))[:10]
        if close and re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
            datetime.strptime(day, '%Y-%m-%d')
            candles.append({'date': day, 'close': close, 'volume': finite(row.get('volume'))})
    candles.sort(key=lambda row: row['date'])
    return {'code': expected, 'name': str(raw.get('name', expected))[:100],
            'source': str(raw.get('source', 'Unknown'))[:40], 'price': float(raw['price']),
            'previous_close': finite(raw.get('previous_close'), positive=True),
            'currency': 'HKD', 'quote_at': at.isoformat(),
            'retrieved_at': retrieved.isoformat(),
            'market_state': str(raw.get('market_state', 'UNKNOWN'))[:40],
            'delay_minutes': finite(raw.get('delay_minutes')), 'candles': candles,
            'source_url': 'https://finance.yahoo.com/quote/'+str(int(expected[3:])).zfill(4)+'.HK/'
                          if raw.get('source') == 'Yahoo Finance' else 'https://openapi.futunn.com/'}


def technical_summary(quote: dict) -> dict:
    closes = [row['close'] for row in quote.get('candles', [])]
    previous = quote.get('previous_close')
    price = quote['price']
    sma = sum(closes[-20:])/20 if len(closes) >= 20 else None
    change = (price/previous-1)*100 if previous else None
    rsi = None
    if len(closes) >= 15:
        changes = [b-a for a,b in zip(closes[-15:-1],closes[-14:])]
        gains = sum(max(x,0) for x in changes)/14
        losses = sum(max(-x,0) for x in changes)/14
        rsi = 100-100/(1+gains/losses) if losses else 100 if gains else 50
    trend = '高於20日均線' if sma and price > sma else '低於20日均線' if sma and price < sma else '均線資料不足或價格持平'
    age = max(0, (datetime.now(timezone.utc)-datetime.fromisoformat(quote['quote_at'])).total_seconds())
    return {'change_pct': change, 'sma20': sma, 'rsi14': rsi,
            'support20': min(closes[-20:]) if closes else None,
            'resistance20': max(closes[-20:]) if closes else None,
            'quote_age_seconds': round(age), 'quote_state': 'STALE_OR_MARKET_CLOSED' if age > 900 else 'RECENT_QUOTE_NOT_REALTIME_GUARANTEED',
            'commentary': f'{trend}。RSI及均線為已取得日線計算；20日範圍按收市價計算。數據可能延遲，不能單憑此確定期權方向。',
            'method': '20-session simple moving average; 14-session simple RSI, not Wilder smoothing.'}


_cache = {}
_public_lock = asyncio.Semaphore(2)
PUBLIC_TIMEOUT_SECONDS = 20


def _fetch_yahoo(code: str) -> dict:
    import yfinance as yf
    ticker = yf.Ticker(str(int(code[3:])).zfill(4)+'.HK')
    history = ticker.history(period='6mo', interval='1d', auto_adjust=False, timeout=8, raise_errors=True)
    if history.empty:
        raise ValueError('Public provider returned no price history')
    meta = ticker.get_history_metadata() or {}
    timestamp = meta.get('regularMarketTime')
    at = (timestamp.to_pydatetime() if hasattr(timestamp,'to_pydatetime') else timestamp) if isinstance(timestamp,datetime) else datetime.fromtimestamp(timestamp, timezone.utc) if timestamp else history.index[-1].to_pydatetime()
    candles = [{'date': index.date().isoformat(), 'close': float(row['Close']), 'volume': finite(row.get('Volume'))}
               for index,row in history.tail(150).iterrows() if finite(row['Close'],positive=True)]
    # chartPreviousClose refers to the start of a multi-month chart, not yesterday.
    completed=[row for row in candles if row['date'] < at.astimezone(history.index.tz).date().isoformat()]
    return sanitize_quote({'code':code, 'name':meta.get('longName') or meta.get('shortName') or code,
        'source':'Yahoo Finance', 'price':meta.get('regularMarketPrice') or candles[-1]['close'],
        'previous_close':meta.get('previousClose') or (completed[-1]['close'] if completed else None),
        'quote_at':at.isoformat(), 'candles':candles, 'delay_minutes':meta.get('exchangeDataDelayedBy'),
        'market_state':meta.get('marketState','UNKNOWN')},code)


async def public_quote(code: str) -> dict:
    cached = _cache.get(code)
    if cached and time.monotonic()-cached[0] < 60:
        return dict(cached[1])
    async with asyncio.timeout(PUBLIC_TIMEOUT_SECONDS):
        async with _public_lock:
            cached = _cache.get(code)
            if cached and time.monotonic()-cached[0] < 60:
                return dict(cached[1])
            result = await asyncio.to_thread(_fetch_yahoo,code)
            if len(_cache) >= 200: _cache.clear()
            _cache[code] = (time.monotonic(), result)
            return dict(result)


async def resolve_quote(raw: str, broker, *, private=False, public=None) -> dict:
    code = normalize_code(raw)
    reason = '請登入擁有者帳戶以使用私人 Futu 連線。'
    if private:
        try:
            result = sanitize_quote(await asyncio.wait_for(broker.quote(code),timeout=11),code)
            age = (datetime.now(timezone.utc)-datetime.fromisoformat(result['quote_at'])).total_seconds()
            if age > 900: raise ValueError('Futu quote is stale')
            result['source'] = 'Futu OpenD'
            result['fallback_reason'] = None
            return result
        except (TimeoutError, ValueError, RuntimeError):
            reason = 'Futu 未連線、行情權限不足、報價逾時或超過15分鐘；已切換公開行情。'
    result = sanitize_quote(await (public or public_quote)(code),code)
    result['source'] = 'Yahoo Finance'
    result['fallback_reason'] = reason
    return result
