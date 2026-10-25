import json
import unittest
import tempfile
from pathlib import Path
from agent_event_log import emit, read
from traced_propagation import propagate_traced
from contextlib import nullcontext
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

    def test_daily_recommendations_are_dated_and_redacted(self):
        w,f,k,b=self.sample()
        raw={"analysis_date":"2026-10-25","action":"等待",
             "risk_review_complete":False,"main_option":{"account":"SECRET_OPTION_ACCOUNT"},
             "stocks":[{"underlying":"HK.00700","complete":True,"rating":"Buy",
                        "strategy":"Short Put（條件式）","decision_summary":"等待核實行情。",
                        "evidence":{"market":"SECRET_EVIDENCE"},"private_note":"SECRET_POSITION"}],
             "reasons":["等待即時合約掃描。"],"api_key":"SECRET_API_KEY"}
        now=datetime(2026,10,25,8,30,tzinfo=ZoneInfo("Asia/Hong_Kong"))
        result=snapshot(watchlist=w,fincept=f,kronos=k,kronos_backtest=b,
                        recommendations=raw,now=now)["daily_recommendations"]
        self.assertEqual(result["stocks"][0]["rating"],"Buy")
        self.assertFalse(result["risk_review_complete"])
        self.assertIsNone(result["option"])
        self.assertNotIn("SECRET_",json.dumps(result))
        raw["analysis_date"]="2026-10-24"
        stale=snapshot(watchlist=w,fincept=f,kronos=k,kronos_backtest=b,
                       recommendations=raw,now=now)["daily_recommendations"]
        self.assertEqual(stale["state"],"UNAVAILABLE")
        self.assertEqual(stale["stocks"],[])

    def test_spider_never_invents_agent_activity(self):
        w,f,k,b=self.sample()
        now=datetime(2026,10,25,8,30,tzinfo=ZoneInfo("Asia/Hong_Kong"))
        health={"date_hkt":"2026-10-25","overall":"WARNING",
                "research":"complete","telegram":"api_acknowledged",
                "deepseek":{"actual_tokens":1234,"measured_calls":1},
                "private_key":"SECRET_HIDDEN"}
        result=snapshot(health=health,watchlist=w,fincept=f,kronos=k,kronos_backtest=b,now=now)["agent_events"]
        self.assertEqual(result["mode"],"DAILY_SNAPSHOT_NOT_LIVE")
        self.assertTrue(result["research_complete"])
        self.assertTrue(all(a["state"]=="UNVERIFIED" for a in result["agents"]))
        self.assertEqual(result["token_count"],1234)
        self.assertNotIn("SECRET_HIDDEN",json.dumps(result))
        self.assertTrue(all(o["day"]=="2026-10-25" for o in result["observations"]))
        stale=snapshot(health={"date_hkt":"2026-10-24","overall":"PASS","research":"complete"},
                       watchlist=w,fincept=f,kronos=k,kronos_backtest=b,now=now)["agent_events"]
        self.assertFalse(stale["research_complete"])
        self.assertEqual(stale["observations"],[])
        self.assertIsNone(stale["token_count"])

    def test_real_trace_emission_is_structured_and_excludes_private_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = str(Path(tmp) / "events.jsonl")
            a=emit("GRAPH_STARTED",ticker="HK.00700",state="STARTED",path=dest)
            b=emit("REPORT_OBSERVED",ticker="HK.00700",role="market",state="OBSERVED",path=dest)
            events=read(dest)
            self.assertEqual([x["kind"] for x in events],["GRAPH_STARTED","REPORT_OBSERVED"])
            self.assertEqual(events[1]["role"],"market")
            self.assertNotIn("prompt",json.dumps(events))
            self.assertIn("timestamp_hkt",a)
            with self.assertRaises(ValueError):
                emit("INVENTED_AGENT_HANDOFF",ticker="HK.00700",path=dest)

    def test_streamed_graph_reports_are_observed_without_duplicate_execution(self):
        class Prop:
            def get_graph_args(self):
                return {"config": {"recursion_limit": 20}}
        class FakeGraph:
            config = {"model": "stub"}
            propagator = Prop()
            def __init__(self):
                self.calls = 0
                self.persisted = 0
                self.cleaned = 0
            def checkpoint_scope(self, *args):
                return nullcontext(None)
            def create_run_state(self, *args):
                return {"company_of_interest": "700.HK"}
            def checkpoint_input(self, initial):
                return initial
            def stream_run(self, inp, **kwargs):
                self.calls += 1
                yield [], {"company_of_interest": "700.HK"}
                yield [], {"market_report": "technical research"}
                yield [], {"news_report": "news research"}
                yield [], {"sentiment_report": "sentiment"}
                yield [], {"fundamentals_report": "fundamentals", "final_trade_decision": "Hold"}
            def record_decision(self, *args):
                self.persisted += 1
            def clear_checkpoint_on_success(self, *args):
                self.cleaned += 1
        g = FakeGraph()
        observed = []
        def capture(kind, **kwargs):
            observed.append((kind,kwargs.get("role")))
        state, rating = propagate_traced(g, "700.HK", "2026-10-25", "HK.00700",
                                        lambda _config: nullcontext(), capture,
                                        rating_fn=lambda _state: "Hold")
        self.assertEqual(rating,"Hold")
        self.assertEqual((g.calls,g.persisted,g.cleaned),(1,1,1))
        self.assertEqual([role for event,role in observed if event=="REPORT_OBSERVED"],
                         ["market","news","social","fundamentals"])
        self.assertEqual(state["final_trade_decision"],"Hold")
        self.assertNotIn("technical research",json.dumps(observed))

    def test_lookup_ui_is_read_only_and_never_collects_credentials(self):
        ui=(Path(__file__).resolve().parents[1]/"dashboard/space/index.html").read_text(encoding="utf-8")
        js=(Path(__file__).resolve().parents[1]/"dashboard/space/assets/app.js").read_text(encoding="utf-8")
        self.assertIn('id="lookup-form"',ui)
        self.assertIn('id="lookup-code"',ui)
        self.assertIn('id="lookup-underlying"',ui)
        self.assertIn('value="option"',ui)
        self.assertIn('function lookup()',js)
        self.assertIn('function normalizeHK(',js)
        self.assertIn('NO VERIFIED STOCK RESEARCH',js)
        self.assertNotIn('DEEPSEEK_API_KEY',ui+js)
        self.assertNotIn('HF_TOKEN',ui+js)

    def test_missing_forecast_fails_closed(self):
        w,_,_,b=self.sample()
        result=snapshot(watchlist=w,fincept={},kronos={},kronos_backtest=b)
        self.assertEqual(result["stocks"][0]["fincept"]["status"],"UNAVAILABLE")
        self.assertIsNone(result["stocks"][0]["fincept"]["forecast_return_pct"])
        self.assertIsNone(safe_number(float("nan")))


if __name__ == "__main__":
    unittest.main()
