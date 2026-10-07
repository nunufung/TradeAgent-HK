# Telegram 最終文字總結

新增一則獨立、短小的 Telegram `sendMessage`，不為這段總結製作 PDF。原有詳細 PDF 及 cron（05:00 預建、07:00 發送、10:00 更新、平日 10:10 Mac Futu 更新）保留。

`final_summary.py` 沿用四分析員、投資辯論及風控整合後的 `stock_signals.json`，重新套用 `build_recommendations` 的同日／四報告／方向／時段／報價／保證金閘門。最多列三隻完整研究股票；有 Buy／Overweight 時優先列偏多研究名單，沒有時明確寫沒有新增買入推薦，列觀望或避免增持的股票。評級中性、缺報告、舊日期不會被轉成買入推介。

每隻股票只附短理由，取已有綜合論點的定性摘錄；不加入新分析員、不另發模型請求、不捏造目標價或倉位。時間顯示研究生成時刻，避免將預建研究當成即時行情。

期權最多一張已通過數值閘門的主候選，保留合約代碼、Put／Call、行使價、到期、DTE、Bid／Ask、Delta、Margin／Premium 及報價時間。現有完整風控缺口未補齊，因此候選仍明確寫等待，不開新倉；沒有候選、舊報價或收市後也不會生成開倉推薦。偏淡股票可研究 Short Call，必須先確認覆蓋／資金風控，不能把 Sell／Underweight 当作裸賣授權。

末尾只有一個「最終決定」。簡述 21–45 DTE、|Delta|≤0.10、Margin／Premium≤10x，以及原 Premium 盈利50–70%止盈／虧損>100%處理的條件規則；未取得現有持倉，不宣稱某個倉位須平倉／Roll。

生成 `recommendations.md/json` 時一併生成 `final_summary.txt`。05:00 artifact 保存這份文字，07:00 發送 PDF 後再送同日短文字；10:00 及指定股票請求亦送文字。Mac 的 PDF 與文字發送分開，缺中文字體或 PDF 發送失敗仍可送有效文字。自託管流程清除舊 `final_summary.txt`，避免查詢失敗後誤發上一輪文字。

`python final_summary.py --directory DIR` 可預覽；加 `--send` 使用現有 Telegram Secrets 發文字。傳送只印成功或安全錯誤摘要，不輸出 token、聊天 ID、API URL 或回應內容。
