"""Render observed Fincept results without turning forecasts into trade approvals."""

def render(data,windows):
    lines=['# Fincept ARIMA：藍籌真實預測與回測','',f"產生時間：{data['generated_at']}；行情截至：{data['data_cutoff']}。",'','實際調用固定版本 Fincept statsmodels_wrapper/timeseries_models.py 的 forecast_arima；不是整個桌面終端、AI代理團隊或獨立行情認證。','',f"來源：[Fincept原始模組](https://github.com/Fincept-Corporation/FinceptTerminal/blob/{data['source_commit']}/{data['module']})。SHA256：`{data['module_sha256']}`。",'', '方法：400個已完成交易日的調整收市價，取log後固定ARIMA(1,1,1)，逐期重新估計，預測5個HKEX交易日，再以exp轉回點預測。沒有依本次結果選階數／調參；不是校準的預測區間或期權盈利機率。','', '| 標的 | 新預測狀態 | 五日點預測回報 | 有效回測/嘗試 | 方向命中 | 模型MAE | 不變基準MAE |','|---|---|---:|---:|---:|---:|---:|']
    for row in data['forecasts']:
        m=(data['stock_metrics'] or {}).get(row['ticker'],{})
        p=m.get('predicted',{});n=p.get('direction_n',0)
        hit=f"{p['direction_correct']}/{n} ({p['direction_correct']/n:.1%})" if n else 'N/A'
        mae=f"{100*p['mae']:.4f}" if p else 'N/A';base=f"{100*m['zero']['mae']:.4f}" if p else 'N/A'
        predicted=f"{row['endpoint_return']:+.3%}" if row['status']=='FORECAST_ONLY' else 'N/A'
        label='可用' if row['status']=='FORECAST_ONLY' else row.get('forecast_error',row.get('error','不可用'))
        lines.append(f"| {row['ticker']} {row['name']} | {label} | {predicted} | {m.get('valid',0)}/{m.get('attempted',0)} | {hit} | {mae} | {base} |")
    lines+=['','MAE為五日回報的百分點，愈低愈好。回測模式使用每股24個不重疊目標區間；誤差只比較相同有效時段。實際回報為零的時段仍計誤差，但不計方向命中分母。缺失、日期不符、非收斂的窗口不會以價格不變冒充模型結果。']
    m=data.get('metrics')
    if m and m.get('valid'):
        p=m['predicted'];n=p['direction_n']
        lines+=['',f"合併回測：有效{m['valid']}/{m['attempted']}；方向{p['direction_correct']}/{n}（{p['direction_correct']/n:.1%}）；模型MAE {100*p['mae']:.5f}、價格不變 {100*m['zero']['mae']:.5f}、20日趨勢基準 {100*m['trend']['mae']:.5f} 個百分點。",'', '模型與價格不變基準的差距須連同覆蓋率及失敗比例解讀；微小差距不能當作已驗證交易優勢。尚未做顯著性檢定或扣除交易成本。']
    if windows:lines+=['',f"預測起點：{min(w['origin'] for w in windows)} 至 {max(w['origin'] for w in windows)}；目標期末：{min(w['target'] for w in windows)} 至 {max(w['target'] for w in windows)}。"]
    lines+=['','## 資料及限制','', '- 股票範圍來自GitHub market_watchlist.json的bluechip分組，包含2800 ETF，並非完整或經認證恒指成分股名單。','- Yahoo Finance/yfinance，auto_adjust=True；下載時點調整價格不是當時可得資料快照，也未與港交所或另一獨立供應商逐日核對。','- 拒絕日期缺失、不合法價格及模型未收斂；沒有修改價格、填補未成交的K線，或以另一個模型替代失敗預測。','- 同日期各股票高度相關，不能把所有窗口當成獨立實驗；當前觀察名單亦存在選樣／生存者偏差。','- 這是預測誤差驗證，不是扣除費用、滑點後的股票或期權策略收益驗證；不授權下單。','', '## 每日報告接駁','', '- 獨立03:07 HKT運算，早報只讀取已保存artifact；不增加DeepSeek調用。','- 摘要包含有效標的數、資料截止日及各股五日情景範圍，並保留四分析員及期權風控。','- 超過26小時或schema／來源版本不合格顯示暫無有效新預測，不啟動臨時模型運算、不延後既定發送時限。','- 有執行回測時，歷史逐期資料見windows.csv；新預測、資料指紋、版本、失敗原因及回測指標見fincept_forecast.json。實際Telegram收件另以delivery receipt驗證。']
    return '\n'.join(lines)+'\n'
