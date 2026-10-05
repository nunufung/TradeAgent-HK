from tradeagent.integrations.whatsapp import compact_summary, normalize_recipient


def test_normalize_recipient():
    assert normalize_recipient("+852 9817 0263") == "85298170263"


def test_actionable_summary():
    payload = {
        "mode": "actionable",
        "stock_recommendation": {
            "symbol": "0700.HK", "action": "WATCH / BULLISH BIAS", "score": 8.1, "trend": "bullish"
        },
        "option": {
            "action": "DO", "symbol": "0700.HK", "type": "PUT", "strike": 500,
            "expiry": "2026-11-27", "dte": 32, "delta": -0.08,
            "margin_premium_ratio": 6.2,
        },
        "errors": [],
    }
    msg = compact_summary(payload)
    assert "0700.HK" in msg
    assert "DTE 32" in msg
    assert "Option: DO" in msg


def test_premarket_summary_blocks_options():
    payload = {"mode": "premarket", "market": [], "stocks": [], "errors": []}
    msg = compact_summary(payload)
    assert "No new option trade before 10:00 HKT" in msg
