from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class StockSnapshot:
    symbol: str
    spot: float
    prev_close: float
    return_5d: float
    return_20d: float
    sma20: float
    sma50: float
    rsi14: float
    volume: float
    avg_volume20: float
    score: float
    trend: str
    as_of: datetime
    source: str = "Yahoo Finance"
    headlines: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class OptionContract:
    symbol: str
    option_type: str
    strike: float
    expiry: date
    bid: float
    ask: float
    delta: Optional[float] = None
    iv: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    margin: Optional[float] = None
    lot_size: int = 1
    source: str = "unknown"

    @property
    def mid(self) -> Optional[float]:
        if self.bid <= 0 or self.ask <= 0:
            return None
        return (self.bid + self.ask) / 2

    @property
    def spread_pct(self) -> Optional[float]:
        mid = self.mid
        if not mid:
            return None
        return (self.ask - self.bid) / mid

    def dte(self, on_date: date) -> int:
        return (self.expiry - on_date).days

    @property
    def premium_cash(self) -> float:
        return max(self.bid, 0) * max(self.lot_size, 1)

    @property
    def margin_premium_ratio(self) -> Optional[float]:
        if self.margin is None or self.premium_cash <= 0:
            return None
        return self.margin / self.premium_cash


@dataclass
class OptionDecision:
    action: str
    contract: Optional[OptionContract]
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
