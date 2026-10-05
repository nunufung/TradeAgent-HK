from __future__ import annotations
from datetime import datetime, timezone
import math
import pandas as pd
import yfinance as yf
from tradeagent.models import StockSnapshot


def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    value = 100 - (100 / (1 + rs))
    last = value.iloc[-1]
    return float(last) if pd.notna(last) else 50.0


def _pct_return(close: pd.Series, lookback: int) -> float:
    if len(close) <= lookback:
        return 0.0
    return float(close.iloc[-1] / close.iloc[-(lookback + 1)] - 1)


def _technical_score(close: pd.Series, volume: pd.Series) -> tuple[float, str]:
    spot = float(close.iloc[-1])
    sma20 = float(close.tail(20).mean())
    sma50 = float(close.tail(50).mean()) if len(close) >= 50 else sma20
    ret5 = _pct_return(close, 5)
    ret20 = _pct_return(close, 20)
    rsi = _rsi(close)
    vol20 = float(volume.tail(20).mean()) if len(volume) else 0.0
    vol_ratio = float(volume.iloc[-1] / vol20) if vol20 > 0 else 1.0

    score = 0.0
    score += 2.0 if spot > sma20 else 0.5
    score += 2.0 if sma20 > sma50 else 0.5
    score += max(0.0, min(2.0, 1.0 + ret20 * 10))
    score += 1.5 if 50 <= rsi <= 70 else (0.75 if 40 <= rsi < 50 else 0.25)
    score += max(0.0, min(1.0, vol_ratio / 1.5))
    score += max(0.0, min(1.5, 0.75 + ret5 * 12))
    score = round(max(0.0, min(10.0, score)), 2)

    if spot > sma20 > sma50 and ret20 > 0:
        trend = "bullish"
    elif spot < sma20 < sma50 and ret20 < 0:
        trend = "bearish"
    else:
        trend = "mixed"
    return score, trend


def _headline_risk_flags(headlines: list[str]) -> list[str]:
    risky = {
        "earnings": "earnings/event risk",
        "results": "earnings/event risk",
        "profit warning": "profit warning",
        "regulator": "regulatory risk",
        "investigation": "regulatory risk",
        "lawsuit": "legal risk",
        "halt": "trading halt risk",
        "suspension": "suspension risk",
    }
    flags = []
    for h in headlines:
        lo = h.lower()
        for needle, label in risky.items():
            if needle in lo and label not in flags:
                flags.append(label)
    return flags


def fetch_stock_snapshot(symbol: str, period: str = "3mo") -> StockSnapshot:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, auto_adjust=False)
    if hist is None or hist.empty or "Close" not in hist:
        raise RuntimeError(f"No stock history returned for {symbol}")
    hist = hist.dropna(subset=["Close"])
    if len(hist) < 20:
        raise RuntimeError(f"Insufficient history for {symbol}: {len(hist)} rows")

    close = hist["Close"]
    volume = hist["Volume"] if "Volume" in hist else pd.Series([0] * len(hist), index=hist.index)
    score, trend = _technical_score(close, volume)

    headlines: list[str] = []
    try:
        news = ticker.news or []
        for item in news[:5]:
            title = item.get("title") or item.get("content", {}).get("title")
            if title:
                headlines.append(str(title))
    except Exception:
        pass

    return StockSnapshot(
        symbol=symbol,
        spot=float(close.iloc[-1]),
        prev_close=float(close.iloc[-2]) if len(close) > 1 else float(close.iloc[-1]),
        return_5d=_pct_return(close, 5),
        return_20d=_pct_return(close, 20),
        sma20=float(close.tail(20).mean()),
        sma50=float(close.tail(50).mean()) if len(close) >= 50 else float(close.tail(20).mean()),
        rsi14=_rsi(close),
        volume=float(volume.iloc[-1]),
        avg_volume20=float(volume.tail(20).mean()),
        score=score,
        trend=trend,
        as_of=datetime.now(timezone.utc),
        headlines=headlines,
        risk_flags=_headline_risk_flags(headlines),
    )


def fetch_watchlist(symbols: list[str], period: str = "3mo") -> tuple[list[StockSnapshot], list[str]]:
    snapshots, errors = [], []
    for symbol in symbols:
        try:
            snapshots.append(fetch_stock_snapshot(symbol, period=period))
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
    return sorted(snapshots, key=lambda s: s.score, reverse=True), errors

MARKET_PROXIES = {
    "Hang Seng Index": "^HSI",
    "Hang Seng China Enterprises": "^HSCE",
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "USD/HKD": "HKD=X",
    "USD/CNH": "CNH=X",
}


def fetch_market_context() -> tuple[list[dict], list[str]]:
    """Fetch a compact set of market proxies for the 07:00/10:00 report."""
    rows, errors = [], []
    for label, symbol in MARKET_PROXIES.items():
        try:
            h = yf.Ticker(symbol).history(period="1mo", auto_adjust=False).dropna(subset=["Close"])
            if h.empty:
                raise RuntimeError("no history")
            close = h["Close"]
            spot = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) > 1 else spot
            rows.append({
                "label": label,
                "symbol": symbol,
                "last": spot,
                "day_change": (spot / prev - 1) if prev else 0.0,
                "five_day_change": _pct_return(close, 5),
            })
        except Exception as exc:
            errors.append(f"market proxy {label}: {exc}")
    return rows, errors
