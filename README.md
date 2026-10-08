# TradeAgent-HK v4.4

## Book-to-skill

官方 book-to-skill 工具已加入；現有 Psychology of Money 風控 Skill 會載入每日及 Telegram 的四分析員流程。
轉換方式、資料來源限制及載入紀錄見 [BOOK_TO_SKILL.md](BOOK_TO_SKILL.md)。

香港市場專用智能交易Agent

### 一、核心評分系統
- 0-10分制，每日掃描 Watchlist
- 技術面 40% (RSI, MACD, 均線, 成交量)
- 基本面 30% (業績, 估值, 行業趨勢)
- 市場情緒 30% (資金流, 新聞)
- >7.5分 做多 / <4.5分 做空 / 中間觀望

### 二、期權法則
1. 方向：>7.5買Call/牛差，<4.5買Put/熊差
2. 止賺：+50%考慮賣一半並將止蝕移至入場價，+100%必須止賺
3. 止蝕：-50%考慮斬倉，-100%硬止蝕本(全斬)
4. 時間過濾：09:30-10:00 HKT 不開新期權倉，10:00後才入場 (止蝕單除外)
5. 到期日：最少30日，建議30-60日

### 三、倉位及手數規則 (與期權獨立)
- 每單最大虧損 <2% 總資金
- 正股：港股400股/手，美股100股/手
- 期權：按張數計算

### 四、自動化功能
- 自動計算 Payoff圖 / Breakeven / 止賺止蝕線
- WhatsApp / Telegram 10:00 HKT後推送
- Watchlist + Total Marks 雲端同步

### 五、外部連接
- 行情：HKEX, Yahoo Finance, Investing.com期權鏈
- 數據：AASTOCKS, 經濟通, TradingView
- 執行：富途 / 耀才 API (需手動確認)
- 通知：WhatsApp + Telegram

## Architecture Map v4.4

Flow: Config & Controls → Multi-Agent Stock Scoring + Option Rules (Expiry min 30d, Stop -100% hard) → External Connections → Fusion Final = Trade*0.6 + Option*0.4

- Option Rules v4.4: Direction >7.5→Call / <4.5→Put, TP +50% consider / +100% must, SL -50% consider / -100% hard stop, No new 09:30-10:00 HKT, Expiry min 30 days
- Lot rules separated from Option rules
- TradeAgent-HK PDF Upgrade
=========================

Files to replace/add in your GitHub repository:

1. Add generate_pdf.py at the repository root.
2. Replace .github/workflows/hk-daily.yml with the included version.
3. Replace requirements.txt with the included version (same current packages + reportlab).

What changes:
- TradingAgents report logic remains in hk_adapter.py and is not modified.
- Clean report_*.md files remain available as audit output.
- Verbose console output is stored as run_*.log instead of overwriting report_*.md.
- A styled PDF is created in pdf_reports/.
- Telegram sends the PDF via sendDocument instead of sending the full raw text.
- GitHub artifacts retain Markdown, log, and PDF files.
- Telegram/PDF failure is non-blocking for the underlying report run.

After committing, manually run Actions > HK Daily Report with ticker 700 and check Telegram.

<img width="536" height="379" alt="Screenshot 2026-10-03 at 11 12 11 AM" src="https://github.com/user-attachments/assets/660b6a82-d449-473e-bb50-398a743acbe9" />
