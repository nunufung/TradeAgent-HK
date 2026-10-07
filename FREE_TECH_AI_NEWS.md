# 免費科技／AI 市場資訊

現有四位 TradingAgents 分析員會收到最近七日的科技／AI 新聞候選。新聞分析員篩選最多五條重要消息，說明事件、潛在市場影響、港股關聯及不確定性，並列出來源、刊登日期和原文連結。

## 來源

| 來源 | 類型 | 免費 RSS／Atom |
| --- | --- | --- |
| OpenAI | 企業官方公告 | https://openai.com/news/rss.xml |
| NVIDIA | 企業官方公告 | https://blogs.nvidia.com/feed/ |
| Google AI | 企業官方公告 | https://blog.google/technology/ai/rss/ |
| Microsoft | 企業官方公告 | https://blogs.microsoft.com/feed/ |
| TechCrunch AI | 媒體報道 | https://techcrunch.com/category/artificial-intelligence/feed/ |
| The Register AI | 媒體報道 | https://www.theregister.com/software/ai_ml/headlines.atom |
| 香港電台財經 | 媒體報道，篩選科技／AI 關鍵字 | https://rthk.hk/rthk/news/rss/c_expressnews_cfinance.xml |

讀取公開 feed 的標題、短摘要、日期和連結；不繞過付費牆，不下載全文，不需要新增新聞 API key。分析沿用已設定的 DeepSeek；原有模型費用仍適用。

## 分析流程與輸出

`free_tech_news.py` 同時讀取來源，限制每個來源的讀取時間，去除重複消息、過期／未來／無日期消息和無效連結。企業公告與獨立媒體分開標示。公司名稱匹配只代表候選相關性，未確認的港股關聯由分析員標示為推論。

`hk_adapter.py` 及 `linked_stock_analysis.py` 把候選資料放入分析員的 instrument context，並把現有 `get_news`／`get_global_news` 工具接到 `free_rss`。所有 RSS 失敗時，工具沿用免費 Yahoo 新聞後備來源。行情、財務、社交及期權工具保持各自來源；新聞不是期權報價。

- `report_####.md`：股票最終判斷。
- `news_####.md`：新聞分析員報告及可核對候選來源。候選清單不代表全部獲採納。
- `free_news_####.json`：本次來源狀態、抓取時間和候選資料。
- 日報／Telegram 股票查詢 PDF：新增「科技／AI 市場資訊」章節，保留中文、日期及可點擊原文 URL。
- Futu 流程：新聞參與四位分析員的股票評級與期權方向閘門；完整新聞報告保存在 Actions artifact。Telegram 的期權摘要沿用原有發送方式。

來源暫時不能讀取時，報告標示覆蓋不足，不會補造消息。沒有直接公司新聞時，產業消息不可當成該公司已確認的事件。

## 排程與檢查

現有 HK Daily 的 05:00 香港時間預製、07:00 發送、10:00 產生及發送維持原設定。Futu 的 10:10 工作日排程及 Telegram 查詢排程維持原設定。GitHub 排程實際啟動時間仍可能延遲。

免費新聞檢查工作流程只做來源讀取和程式／PDF測試，不使用交易、Telegram 或模型 secrets。

需要即時檢查完整報告時，在 Actions → HK Daily Report → Run workflow，選擇 `main` 並填入 `700` 或其他港股代號；新一輪分析完成後沿用現有 Telegram PDF 發送。

本地來源檢查：

```bash
python free_tech_news.py --output free_news_preview.json
python -m unittest discover -s tests -p 'test_free_tech_news.py' -v
```
