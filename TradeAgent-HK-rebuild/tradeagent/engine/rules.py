from __future__ import annotations
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from tradeagent.models import OptionContract, OptionDecision, StockSnapshot


def _parse_hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def market_allows_new_trade(rules: dict, now: datetime | None = None) -> bool:
    tz = ZoneInfo(rules["market"]["timezone"])
    now = now.astimezone(tz) if now else datetime.now(tz)
    return now.time() >= _parse_hhmm(rules["market"]["no_new_trade_before"])


def evaluate_option(
    contract: OptionContract,
    stock: StockSnapshot,
    rules: dict,
    on_date: date,
    require_margin: bool = True,
) -> OptionDecision:
    cfg = rules["short_option"]
    liq = rules["liquidity_defaults"]
    reasons, warnings = [], []
    dte = contract.dte(on_date)

    if contract.symbol != stock.symbol:
        return OptionDecision("REJECT", contract, reasons=["underlying mismatch"])
    if contract.option_type not in {"PUT", "CALL"}:
        return OptionDecision("REJECT", contract, reasons=["unsupported option type"])
    if contract.bid <= 0 or contract.ask <= 0 or contract.ask < contract.bid:
        return OptionDecision("REJECT", contract, reasons=["invalid bid/ask"])
    if dte < cfg["no_new_naked_short_below_dte"]:
        return OptionDecision("REJECT", contract, reasons=[f"DTE {dte} below new-trade floor"])
    if not (cfg["preferred_dte_min"] <= dte <= cfg["preferred_dte_max"]):
        warnings.append(f"DTE {dte} outside preferred {cfg['preferred_dte_min']}-{cfg['preferred_dte_max']}")
    else:
        reasons.append("DTE in preferred range")

    if contract.delta is None:
        return OptionDecision("REJECT", contract, reasons=["Delta unavailable"])
    if abs(contract.delta) > cfg["delta_max"]:
        return OptionDecision("REJECT", contract, reasons=[f"|Delta| {abs(contract.delta):.3f} > {cfg['delta_max']:.2f}"])
    reasons.append("Delta within limit")

    sp = contract.spread_pct
    if sp is None or sp > cfg["max_spread_pct"]:
        return OptionDecision("REJECT", contract, reasons=["spread too wide or unavailable"])
    reasons.append("spread acceptable")

    if contract.volume is None or contract.volume < liq["min_volume"]:
        return OptionDecision("REJECT", contract, reasons=["volume below configured liquidity floor or unavailable"])
    if contract.open_interest is None or contract.open_interest < liq["min_open_interest"]:
        return OptionDecision("REJECT", contract, reasons=["open interest below configured liquidity floor or unavailable"])
    reasons.append("liquidity checks passed")

    ratio = contract.margin_premium_ratio
    if ratio is None:
        if require_margin:
            return OptionDecision("WAIT", contract, reasons=reasons, warnings=["margin unavailable; verify broker margin before trade"])
        warnings.append("margin unavailable")
    elif ratio > cfg["margin_premium_max"]:
        return OptionDecision("REJECT", contract, reasons=[f"Margin/Premium {ratio:.2f}x > {cfg['margin_premium_max']:.1f}x"])
    else:
        reasons.append(f"Margin/Premium {ratio:.2f}x within limit")

    # Direction alignment: PUT sale wants bullish/neutral; CALL sale wants bearish/neutral.
    if contract.option_type == "PUT" and stock.trend == "bearish":
        return OptionDecision("REJECT", contract, reasons=["Short Put conflicts with bearish stock trend"])
    if contract.option_type == "CALL" and stock.trend == "bullish":
        return OptionDecision("REJECT", contract, reasons=["Short Call conflicts with bullish stock trend"])
    if stock.risk_flags:
        warnings.append("event/news risk: " + ", ".join(stock.risk_flags))

    dte_score = max(0.0, 1 - abs(dte - 30) / 30)
    delta_score = max(0.0, 1 - abs(abs(contract.delta) - cfg["target_abs_delta"]) / max(cfg["target_abs_delta"], 0.01))
    spread_score = max(0.0, 1 - sp / cfg["max_spread_pct"])
    liquidity_score = min(1.0, (contract.volume or 0) / max(liq["min_volume"] * 5, 1)) * 0.5 + min(1.0, (contract.open_interest or 0) / max(liq["min_open_interest"] * 5, 1)) * 0.5
    margin_score = 0.5 if ratio is None else max(0.0, 1 - ratio / cfg["margin_premium_max"])
    score = round(100 * (0.25*dte_score + 0.25*delta_score + 0.20*spread_score + 0.15*liquidity_score + 0.15*margin_score), 1)
    return OptionDecision("DO" if ratio is not None else "WAIT", contract, score=score, reasons=reasons, warnings=warnings)


def rank_options(contracts: list[OptionContract], stocks: list[StockSnapshot], rules: dict, on_date: date) -> list[OptionDecision]:
    stock_map = {s.symbol: s for s in stocks}
    decisions = []
    for c in contracts:
        s = stock_map.get(c.symbol)
        if not s:
            continue
        d = evaluate_option(c, s, rules, on_date, require_margin=True)
        if d.action in {"DO", "WAIT"}:
            decisions.append(d)
    return sorted(decisions, key=lambda d: (d.action == "DO", d.score), reverse=True)
