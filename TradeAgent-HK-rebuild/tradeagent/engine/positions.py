from __future__ import annotations


def manage_short_option(entry_premium: float, current_buyback: float, dte: int, rules: dict) -> dict:
    cfg = rules["short_option"]
    if entry_premium <= 0:
        return {"action": "ERROR", "reason": "entry premium must be positive"}
    pnl_pct = (entry_premium - current_buyback) / entry_premium
    loss_multiple = max(0.0, (current_buyback - entry_premium) / entry_premium)

    if loss_multiple > cfg["stop_loss_premium_multiple"]:
        return {"action": "CLOSE_OR_ROLL", "pnl_pct": pnl_pct, "reason": "loss exceeds 100% of original premium"}
    if cfg["take_profit_min"] <= pnl_pct <= 1.0:
        return {"action": "TAKE_PROFIT", "pnl_pct": pnl_pct, "reason": "profit reached take-profit zone"}
    if dte < cfg["manage_below_dte"] and pnl_pct > 0:
        return {"action": "CLOSE_PRIORITY", "pnl_pct": pnl_pct, "reason": "DTE below 21 with profit"}
    if dte < cfg["urgent_exit_below_dte"]:
        return {"action": "EXIT", "pnl_pct": pnl_pct, "reason": "extreme short-DTE gamma risk"}
    return {"action": "MONITOR", "pnl_pct": pnl_pct, "reason": "no hard exit trigger"}
