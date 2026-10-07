"""Rule-based gate for OpenD option-chain records.

The data adapter supplies quote fields; this agent applies the configured
entry rules and ranks only contracts that pass every enabled hard gate.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

HKT = ZoneInfo("Asia/Hong_Kong")


class ScreeningAgent:
    def __init__(self, rules: dict[str, Any]):
        self.r = rules

    def _fresh(self, value: Any) -> bool:
        try:
            quote_time = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=HKT)
        except (TypeError, ValueError):
            return False
        age = (datetime.now(HKT) - quote_time).total_seconds() / 60
        return -1 <= age <= self.r.get("max_quote_age_minutes", 30)

    def _passes(self, opt: dict[str, Any], check_margin: bool) -> bool:
        try:
            delta = float(opt["delta"])
            iv = float(opt["iv"])
            dte = int(opt.get("days_to_expiry", opt.get("dte", 0)))
            bid, ask = float(opt["bid"]), float(opt["ask"])
            spot, strike = float(opt["spot"]), float(opt["strike"])
            oi = int(opt.get("oi", opt.get("open_interest", 0)))
            volume = int(opt.get("vol", opt.get("volume", 0)))
        except (KeyError, TypeError, ValueError, OverflowError):
            return False

        expiry_days = self.r.get("expiry_days", [])
        tolerance = int(self.r.get("expiry_tolerance", 0))
        if not any(abs(dte - int(day)) <= tolerance for day in expiry_days):
            return False
        if not math.isfinite(delta) or abs(delta) > float(self.r["delta_max"]):
            return False
        if not math.isfinite(iv) or iv <= 0 or not self._fresh(opt.get("quote_time")):
            return False
        if not all(math.isfinite(value) for value in (bid, ask, spot, strike)):
            return False
        if bid <= 0 or ask <= 0 or ask < bid or spot <= 0 or strike <= 0:
            return False
        mid = (bid + ask) / 2
        if (ask - bid) / mid > float(self.r.get("max_spread_pct", 0.30)):
            return False
        if oi < int(self.r.get("min_oi", 100)) or volume < int(self.r.get("min_volume", 1)):
            return False

        # Short puts must be below spot; short calls must be above spot.
        option_type = str(opt.get("option_type", opt.get("type", ""))).upper()
        if option_type == "PUT" and strike >= spot:
            return False
        if option_type == "CALL" and strike <= spot:
            return False
        if option_type not in {"PUT", "CALL"}:
            return False

        # Preserve the old optional price-band rule for callers that configure it.
        price_band = self.r.get("price_band_pct")
        if price_band is not None and abs(strike - spot) / spot > float(price_band):
            return False

        if check_margin:
            margin = opt.get("short_required_im")
            lot_size = float(opt.get("lot_size", 0) or 0)
            premium_per_contract = bid * lot_size
            try:
                margin = float(margin)
            except (TypeError, ValueError):
                return False
            if not math.isfinite(margin) or not math.isfinite(lot_size) or margin <= 0 or premium_per_contract <= 0:
                return False
            if margin / premium_per_contract > float(self.r.get("max_margin_premium_multiple", 10)):
                return False
        return True

    def screen(
        self,
        chains: list[dict[str, Any]],
        *,
        check_margin: bool = True,
        allowed_option_types: dict[str, set[str]] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter by hard gates, rank by quote quality, return up to top_n."""
        result = []
        for source in chains:
            if allowed_option_types is not None:
                underlying = str(source.get("underlying", ""))
                allowed = allowed_option_types.get(underlying, set())
                option_type = str(source.get("option_type", source.get("type", ""))).upper()
                if option_type not in allowed:
                    continue
            if not self._passes(source, check_margin):
                continue
            opt = dict(source)
            mid = (float(opt["ask"]) + float(opt["bid"])) / 2
            spread = (float(opt["ask"]) - float(opt["bid"])) / mid
            delta_quality = 1 - abs(float(opt["delta"])) / float(self.r["delta_max"])
            volume = float(opt.get("vol", opt.get("volume", 0)))
            oi = float(opt.get("oi", opt.get("open_interest", 0)))
            # Bounded score keeps raw volume from overwhelming all other factors.
            opt["score"] = round(
                0.45 * (1 - spread / float(self.r.get("max_spread_pct", 0.30)))
                + 0.25 * min(volume / 100, 1)
                + 0.20 * min(oi / 1000, 1)
                + 0.10 * max(delta_quality, 0),
                4,
            )
            result.append(opt)
        result.sort(key=lambda item: item["score"], reverse=True)
        return result[: int(self.r.get("top_n", 3))]
