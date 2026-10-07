"""Keyless news validation, analyst routing and date/source provenance."""
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape

import free_tech_news as news

NOW = datetime(2026, 10, 7, 5, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=7)


def rss_item(title="Tencent AI cloud update", url="https://example.com/news", date="Wed, 07 Oct 2026 04:00:00 GMT"):
    return f"<item><title>{escape(title)}</title><link>{escape(url)}</link><pubDate>{date}</pubDate><description>&lt;b&gt;AI platform&lt;/b&gt;</description></item>"


def feed(*items):
    return ("<rss><channel>" + "".join(items) + "</channel></rss>").encode()


def batch():
    rows = news.parse_feed(feed(rss_item()), "Test official", "official", now=NOW, start=START)
    return {"fetched_at": NOW.isoformat(), "sources": [{"source": "Test official", "status": "ok"}], "articles": [news.asdict(row) for row in rows]}


class FeedTests(unittest.TestCase):
    def test_only_current_dated_technology_items_reach_analysis(self):
        rows = news.parse_feed(feed(
            rss_item(),
            rss_item(date="Mon, 21 Sep 2026 04:00:00 GMT"),
            rss_item(date="Thu, 08 Oct 2026 04:00:00 GMT"),
            rss_item(date="2026-10-07T04:00:00"),
            rss_item(url="javascript:alert(1)"),
            rss_item(url="https://[invalid"),
        ), "A", "official", now=NOW, start=START)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].published_at, "2026-10-07T04:00:00+00:00")
        self.assertEqual(rows[0].summary, "AI platform")
        self.assertEqual(rows[0].source_type, "official")

    def test_non_technology_items_are_excluded(self):
        data = b"<rss><channel><item><title>Local weather today</title><link>https://example.com/weather</link><pubDate>Wed, 07 Oct 2026 04:00:00 GMT</pubDate></item></channel></rss>"
        self.assertEqual(news.parse_feed(data, "A", "media", now=NOW, start=START), [])

    def test_atom_alternate_link_and_timestamp(self):
        data = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>GPU chip update</title><link rel="self" href="https://example.com/feed"/><link rel="alternate" href="https://example.com/story?utm_source=x&amp;id=2"/><published>2026-10-07T12:00:00+08:00</published><summary>Semiconductor news</summary></entry></feed>'
        rows = news.parse_feed(data, "A", "media", now=NOW, start=START)
        self.assertEqual(rows[0].url, "https://example.com/story?id=2")
        self.assertIn("Semiconductors", rows[0].topics)

    def test_unsafe_xml_and_credentials_are_rejected(self):
        with self.assertRaises(ValueError):
            news.parse_feed(b'<!DOCTYPE rss [<!ENTITY x "AI">]><rss/>', "A", "media", now=NOW, start=START)
        with self.assertRaises(ValueError):
            news.parse_feed(b'<html><body>Sign in</body></html>', "A", "media", now=NOW, start=START)
        self.assertEqual(news.canonical_url("https://user:password@example.com/story"), "")
        self.assertEqual(news.canonical_url("file:///etc/passwd"), "")
        self.assertEqual(news.plain_text("<script>invisible</script><b>人工智能</b>", 100), "人工智能")

    def test_partial_failure_and_duplicates_do_not_destroy_good_sources(self):
        article = news.parse_feed(feed(rss_item()), "A", "official", now=NOW, start=START)[0]
        outcomes = [([article], {"source": "A", "status": "ok"}), ([article], {"source": "B", "status": "ok"}), ([], {"source": "C", "status": "unavailable"})]
        with patch.object(news, "SOURCES", (1, 2, 3)), patch.object(news, "_download", side_effect=lambda source, **_: outcomes[source - 1]):
            result = news.collect_news(now=NOW)
        self.assertEqual(len(result["articles"]), 1)
        self.assertEqual(result["sources"][2]["status"], "unavailable")

    def test_failure_output_contains_only_sanitized_error_type(self):
        with patch.object(news.urllib.request, "urlopen", side_effect=RuntimeError("private diagnostic contents")):
            rows, status = news._download(("A", "https://example.com/feed", "official"), now=NOW, start=START)
        self.assertEqual(rows, [])
        self.assertEqual(status, {"source": "A", "status": "unavailable", "error_type": "RuntimeError"})


class AnalystTests(unittest.TestCase):
    def test_direct_company_match_and_hong_kong_date_cutoff(self):
        data = batch()
        older = {**data["articles"][0], "title": "Latest generic AI story", "published_at": "2026-10-07T04:30:00+00:00", "url": "https://example.com/latest"}
        data["articles"].append(older)
        rows = news.select_articles(data, "0700.HK", "2026-10-07", "2026-10-07")
        self.assertEqual(rows[0]["title"], "Tencent AI cloud update")
        self.assertTrue(rows[0]["company_match"])
        self.assertFalse(rows[1]["company_match"])
        self.assertFalse(any(row["company_match"] for row in news.select_articles(data, "2800.HK")))
        data["articles"][0]["published_at"] = "2026-10-06T17:00:00+00:00"
        self.assertEqual(len(news.select_articles(data, "700", "2026-10-07", "2026-10-07")), 2)

    def test_source_diversity_is_retained(self):
        data = batch()
        data["articles"] = [{**data["articles"][0], "title": f"AI update {i}", "url": f"https://example.com/{i}", "source": "A" if i < 10 else "B"} for i in range(12)]
        rows = news.select_articles(data, limit=18)
        self.assertEqual(sum(row["source"] == "A" for row in rows), 4)
        self.assertEqual(sum(row["source"] == "B" for row in rows), 2)

    def test_graph_keeps_identity_and_passes_evidence_to_initial_context(self):
        graph = types.SimpleNamespace(resolve_instrument_context=lambda ticker, asset_type, date: f"Resolved identity: {ticker}; asset: {asset_type}; date: {date}")
        news.attach_news_context(graph, batch())
        context = graph.resolve_instrument_context("0700.HK", "stock", "2026-10-07")
        self.assertIn("Resolved identity: 0700.HK", context)
        evidence = json.loads(context.split("UNTRUSTED_RSS_DATA\n")[1].split("\nEND_UNTRUSTED_RSS_DATA")[0])
        self.assertEqual(evidence["candidates"][0]["url"], "https://example.com/news")
        self.assertEqual(evidence["window"], ["2026-09-30", "2026-10-07"])

    def test_news_tools_use_current_graph_config_and_fail_to_fallback(self):
        current = ContextVar("current_graph")
        config_module = types.ModuleType("tradingagents.dataflows.config")
        config_module.get_config = lambda: current.get()
        router = types.ModuleType("tradingagents.dataflows.router")
        router.VENDOR_METHODS = {"get_news": {"yfinance": object()}, "get_global_news": {"yfinance": object()}}
        error_module = types.ModuleType("tradingagents.dataflows.errors")
        error_module.VendorUnavailableError = type("VendorUnavailableError", (Exception,), {})
        package = types.ModuleType("tradingagents.dataflows")
        package.router = router
        stubs = {"tradingagents": types.ModuleType("tradingagents"), "tradingagents.dataflows": package, "tradingagents.dataflows.router": router, "tradingagents.dataflows.config": config_module, "tradingagents.dataflows.errors": error_module}
        config = {"tool_vendors": {"get_stock_data": "yfinance"}}
        with patch.dict(sys.modules, stubs):
            news.configure_free_news(config, batch=batch())
            self.assertEqual(config["tool_vendors"]["get_stock_data"], "yfinance")
            current.set(config)
            output = router.VENDOR_METHODS["get_news"]["free_rss"]("700", "2026-10-01", "2026-10-07")
            self.assertIn("Tencent AI cloud update", output)
            self.assertIn("https://example.com/news", router.VENDOR_METHODS["get_global_news"]["free_rss"]("2026-10-07", 7, 5))
            current.set({"tech_ai_news": {"sources": [{"status": "unavailable"}]}})
            with self.assertRaises(error_module.VendorUnavailableError):
                router.VENDOR_METHODS["get_news"]["free_rss"]("700", "2026-10-01", "2026-10-07")

    def test_audit_distinguishes_selected_report_from_candidate_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            news.write_news_audit(batch(), "0700.HK", "分析員：需觀察雲端業務的後續證據。", root)
            report = (root / "news_0700.md").read_text(encoding="utf-8")
            self.assertIn("分析員：需觀察", report)
            self.assertIn("候選清單，並非全部獲分析員採納", report)
            self.assertIn("2026-10-07 12:00 HKT", report)
            self.assertEqual(json.loads((root / "free_news_0700.json").read_text())["articles"][0]["url"], "https://example.com/news")
            news.write_news_audit(batch(), "700", "", root)
            self.assertIn("未經分析員確認", (root / "news_0700.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
