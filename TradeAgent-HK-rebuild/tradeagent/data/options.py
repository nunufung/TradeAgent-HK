from __future__ import annotations
from datetime import datetime
from pathlib import Path
import pandas as pd
from tradeagent.models import OptionContract

REQUIRED = {"symbol", "type", "strike", "expiry", "bid", "ask"}


def load_verified_csv(path: str | Path) -> tuple[list[OptionContract], list[str]]:
    """Load option observations from a user/broker/HKEX-derived CSV.

    The loader never fills missing market fields with invented values. For an
    actionable recommendation, the rule engine still requires Delta, liquidity,
    and margin evidence according to config.
    """
    p = Path(path)
    if not p.exists():
        return [], [f"Option data file not found: {p}"]

    df = pd.read_csv(p)
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED - set(df.columns)
    if missing:
        return [], [f"Option CSV missing required columns: {sorted(missing)}"]

    out, errors = [], []
    for i, row in df.iterrows():
        try:
            expiry = pd.to_datetime(row["expiry"]).date()
            def opt_float(name):
                if name not in df.columns or pd.isna(row[name]):
                    return None
                return float(row[name])
            def opt_int(name):
                if name not in df.columns or pd.isna(row[name]):
                    return None
                return int(float(row[name]))
            out.append(OptionContract(
                symbol=str(row["symbol"]).strip().upper(),
                option_type=str(row["type"]).strip().upper(),
                strike=float(row["strike"]),
                expiry=expiry,
                bid=float(row["bid"]),
                ask=float(row["ask"]),
                delta=opt_float("delta"),
                iv=opt_float("iv"),
                volume=opt_int("volume"),
                open_interest=opt_int("open_interest"),
                margin=opt_float("margin"),
                lot_size=opt_int("lot_size") or 1,
                source=str(row["source"]).strip() if "source" in df.columns and not pd.isna(row["source"]) else "CSV",
            ))
        except Exception as exc:
            errors.append(f"row {i + 2}: {exc}")
    return out, errors
