import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from dashboard.build_data import snapshot, safe_number


class PublicDashboardTests(unittest.TestCase):
    def sample(self):
        watchlist = {"stocks": [{"code": "0700", "name": "騰訊控股", "group": "technology",
                    "aliases": ["USER_PRIVATE_NOTE_SHOULD_NOT_EXPORT"]}], "updated_at": "2026-10-19",
                    "private_holdings": [{"account_id": "NEVER_PUBLISH"}]}
        fincept = {"generated_at": "2026-10-25T06:00:00+08:00", "data_cutoff": "2026-10-23",
                   "forecasts": [{"ticker": "0700", "status": "FORECAST_ONLY", "last_close": 500,
                      "endpoint_return": 0.01, "forecast": [501,502,503,504,505],
                      "sessions": ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"],
                      "trading_account": "PRIVATE_ACCOUNT"}],
                   "metrics": {"valid": 20, "predicted": {"mae": 0.02}, "zero": {"mae": 0.015}}}
        kronos = {"generated_at": "2026-10-25T03:25:00+08:00",
                  "forecasts": [{"ticker": "0700", "data_cutoff": "2026-10-23",
                     "status": "FORECAST_ONLY", "last_close": 500,
                     "endpoint_return": -0.02,
                     "sessions": ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"],
                     "candles": [{"close": n} for n in [498, 496, 494, 492, 490]]}]}
        metrics = {"pooled": {"valid": 30, "predicted": {"mae": 0.05}},
                   "stocks": [{"ticker": "0700", "metrics": {"valid": 24,
                      "predicted": {"mae": 0.035, "direction_correct": 14, "direction_n": 24},
                      "zero": {"mae": 0.024}}}]}
        return watchlist, fincept, kronos, metrics

    def test_whitelist_excludes_private_accounts_aliases_and_nonapproved_fields(self):
        w,f,k,b = self.sample()
        result=snapshot(watchlist=w,fincept=f,kronos=k,kronos_backtest=b,
                        now=datetime(2026,10,25,8,30,tzinfo=ZoneInfo("Asia/Hong_Kong")))
        data=json.dumps(result,ensure_ascii=False)
        for secret in ["PRIVATE_ACCOUNT", "NEVER_PUBLISH", "USER_PRIVATE_NOTE", "trading_account"]:
            self.assertNotIn(secret,data)
        self.assertEqual(result["stocks"][0]["fincept"]["forecast_return_pct"],1)
        self.assertEqual(result["stocks"][0]["kronos"]["forecast_return_pct"],-2)
        self.assertEqual(result["stocks"][0]["backtest"]["kronos_mae_pp"],3.5)
        self.assertTrue(result["meta"]["not_live"])
        self.assertEqual(result["health"]["state"],"UNVERIFIED")

    def test_valid_same_day_health_display_and_no_raw_extras(self):
        w,f,k,b=self.sample()
        health={"date_hkt":"2026-10-25","overall":"FAILED","research":"incomplete",
                "telegram":"api_acknowledged","futu_opend":"stale_smoke_test",
                "deepseek":{"measured_calls":0,"actual_tokens":0,"cache_hit_tokens":0},
                "raw_access_token":"SENSITIVE_TEST_TOKEN"}
        result=snapshot(health=health,watchlist=w,fincept=f,kronos=k,kronos_backtest=b,
                        now=datetime(2026,10,25,8,30,tzinfo=ZoneInfo("Asia/Hong_Kong")))
        self.assertEqual(result["health"]["state"],"FAILED")
        self.assertEqual(result["health"]["api_calls"],0)
        self.assertNotIn("SENSITIVE_TEST_TOKEN",json.dumps(result))

    def test_prior_day_health_is_unverified_not_carried_forward(self):
        w,f,k,b=self.sample()
        result=snapshot(health={"date_hkt":"2026-10-24","overall":"PASS"},
                        watchlist=w,fincept=f,kronos=k,kronos_backtest=b,
                        now=datetime(2026,10,25,8,30,tzinfo=ZoneInfo("Asia/Hong_Kong")))
        self.assertEqual(result["health"]["state"],"UNVERIFIED")

    def test_missing_forecast_fails_closed(self):
        w,_,_,b=self.sample()
        result=snapshot(watchlist=w,fincept={},kronos={},kronos_backtest=b)
        self.assertEqual(result["stocks"][0]["fincept"]["status"],"UNAVAILABLE")
        self.assertIsNone(result["stocks"][0]["fincept"]["forecast_return_pct"])
        self.assertIsNone(safe_number(float("nan")))


if __name__ == "__main__":
    unittest.main()
