"""News sidecar compatibility, embedded Chinese and clickable PDF evidence."""
import os
from pathlib import Path
import tempfile
import unittest

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
