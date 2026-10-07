# 四分析員推薦與期權守則

每日市場 PDF 在新聞前增加「四分析員推薦與期權紀律」。保留 23 隻新聞觀察名單；從當日入選新聞的直接公司關聯挑三隻研究股票，保留至少一隻藍籌及一隻科技股。沒有公司新聞時按日期輪換，不固定 700。三隻股票是研究名單，並非已確認具備合格期權鏈。

同一批 publisher／日期篩選後的市場新聞直接傳入四分析員的 RSS 工具及背景；拒絕的原始 RSS 不會加入。每隻研究股實際執行 TradingAgents 的 market、social、news、fundamentals 四位分析員及既有投資辯論／風控整合。stock_signals.json 保存同日評級、四份原文及綜合決策；stock_analysis.md 保存完整四份論證。PDF 顯示各分析員原文摘錄及綜合決策，長文可在 Actions artifact 查閱。模型評級為研究意見，模型文字中的價位仍須核對行情；四份報告齊備不代表已完成原始數據驗證。

方向連動：Buy/Overweight → 條件式 Short Put；Underweight/Sell → 條件式 Short Call；Hold/REVIEW、舊日期或分析缺失 → 不做。此處是賣期權策略，不能當作買入 Call/Put 指示。

## 時間與行情

- 05:00 HKT：雲端建市場新聞及三隻股票四分析員研究；不連 Mac、不送 Telegram。
- 07:00 HKT：送當日預建 PDF；開倉結論只能「等待」或「不做」。
- 10:00 HKT：原有雲端更新仍保留，沒有 Mac 的即時合約資料時清楚寫等待 Futu。
- 10:10 HKT 平日：原有 self-hosted macOS Futu 工作流，先嘗試取當日已完成的雲端研究 artifact，再從本機 OpenD 更新期權鏈及實際初始保證金。不成功則 Mac 建新的新聞及三隻股票研究。手動輸入 tickers 時，使用指定股票重新分析。更新結果以 PDF 送 Telegram；Mac 沒有可嵌入的中文字體時，改送清楚標示的文字並保留完整 artifact。

排程 cron 不變；GitHub Actions 可能排隊或延遲。四分析員增加模型用量及預建時間。Mac runner、OpenD 必須在線。

Mac PDF 優先使用 repository variable `TAHK_CJK_FONT` 指向本機 TrueType 中文字體；亦探測 `/Library/Fonts/Arial Unicode.ttf` 及 `/System/Library/Fonts/Supplemental/Arial Unicode.ttf`。找不到字體不產生缺字 PDF。

## 完整守則與推薦上限

採用使用者附件 `02-HKEX-Options-Trading-Rules.docx`，配合原有數值閘門：21–45 DTE、|Delta| ≤0.10、Spread ≤30%、OI ≥100、Volume ≥1、實際 Margin/Premium ≤10x、報價 ≤30分鐘。正常平日只在 10:00–12:00／13:00–16:00 內考慮；假期／半日市另需查核。

最多一張主候選，列合約代碼、Put/Call、行使價、到期、DTE、正股、Bid/Ask/Mid、Delta、IV、成交量、OI、報價時間、每張 Gross Premium 及實際初始保證金。Premium 按 Bid×lot_size、未扣費用，不保證成交。

目前 Futu 數值篩選尚未提供下列完整風控證據：行使價低於重要支持／高於重要阻力、IV 相對歷史高低、到期前完整事件及長假期日曆、實際帳戶現金／buffer／接貨能力／Call 持股覆蓋。**因此即使有數值合格候選，這版本仍明確標「等待完整風控覆核」，不自動宣稱「做」或全部合規。** 不以模型評級或 RSS 沒有事件代替風控證據。行情資料缺口是等待，完整掃描無合格合約是不做。

PDF 同時列出條件式管理守則：盈利達原收 Premium 50–70% 止盈；虧損超過原收 Premium 100% 平倉／減倉／合規 Roll；DTE <21/<14/<7/<3 日分級管理，Roll 須新 DTE 21–45、較安全行使價、額外收入及不擴大總倉位。尚未接入當前持倉和開倉成本，不捏造倉位損益或平倉／Roll 個案。

此流程只讀取行情／保證金及發送分析，不下單。不增加新 API key；沿用現有 GitHub Secrets，錯誤只顯示類型或安全摘要。

## 驗證

`python -m unittest discover -s tests -v`；PDF 測試需先安裝 WQY/DejaVu，或設定 `TAHK_CJK_FONT`。測試覆蓋新聞選股、晨報等待、舊／不完整評級封鎖、中性不做、部分行情不能冒充完整守則、實際四分析員證據在中文 PDF 可讀、NaN/Inf 數據封鎖及午間／收市後不開倉。
