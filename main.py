"""Futu OpenD based HK option screener. Read-only; never places orders."""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

HKT = ZoneInfo("Asia/Hong_Kong")
DEFAULT_WATCHLIST = ["HK.00700", "HK.02800", "HK.01299", "HK.09988", "HK.00388", "HK.00005", "HK.00941", "HK.01810"]


@dataclass(frozen=True)
class Rules:
    min_dte: int = 21
    max_dte: int = 45
    max_abs_delta: float = 0.10
    max_relative_spread: float = 0.30
    min_volume: int = 1
    min_open_interest: int = 100
    max_margin_premium_multiple: float = 10.0


def _number(row: Any, key: str, default: float = 0.0) -> float:
    try:
        value = float(row[key])
        return value if value == value else default
    except (KeyError, TypeError, ValueError):
        return default


def evaluate_option(row: dict[str, Any], rules: Rules = Rules(), *, check_margin: bool = True) -> tuple[bool, list[str]]:
    """Apply measurable entry gates. Missing required data fails closed."""
    failures: list[str] = []
    dte = int(row.get("dte", 0) or 0)
    if not rules.min_dte <= dte <= rules.max_dte:
        failures.append("DTE 不在 21–45 日")
    delta = row.get("delta")
    if delta is None or not math.isfinite(float(delta)) or abs(float(delta)) > rules.max_abs_delta:
        failures.append("Delta 缺失或絕對值高於 0.10")
    iv = row.get("iv")
    if iv is None or not math.isfinite(float(iv)) or float(iv) <= 0:
        failures.append("IV 數據缺失或無效")
    bid, ask = float(row.get("bid", 0) or 0), float(row.get("ask", 0) or 0)
    if bid <= 0 or ask <= 0 or ask < bid:
        failures.append("Bid/Ask 無效或單邊報價")
    else:
        mid = (bid + ask) / 2
        if (ask - bid) / mid > rules.max_relative_spread:
            failures.append("相對 Spread 高於 30%")
    if int(row.get("volume", 0) or 0) < rules.min_volume:
        failures.append("成交量不足")
    if int(row.get("open_interest", 0) or 0) < rules.min_open_interest:
        failures.append("未平倉量低於 100 張")
    if not check_margin:
        return not failures, failures
    margin = row.get("short_required_im")
    lot = float(row.get("lot_size", 0) or 0)
    premium_per_lot = bid * lot
    if margin is None or float(margin) <= 0 or premium_per_lot <= 0:
        failures.append("無法核實賣出初始保證金 / Premium")
    elif not math.isfinite(float(margin)):
        failures.append("賣出初始保證金數據無效")
    elif float(margin) / premium_per_lot > rules.max_margin_premium_multiple:
        failures.append("Margin / Premium 高於 10x")
    return not failures, failures


def _hkt_today() -> date:
    return datetime.now(HKT).date()


def _is_open_window(now: datetime | None = None) -> bool:
    now = now or datetime.now(HKT)
    return now.weekday() < 5 and (now.hour, now.minute) >= (10, 0)


def _market_code(raw: str) -> str:
    code = raw.strip().upper().replace(".HK", "").replace("HK.", "")
    if not code.isdigit() or not 1 <= int(code) <= 99999:
        raise ValueError(f"無效港股代號：{raw}")
    return f"HK.{int(code):05d}"


def _fresh_quote_time(value: Any, now: datetime | None = None) -> bool:
    """Reject cached/closed-market prices older than 30 minutes."""
    try:
        quote_time = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=HKT)
    except (TypeError, ValueError):
        return False
    now = now or datetime.now(HKT)
    age_minutes = (now - quote_time).total_seconds() / 60
    return -1 <= age_minutes <= 30


def _snapshot_map(quote_ctx, codes: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    # Futu supports up to 400 snapshot codes per request.
    for offset in range(0, len(codes), 400):
        ret, frame = quote_ctx.get_market_snapshot(codes[offset:offset + 400])
        if ret != 0:
            raise RuntimeError(f"OpenD get_market_snapshot 失敗：{frame}")
        for _, series in frame.iterrows():
            result[str(series.get("code", ""))] = series.to_dict()
    return result


def scan(watchlist: list[str], host: str, port: int, require_margin: bool = True) -> tuple[list[dict[str, Any]], list[str]]:
    """Connect to local OpenD and return real, rule-qualified candidates."""
    try:
        from futu import (  # type: ignore
            OpenQuoteContext, OpenSecTradeContext, RET_OK, OrderType,
            TrdEnv, TrdMarket, SecurityFirm,
        )
    except ImportError as exc:
        raise RuntimeError("未安裝 futu-api；請先執行 python -m pip install futu-api") from exc

    quote_ctx = OpenQuoteContext(host=host, port=port)
    trade_ctx = None
    try:
        if require_margin:
            firm = getattr(SecurityFirm, os.getenv("FUTU_SECURITY_FIRM", "FUTUSECURITIES"), SecurityFirm.FUTUSECURITIES)
            trade_ctx = OpenSecTradeContext(
                filter_trdmarket=TrdMarket.HK, host=host, port=port, security_firm=firm
            )

        raw_contracts: list[dict[str, Any]] = []
        errors: list[str] = []
        today = _hkt_today()
        for underlying in watchlist:
            ret, expiries = quote_ctx.get_option_expiration_date(code=underlying)
            if ret != RET_OK:
                errors.append(f"{underlying}: 無法取得到期日 ({expiries})")
                continue
            expiry_dates = []
            for text in expiries.get("strike_time", []).tolist():
                exp = date.fromisoformat(str(text)[:10])
                dte = (exp - today).days
                if Rules().min_dte <= dte <= Rules().max_dte:
                    expiry_dates.append((exp, dte))

            for expiry, dte in expiry_dates:
                ret, chain = quote_ctx.get_option_chain(
                    code=underlying, start=expiry.isoformat(), end=expiry.isoformat()
                )
                if ret != RET_OK:
                    errors.append(f"{underlying} {expiry}: 無法讀取期權鏈 ({chain})")
                    continue
                for _, contract in chain.iterrows():
                    option_type = str(contract.get("option_type", "")).upper()
                    if option_type not in {"PUT", "CALL"} or bool(contract.get("suspension", False)):
                        continue
                    raw_contracts.append({
                        "underlying": underlying,
                        "option_code": str(contract["code"]),
                        "option_type": option_type,
                        "expiry": expiry.isoformat(),
                        "dte": dte,
                        "strike": _number(contract, "strike_price"),
                        "lot_size": _number(contract, "lot_size"),
                        "name": str(contract.get("name", "")),
                    })
                # Futu documents a limit of 10 chain calls per 30 seconds.
                time.sleep(3.1)

        snapshots = _snapshot_map(quote_ctx, [c["option_code"] for c in raw_contracts]) if raw_contracts else {}
        underlying_snaps = _snapshot_map(quote_ctx, watchlist)
        prequalified: list[dict[str, Any]] = []
        for contract in raw_contracts:
            snap = snapshots.get(contract["option_code"])
            if not snap:
                continue
            row = {
                **contract,
                "bid": _number(snap, "bid_price"),
                "ask": _number(snap, "ask_price"),
                "delta": _number(snap, "option_delta", float("nan")),
                "iv": _number(snap, "option_implied_volatility", float("nan")),
                "volume": int(_number(snap, "volume")),
                "open_interest": int(_number(snap, "option_open_interest")),
                "quote_time": str(snap.get("update_time", "")),
                "spot": _number(underlying_snaps.get(contract["underlying"], {}), "last_price"),
                "short_required_im": None,
            }
            if not _fresh_quote_time(row["quote_time"]):
                continue
            if row["spot"] <= 0:
                continue
            if row["option_type"] == "PUT" and row["strike"] >= row["spot"]:
                continue
            if row["option_type"] == "CALL" and row["strike"] <= row["spot"]:
                continue
            accepted, _ = evaluate_option(row, check_margin=False)
            if accepted:
                prequalified.append(row)

        # Rank by quote quality first; margin queries are only needed for a small
        # set of viable contracts, not every contract in the chain.
        prequalified.sort(key=lambda x: (
            (x["ask"] - x["bid"]) / ((x["ask"] + x["bid"]) / 2),
            -x["open_interest"], -x["volume"],
        ))
        candidates: list[dict[str, Any]] = []
        for row in prequalified[:50]:
            # Query the broker/account specific incremental initial margin. Never
            # treat an estimate as a valid value when this read-only query fails.
            if trade_ctx is not None:
                ret, margin_frame = trade_ctx.acctradinginfo_query(
                    order_type=OrderType.NORMAL,
                    code=row["option_code"],
                    price=row["bid"],
                    trd_env=getattr(TrdEnv, os.getenv("FUTU_TRD_ENV", "REAL"), TrdEnv.REAL),
                    acc_id=int(os.getenv("FUTU_ACC_ID", "0") or 0),
                    acc_index=int(os.getenv("FUTU_ACC_INDEX", "0") or 0),
                )
                if ret == RET_OK and len(margin_frame):
                    value = margin_frame.iloc[0].get("short_required_im")
                    try:
                        row["short_required_im"] = float(value)
                    except (TypeError, ValueError):
                        pass
            accepted, reasons = evaluate_option(row)
            row["accepted"] = accepted
            row["failures"] = reasons
            if accepted:
                candidates.append(row)

        # Prefer tighter markets and better displayed liquidity. Premium/IV are
        # reported but never used alone to override a hard risk gate.
        candidates.sort(key=lambda x: (
            (x["ask"] - x["bid"]) / ((x["ask"] + x["bid"]) / 2),
            -x["open_interest"], -x["volume"],
        ))
        return candidates, errors
    finally:
        quote_ctx.close()
        if trade_ctx is not None:
            trade_ctx.close()


def render(candidates: list[dict[str, Any]], errors: list[str], watchlist: list[str], *, now: datetime | None = None) -> str:
    now = now or datetime.now(HKT)
    lines = [
        "📊 TradeAgent-HK｜Futu OpenD 期權篩選",
        f"報價時間：{now:%Y-%m-%d %H:%M HKT}",
        f"掃描：{', '.join(watchlist)}",
        "硬性篩選：Short Put/Call｜Delta 絕對值 ≤0.10｜21–45 DTE｜Spread ≤30%｜OI ≥100｜Margin/Premium ≤10x",
        "此清單只通過可量化篩選；開倉前仍須人工核對股價趨勢、支撐/阻力、業績/新聞、假期及現金 buffer。",
        "",
    ]
    if not _is_open_window(now):
        lines.append("⏸️ 現在未符合 10:00 HKT 後開倉時段，今日不會提出新倉建議。")
    elif candidates:
        lines.append("候選合約（最多 3 張）：")
        for n, c in enumerate(candidates[:3], 1):
            mid = (c["bid"] + c["ask"]) / 2
            spread_pct = (c["ask"] - c["bid"]) / mid * 100
            side = "賣 Put" if c["option_type"] == "PUT" else "賣 Call"
            per_contract_premium = c["bid"] * c["lot_size"]
            ratio = c["short_required_im"] / per_contract_premium
            lines.append(
                f"{n}. {c['underlying']} {side}｜行使價 {c['strike']:g}｜到期 {c['expiry']} ({c['dte']} DTE)\n"
                f"   正股 {c['spot']:g}｜Delta {c['delta']:.3f}｜Bid/Ask {c['bid']:.3f}/{c['ask']:.3f}｜Spread {spread_pct:.1f}%\n"
                f"   IV {c['iv']:.1f}%｜Vol {c['volume']}｜OI {c['open_interest']}｜每張 Premium 約 HK${per_contract_premium:,.0f}\n"
                f"   賣出初始保證金約 HK${c['short_required_im']:,.0f}｜Margin/Premium {ratio:.1f}x｜代碼 {c['option_code']}"
            )
        lines.append("\n結論：以上為合規候選，並非自動下單或保證買賣指示。")
    else:
        lines.append("⛔ 沒有合約同時通過硬性數據篩選；今日不做。")
    if errors:
        lines.append("\n資料 / 連線提示：")
        lines.extend(f"- {e}" for e in errors[:8])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="只讀 Futu OpenD 港股期權篩選器")
    parser.add_argument("tickers", nargs="*", help="股票代號，例如 700 2800；預設使用 watchlist")
    parser.add_argument("--host", default=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("FUTU_OPEND_PORT", "11111")))
    parser.add_argument("--output", default="option_screen.md")
    args = parser.parse_args()

    try:
        watchlist = [_market_code(x) for x in args.tickers] if args.tickers else DEFAULT_WATCHLIST
        candidates, errors = scan(watchlist, args.host, args.port)
        report = render(candidates, errors, watchlist)
    except Exception as exc:
        report = (
            "📊 TradeAgent-HK｜Futu OpenD 期權篩選\n"
            f"⛔ 連線/掃描失敗：{type(exc).__name__}: {exc}\n"
            "本次沒有使用模擬報價，亦不會產生開倉候選。請確認本機 OpenD 已登入並可由此 Mac 連接。"
        )
        print(report, file=sys.stderr)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        return 1
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
