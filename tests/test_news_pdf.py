"""News sidecar compatibility, embedded Chinese and clickable PDF evidence."""
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import chdir

from pypdf import PdfReader
import generate_pdf as pdf

NEWS = """# 科技／AI 市場資訊（新聞分析員篩選）
## 測試資料：人工智能與雲端業務
事件：測試資料用來驗證中文排版，並非真實市場新聞。
影響：產業相關性屬推論，不能代替公司公告或真實期權報價。
來源：[官方測試連結](https://example.com/ai?one=1&two=2)，日期：2026-10-07。
## 可核對來源（候選清單，並非全部獲分析員採納）
| 標題 | 日期 | 來源 |
| --- | --- | --- |
| 中文科技／AI 測試標題 | 2026-10-07 | https://example.com/news |
"""


class NewsPDFTests(unittest.TestCase):
    def test_verified_price_does_not_use_historical_insider_trade(self):
        with tempfile.TemporaryDirectory() as directory, chdir(directory):
            path = Path('report_0700.md')
            path.write_text('# 0700.HK 2026-10-07\n評級：Sell\n', encoding='utf-8')
            Path('run_700.log').write_text('Sale at price 64.24 per share.\nName: get_verified_market_snapshot\n\n## Verified market data snapshot for 0700.HK\n\n- Requested analysis date: 2026-10-07\n- Latest trading row used: 2026-10-07\n\n### Latest verified OHLCV row\n\n| Field | Value |\n|---|---:|\n| Close | 420.40 |\n================================== Ai Message\n', encoding='utf-8')
            self.assertEqual(pdf.parse_report(str(path)).price, 'HK$420.40')

    def test_no_verified_price_uses_no_unrelated_log_price(self):
        with tempfile.TemporaryDirectory() as directory, chdir(directory):
            path = Path('report_0700.md')
            path.write_text('# 0700.HK 2026-10-07\n評級：Sell\n**Price Target**: 411\n', encoding='utf-8')
            Path('run_700.log').write_text('Sale at price 64.24 per share.', encoding='utf-8')
            self.assertEqual(pdf.parse_report(str(path)).price, '-')

    def test_wrong_ticker_and_future_snapshots_cannot_supply_price(self):
        with tempfile.TemporaryDirectory() as directory, chdir(directory):
            path = Path('report_0700.md')
            path.write_text('# 0700.HK 2026-10-07\n評級：Hold\n', encoding='utf-8')
            Path('run_700.log').write_text('Name: get_verified_market_snapshot\n\n## Verified market data snapshot for 0005.HK\n- Requested analysis date: 2026-10-07\n- Latest trading row used: 2026-10-07\n\n### Latest verified OHLCV row\n| Field | Value |\n|---|---:|\n| Close | 64.24 |\n================================== Ai Message\nName: get_verified_market_snapshot\n\n## Verified market data snapshot for 0700.HK\n- Requested analysis date: 2026-10-07\n- Latest trading row used: 2026-10-08\n\n### Latest verified OHLCV row\n| Field | Value |\n|---|---:|\n| Close | 421.00 |\n================================== Ai Message\n', encoding='utf-8')
            self.assertEqual(pdf.parse_report(str(path)).price, '-')

    def test_decision_summary_starts_with_executive_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'report_0700.md'
            path.write_text('# 0700.HK 2026-10-07\n評級：Sell\n**Executive Summary**: 應先核對行情與公司事件，再按已有持倉評估風險。\n\n**Investment Thesis**: '+('長篇分析內容。'*300)+'\n\n**Price Target**: 411\n', encoding='utf-8')
            summary=pdf.parse_report(str(path)).decision
            self.assertTrue(summary.startswith('應先核對行情'))
            self.assertNotIn('長篇分析內容',summary)

    def test_key_signals_do_not_quote_agent_planning_messages(self):
        with tempfile.TemporaryDirectory() as directory, chdir(directory):
            path=Path('report_0700.md')
            path.write_text('# 0700.HK 2026-10-07\n評級：Hold\n需覆核股票風險及實際部位。',encoding='utf-8')
            Path('run_700.log').write_text("I'll gather evidence across company news, global macro, macro indicators and prediction markets in parallel.",encoding='utf-8')
            self.assertFalse(any("I'll gather" in item for item in pdf.parse_report(str(path)).highlights))

    def test_canonical_sidecar_and_five_tier_rating_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report_700.md"
            path.write_text("# 0700.HK 2026-10-07\n評級：Overweight\n需覆核股價及風險。", encoding="utf-8")
            (path.parent / "news_0700.md").write_text(NEWS, encoding="utf-8")
            report = pdf.parse_report(str(path))
            self.assertEqual(report.news_text, NEWS)
            self.assertEqual(report.action, "OVERWEIGHT")
            (path.parent / "news_0700.md").unlink()
            self.assertEqual(pdf.parse_report(str(path)).news_text, "")

    def test_news_links_keep_urls(self):
        paragraphs = pdf.news_flowables(NEWS, pdf.build_styles())
        content = "\n".join(paragraph.getPlainText() for paragraph in paragraphs)
        self.assertIn("https://example.com/ai?one=1&two=2", content)
        self.assertIn("並非真實市場新聞", content)
        self.assertTrue(content.splitlines()[-1].endswith("https://example.com/news"))

    def test_pdf_contains_chinese_news_sources_and_link_annotations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report_0700.md"
            path.write_text("# 0700.HK 2026-10-07\n評級：Hold\n需覆核股價及風險。", encoding="utf-8")
            (path.parent / "news_0700.md").write_text(NEWS, encoding="utf-8")
            output = Path(os.getenv("TAHK_PDF_TEST_OUTPUT", str(path.parent / "report.pdf")))
            output.parent.mkdir(parents=True, exist_ok=True)
            pdf.build_pdf([pdf.parse_report(str(path))], str(output))
            reader = PdfReader(output)
            text = "\n".join(page.extract_text() for page in reader.pages)
            self.assertGreaterEqual(len(reader.pages), 2)
            self.assertIn("人工智能", text)
            self.assertIn("https://example.com/news", text)
            urls = [annotation.get_object()["/A"].get("/URI") for page in reader.pages for annotation in page.get("/Annots", []) if "/A" in annotation.get_object()]
            self.assertIn("https://example.com/ai?one=1&two=2", urls)
            fonts = [font.get_object() for page in reader.pages for font in page["/Resources"]["/Font"].get_object().values()]
            self.assertTrue(any("WenQuanYi" in str(font.get("/BaseFont", "")) for font in fonts))


if __name__ == "__main__":
    unittest.main()
