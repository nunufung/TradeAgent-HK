"""Futu OpenD based HK option screener. Read-only; never places orders."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo
from agents.screening_agent import ScreeningAgent

HKT = ZoneInfo("Asia/Hong_Kong")
DEFAULT_WATCHLIST = ["HK.00700", "HK.02800", "HK.01299", "HK.09988", "HK.00388", "HK.00005", "HK.00941", "HK.01810"]


SCREENING_RULES = {
    "delta_max": 0.10,
    "expiry_days": list(range(21, 46)),
    "expiry_tolerance": 0,
    "max_spread_pct": 0.30,
    "min_volume": 1,
    "min_oi": 100,
    "max_margin_premium_multiple": 10.0,
    "max_quote_age_minutes": 30,
    # Query account-specific margin only for the best 50 quote candidates.
    "top_n": 50,
}


def _number(row: Any, key: str, default: float = 0.0) -> float:
    try:
        value = float(row[key])
        return value if value == value else default
    except (KeyError, TypeError, ValueError):
        return default


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


def scan(
    watchlist: list[str],
    host: str,
    port: int,
    require_margin: bool = True,
    stock_signals: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
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
        screener = ScreeningAgent(SCREENING_RULES)
        for underlying in watchlist:
            signal = (stock_signals or {}).get(underlying, {})
            allowed_types = set(signal.get("allowed_option_types", []))
            if stock_signals is not None and not allowed_types:
                errors.append(
                    f"{underlying}: 正股評級 {signal.get('rating', '缺少')}，方向未明或分析不完整；期權篩選已封鎖"
                )
                continue
            ret, expiries = quote_ctx.get_option_expiration_date(code=underlying)
            if ret != RET_OK:
                errors.append(f"{underlying}: 無法取得到期日 ({expiries})")
                continue
            expiry_dates = []
            for text in expiries.get("strike_time", []).tolist():
                exp = date.fromisoformat(str(text)[:10])
                dte = (exp - today).days
                if 21 <= dte <= 45:
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
        quote_candidates: list[dict[str, Any]] = []
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
            quote_candidates.append(row)

        # First pass follows the original Data -> ScreeningAgent design without
        # margin data; then query account margin only for its top 50 candidates.
        allowed_types_by_underlying = (
            {ticker: set(signal.get("allowed_option_types", [])) for ticker, signal in stock_signals.items()}
            if stock_signals is not None
            else None
        )
        prequalified = screener.screen(
            quote_candidates,
            check_margin=False,
            allowed_option_types=allowed_types_by_underlying,
        )
        for row in prequalified:
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
        candidates = screener.screen(
            prequalified,
            check_margin=True,
            allowed_option_types=allowed_types_by_underlying,
        )
        return candidates, errors
    finally:
        quote_ctx.close()
        if trade_ctx is not None:
            trade_ctx.close()


def render(
    candidates: list[dict[str, Any]],
    errors: list[str],
    watchlist: list[str],
    *,
    stock_signals: dict[str, dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(HKT)
    lines = [
        "📊 TradeAgent-HK｜Futu OpenD 期權篩選",
        f"報價時間：{now:%Y-%m-%d %H:%M HKT}",
        f"掃描：{', '.join(watchlist)}",
        "硬性篩選：Short Put/Call｜Delta 絕對值 ≤0.10｜21–45 DTE｜Spread ≤30%｜OI ≥100｜Margin/Premium ≤10x",
        "正股方向連動：Buy/Overweight → 只篩 Short Put；Underweight/Sell → 只篩 Short Call；Hold/REVIEW/分析不完整 → 不篩期權。",
        "TradingAgents 四位分析員：市場技術、社交情緒、新聞、基本面；以下評級由完整分析流程產生。",
        "",
    ]
    if stock_signals is not None:
        lines.append("正股篩選結果：")
        for ticker in watchlist:
            signal = stock_signals.get(ticker, {})
            analysts = signal.get("analysts", {})
            analyst_status = "/".join(
                f"{name}:{'✓' if analysts.get(name, {}).get('complete') else '✗'}"
                for name in ("market", "social", "news", "fundamentals")
            )
            allowed = ", ".join(signal.get("allowed_option_types", [])) or "不開倉"
            lines.append(f"- {ticker}｜{signal.get('rating', 'REVIEW')}｜期權方向：{allowed}｜四分析員 {analyst_status}")
        lines.append("")
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
        lines.append("⛔ 沒有合約通過正股方向及期權硬性篩選；今日不做。")
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
    parser.add_argument(
        "--stock-signals",
        help="TradingAgents 正股評級 JSON；指定後每隻股票必須有有效評級才會篩期權",
    )
    args = parser.parse_args()

    try:
        watchlist = [_market_code(x) for x in args.tickers] if args.tickers else DEFAULT_WATCHLIST
        stock_signals = None
        if args.stock_signals:
            with open(args.stock_signals, encoding="utf-8") as f:
                payload = json.load(f)
            stock_signals = payload.get("signals", {})
            missing = [ticker for ticker in watchlist if ticker not in stock_signals]
            if missing:
                raise ValueError(f"正股分析缺少股票評級，期權流程封鎖：{', '.join(missing)}")
        candidates, errors = scan(watchlist, args.host, args.port, stock_signals=stock_signals)
        report = render(candidates, errors, watchlist, stock_signals=stock_signals)
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
