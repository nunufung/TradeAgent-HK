# 急升後低 Delta Call 隔夜候選策略

自 2026-10-27 起接入 TradeAgent-HK 的每日推薦及 Telegram 摘要。狀態為候選研究，未做歷史盈利驗證，永不授權下單。

## 策略

正股當日急升後，研究賣出開倉 Call，期權本身須滿足 0 < Delta < 0.10。翌日權利金回落 20%–30% 即為止盈目標。百分比以初始實收權利金為分母，不是正股升跌幅或保證金回報；淨利另扣買賣費用及滑價。

本策略獨立於原策略的 50%–70% 止盈及 21–45 DTE 篩選，不更改四分析員評級或原有方向閘門。研究版按實際到期日計算 DTE，排除已到期及到期當日合約；其餘到期日只供分組研究，並非已驗證適合開倉。未指定止蝕、翌日未達標的退出時間、倉位上限；這些欄位保持 null，execution_eligible 永遠為 false。

「急升」暫以當日相對前收市升幅至少 5% 作可調研究門檻，這是實作預設，並非用戶已確認的有效門檻或回測結論。IV、事件、交收及帳戶風險必須人工查核；單靠股價上升不代表 Call 被高估。裸賣 Call 理論損失無上限，低 Delta 及預設止蝕都不能消除隔夜跳空風險。

## 手動輸入

沿用現有 TAHK_RESEARCH_INPUT_JSON 或本機 TAHK_RESEARCH_INPUT_PATH，不使用 Futu CSV。保留原 JSON 的 portfolio、journal 等欄位，新增 overnight_call。現有 GitHub 每日研究工作及 Telegram 指定股票研究工作會讀取同名 Secret。

以下是欄位示例，所有行情均為虛構，不能作交易建議；使用前必須換成有來源的當日實際資料和查核結果。quote_time 為整個快照的香港時間，包括 stock_change_pct（單位為百分點，例如 6 表示升 6%）。

```json
{
  "schema_version": 1,
  "overnight_call": {
    "surge_threshold_pct": 5,
    "candidates": [{
      "underlying": "HK.00005",
      "option_code": "HK.SYNTHETIC",
      "option_type": "CALL",
      "expiry": "2026-11-10",
      "quote_time": "2026-10-27T10:30:00+08:00",
      "source": "SYNTHETIC documentation example - replace with actual source",
      "verified": true,
      "stock_change_pct": 6,
      "spot": 100,
      "strike": 120,
      "delta": 0.08,
      "bid": 1,
      "ask": 1.1,
      "lot_size": 100,
      "volume": 10,
      "open_interest": 200,
      "initial_margin": 900,
      "event_risk": false,
      "iv_reviewed": true,
      "account_risk_reviewed": true,
      "assignment_reviewed": true
    }]
  }
}
```

initial_margin 是每張合約的實際初始保證金，與 bid × lot_size 的每張權利金比較，不可填入帳戶總保證金。IV 查核旗標不代表系統已獨立驗證波幅價值。covered／裸賣的分類、持股覆蓋及承受能力仍須人工覆核，不能由旗標推定安全。

只在周一至五香港時間 10:00–12:00、13:00–16:00 列出合約候選，假日及半日市仍須人工覆核。報價必須帶時區、同日、不在未來且不超過 30 分鐘；Call 須價外，OI 至少 100、成交量至少 1，買賣差價／中間價不超過 20%，保證金／按 Bid 權利金不超過 10 倍。不滿足條件不列出合約。

盤前晨報只展示策略和等待條件，不能確認當日尚未發生的急升。研究失敗的備用訊息亦會保留新策略及資料不足提示。沒有新盤中手動資料時，不會憑前一日報價捏造推薦。系統未新增盤中輪詢、翌日實盤持倉監察、止盈觸發通知或自動平倉；這些需要當前持倉及持續報價來源。

## 接入及驗證

- overnight_call.py 執行獨立確定性篩選，不增加 DeepSeek 呼叫。
- market_recommendations.write_recommendations 將結果寫入 recommendations.json、overnight_call.json、完整報告和 final_summary.txt。
- final_summary.py 的完整及壓縮摘要均保留新策略；既有單次 Telegram 晨報傳送流程不變。
- 20%／30% 買回參考價以 Bid × 0.8／0.7 計算，非保證成交價；成交後必須以實際權利金重算並依合約最小價格變動單位處理。
- tests/test_overnight_call.py 驗證數值邊界、時效、資料缺口、報告及 Telegram 傳送路徑；合成測試不代表回測勝率或收益。

本機驗證：python -m unittest discover -s tests -p test_overnight_call.py -v

## 本次驗證記錄

2026-10-27 本機：新策略 8 項、現有摘要 8 項、六模組工作流 12 項，共 28 項針對測試通過。全套執行 162 項，3 項失敗、5 項錯誤、3 項略過；與未修改基線相同，沒有新增失敗。Telegram 傳送測試使用 mock，尚未確認真實 Telegram 收件。

現存失敗項目如下；本次不更改原 token 預算或研究模組來掩蓋問題。

- ERROR: test_market_pdf_contains_news_and_codes_without_single_stock_price_card (test_market_briefing.MarketBriefingTests.test_market_pdf_contains_news_and_codes_without_single_stock_price_card)
- ERROR: test_news_pdf (unittest.loader._FailedTest.test_news_pdf)
- ERROR: test_pdf_puts_decision_before_news_overview (test_professional_report.ProfessionalReportTests.test_pdf_puts_decision_before_news_overview)
- ERROR: test_recommendations_and_four_actual_excerpts_survive_pdf (test_recommendations.RecommendationPDFTests.test_recommendations_and_four_actual_excerpts_survive_pdf)
- ERROR: test_single_stock_pdf_keeps_its_recommendation_section (test_recommendations.SharedStockReportTests.test_single_stock_pdf_keeps_its_recommendation_section)
- FAIL: test_daily_pipeline_propagates_book_context_and_records_its_fingerprint (test_book_skill_context.BookSkillTests.test_daily_pipeline_propagates_book_context_and_records_its_fingerprint)
- FAIL: test_daily_profile_preserves_actual_four_analysts_and_limits_generation (test_daily_budget.DailyBudgetTests.test_daily_profile_preserves_actual_four_analysts_and_limits_generation)
- FAIL: test_gateway_forwards_once_clamps_output_and_blocks_exhausted_calls (test_daily_transport.DailyTransportTests.test_gateway_forwards_once_clamps_output_and_blocks_exhausted_calls)

其中五項 PDF 錯誤源於本機缺中文字型，書籍流程測試遇到 ModuleNotFoundError，兩項 token 測試預期 800 但原程式回傳 1600。
