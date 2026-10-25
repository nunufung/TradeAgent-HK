"""Combine independently executed watchlist audits, including missing/failed stocks."""
import argparse,csv,json
from pathlib import Path
from kronos_backtest import metrics

def build(inputs,output,watchlist):
    watch=json.loads(Path(watchlist).read_text())
    stocks=[s for s in watch['stocks'] if s['group']=='bluechip']
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'watchlist.json').write_text(json.dumps(watch,ensure_ascii=False,indent=2))
    all_rows=[];summary=[];provenance={}
    for stock in stocks:
        code=stock['code'];matches=list(Path(inputs).glob('**/'+code+'/results.json'))
        if not matches:matches=list(Path(inputs).glob('**/'+code+'-results.json'))
        if len(matches)!=1:
            summary.append(dict(ticker=code,name=stock['name'],status='FAILED_OR_MISSING',metrics=None));continue
        data=json.loads(matches[0].read_text());rows=data['records']
        assert len(rows)==24 and all(r['ticker']==code for r in rows)
        all_rows+=rows;summary.append(dict(ticker=code,name=stock['name'],status='COMPLETED',metrics=metrics(rows)))
        provenance[code]={k:v for k,v in data.items() if k not in ['records','metrics']}
    result={'scope':'GitHub watchlist bluechip routing group, not a certified HSI constituent list; includes 2800 ETF','stocks':summary,'pooled':metrics(all_rows) if all_rows else None,'provenance':provenance}
    (output/'metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    with (output/'windows.csv').open('w') as f:
        fields=['ticker','origin','target','actual','predicted','zero','trend','valid'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in all_rows)
    lines=['# GitHub 藍籌觀察分組：Kronos 回測','', '固定設定：400日歷史、五交易日預測、small模型、base tokenizer、5路徑平均、seed 42、CPU、批次4。每股獨立程序重置seed，故與之前兩股連續執行時的隨機路徑未必逐一相同。沒有按本次結果調參。','', '範圍為GitHub當時bluechip分組16個標的，包括2800 ETF，並非經認證的完整恒指成分股名單。行情仍為Yahoo Finance/yfinance調整歷史，未逐日與獨立供應商或港交所對數。','', '| 股票 | 狀態 | 有效/嘗試 | 方向命中 | Kronos MAE | 不變基準 MAE | 趨勢基準 MAE |','|---|---|---:|---:|---:|---:|---:|']
    better=0;complete=0
    for s in summary:
        m=s['metrics'];label=s['ticker']+' '+s['name']
        if not m or not m['valid']:lines.append(f'| {label} | {s["status"]} | — | — | — | — | — |');continue
        complete+=1;p=m['predicted'];n=p['direction_n'];correct=p['direction_correct'];better+=p['mae']<m['zero']['mae']
        hit=f'{correct}/{n} ({correct/n:.1%})' if n else 'N/A'
        lines.append(f"| {label} | 完成 | {m['valid']}/{m['attempted']} | {hit} | {100*p['mae']:.2f} | {100*m['zero']['mae']:.2f} | {100*m['trend']['mae']:.2f} |")
    lines+=['','誤差為五日回報百分點，愈低愈好；基準與模型採相同有效窗口。方向命中率只計實際非零回報，並非交易勝率。零回報仍計入MAE/RMSE。', '',f'完成 {complete}/{len(stocks)} 個標的，其中 {better}/{complete} 個標的的模型MAE低於價格不變基準。各股票逐期預測與實際值見 windows.csv；模型、來源、原始資料指紋、參數及RMSE見 metrics.json。']
    if all_rows:
        m=result['pooled'];p=m['predicted'];n=p['direction_n']
        lines+=['',f"合併：有效 {m['valid']}/{m['attempted']}；模型MAE {100*p['mae']:.2f}、不變基準 {100*m['zero']['mae']:.2f}、趨勢基準 {100*m['trend']['mae']:.2f} 個百分點。方向 {p['direction_correct']}/{n} ({p['direction_correct']/n:.1%})。",'', '合併指標按有效窗口等權，不是等資金投資組合績效；同日期各股相關，不能把全部窗口當成獨立實驗。']
        lines+=['', '觀察結論：'+('此樣本整體模型MAE較不變基準低，但未證明統計顯著性、樣本外穩健性或交易盈利。' if p['mae']<m['zero']['mae'] else '此樣本整體模型MAE未優於不變基準，暫無支持提高決策權重的證據。')]
    lines+=['','## 方法與限制','', '- 每股最近24個五日目標回報區間，在同股內不重疊；只輸入起點已收市的400日OHLCV，未來只輸入日曆日期。過去20日趨勢換算為五日回報作另一基準。','- 輸入價格次序接受1e-10絕對容差，僅處理浮點運算誤差，不改動原始價格；實際不合法資料及生成K線均不修補。無效輸出保留失敗次數，只在相同有效窗口比較誤差。','- 預訓練截止時間未核實，不能保證模型未接觸歷史測試期。調整價格亦不是當時可得的資料快照；當前觀察名單有選樣及生存者偏差。','- 個別標的排名屬探索性結果；16股多重比較可能偶然出現表現好者，不能因此選成交易策略。','- 未計交易收益、手續費、滑點、保證金、Greeks或指派風險；不是股票策略或期權盈利驗證。','- 逐股獨立回測，失敗不阻斷其他標的；缺失標的須獨立檢查Actions記錄，沒有用零收益冒充完成。']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'completed':complete,'total':len(stocks),'better_than_zero':better,'pooled':result['pooled']},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);p.add_argument('--watchlist',default='market_watchlist.json');a=p.parse_args();build(a.inputs,a.output,a.watchlist)
