import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from market_recommendations import build_recommendations, render_recommendations
from final_summary import render_final_summary

NOW = datetime(2026, 10, 9, 9, tzinfo=ZoneInfo('Asia/Hong_Kong'))

def payload():
    reports = {
        'market': '# 技術報告\n## 一、核心結論摘要\n股價仍處於下行趨勢，反彈力度有限。\n## 指標\n' + '| 指標 | 數值 |\n' * 100,
        'social': 'Overall Sentiment: Neutral (Score: 5.0/10) Confidence: Low\n資料擷取失敗，沒有取得有效情緒樣本。',
        'news': '# 新聞報告\n## 執行摘要\n本批次未取得公司專屬新聞，事件日曆尚未核實。',
        'fundamentals': '# 基本面報告\n## 執行摘要\n估值缺乏明確安全邊際，現金流資料仍有缺口。',
    }
    return {'date': '2026-10-09', 'analyst_set': list(reports), 'signals': {'HK.00388': {
        'rating': 'Underweight', 'analysis_complete': True,
        'analysts': {k: {'complete': True} for k in reports}, 'reports': reports,
        'decision': 'Rating: Underweight\nExecutive Summary: 綜合研究偏向降低正股曝險，相關價位須核實。\nInvestment Thesis: ' + '長篇辯論。' * 200,
    }}}

class ProfessionalReportTests(unittest.TestCase):
    def test_concise_research_retains_evidence_and_missing_data(self):
        text = render_recommendations(build_recommendations(payload(), now=NOW))
        for heading in ['決策摘要', '股票研究', '期權評估', '執行計劃', '資料說明']:
            self.assertIn(heading, text)
        self.assertLess(text.index('期權評估'), text.index('股票研究'))
        self.assertIn('股價仍處於下行趨勢', text)
        self.assertIn('沒有取得有效情緒樣本', text)
        self.assertNotIn('原文摘錄', text)
        self.assertNotIn('| 指標 |', text)
        self.assertNotIn('長篇辯論', text)
        self.assertLess(len(text), 2500)

    def test_bearish_rating_is_research_not_short_call_instruction(self):
        text = render_recommendations(build_recommendations(payload(), now=NOW))
        self.assertIn('研究方向', text)
        self.assertNotIn('策略建議：Short Call', text)
        self.assertIn('不構成開倉指令', text)
        self.assertIn('50–70%', text)
        self.assertIn('100%', text)

    def test_telegram_leads_with_decision_and_keeps_one_conclusion(self):
        text = render_final_summary(payload(), now=NOW)
        self.assertIn('決策摘要', text.splitlines()[0])
        self.assertLess(text.index('期權：'), text.index('正股：'))
        self.assertNotIn('最終決定：', text)

    def test_pdf_puts_decision_before_news_overview(self):
        import tempfile
        from pathlib import Path
        from pypdf import PdfReader
        import generate_pdf as pdf
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.pdf'
            report = pdf.ReportSummary(filename='report_market.md', ticker='港股市場', date='2026-10-09',
                action='REVIEW', price='-', confidence='-', decision='市場概覽測試',
                highlights=[], warnings=[], data_quality='待核實', raw_text='',
                market_metadata={'watchlist_count': 23}, news_text='',
                recommendation_text=render_recommendations(build_recommendations(payload(), now=NOW)))
            pdf.build_pdf([report], str(path))
            text = '\n'.join(page.extract_text() for page in PdfReader(path).pages)
            self.assertLess(text.index('決策摘要'), text.index('市場新聞概覽'))
            for page in PdfReader(path).pages:
                page_text = page.extract_text()
                if '資料說明' in page_text:
                    self.assertIn('研究方法', page_text)

if __name__ == '__main__':
    unittest.main()
