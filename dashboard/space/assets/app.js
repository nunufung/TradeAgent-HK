(()=>{
"use strict";
const $=id=>document.getElementById(id),NS="http://www.w3.org/2000/svg";
let data=null,lastTrace=[],replayTimers=[],lookupUnderlying='';
const num=(x,d=2)=>Number.isFinite(x)?Number(x).toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d}):"—";
const text=(id,v)=>{$(id).textContent=v??"—"};
const date=x=>{if(!x)return"未取得";const d=new Date(x);return isNaN(d.valueOf())?String(x).slice(0,10):d.toLocaleString("zh-HK",{timeZone:"Asia/Hong_Kong",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})};
const node=(tag,cls,val)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(val!==undefined)e.textContent=val;return e};
const state=(id,v,cls)=>{text(id,v);$(id).className="state "+cls};
function nav(){
 document.querySelectorAll(".nav").forEach(btn=>btn.addEventListener("click",()=>{
 document.querySelectorAll(".nav").forEach(b=>b.classList.toggle("active",b===btn));
 document.querySelectorAll(".view").forEach(v=>v.classList.toggle("active",v.id===btn.dataset.view+"-view"));
 text("view-crumb",btn.dataset.view.toUpperCase())}));
 $("refresh").addEventListener("click",load);
 $("open-ideas").addEventListener("click",()=>document.querySelector('.nav[data-view="ideas"]').click());
 $("spider-replay").addEventListener("click",replayTrace);
 $("lookup-type").addEventListener("change",()=>{
   $("lookup-underlying-wrap").classList.toggle("hidden",$("lookup-type").value!=="option");
   $("lookup-code").placeholder=$("lookup-type").value==="option"?"輸入合約代號（需核對正股）":"例如 0700 / 700";
 });
 $("lookup-form").addEventListener("submit",e=>{e.preventDefault();lookup();});
 $("lookup-copy").addEventListener("click",()=>{
   if(!data||!lookupUnderlying)return;
   if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(lookupUnderlying).then(()=>{text("lookup-hint","已複製 "+lookupUnderlying+"，可在 GitHub Run workflow 嘅 ticker 欄貼上。");}).catch(()=>{text("lookup-hint","請手動複製正股代號："+lookupUnderlying);});}
   else{text("lookup-hint","請手動複製正股代號："+lookupUnderlying);}
 });
 $("fullscreen").addEventListener("click",()=>{if(document.fullscreenElement){document.exitFullscreen?.()}else{document.documentElement.requestFullscreen?.()}});

 $("chart-stock").addEventListener("change",chart);
 $("chart-model").addEventListener("change",chart);
 $("search-stock").addEventListener("input",table);
 $("group-filter").addEventListener("change",table);
}
function health(){
 const h=data.health||{},ok=h.telegram==="api_acknowledged";
 text("kpi-stocks",data.stocks.length);
 text("kpi-research",h.research==="complete"?"COMPLETE":h.research==="incomplete"?"INCOMPLETE":"UNVERIFIED");
 text("kpi-health-day",(h.day||"—")+" · "+(h.state||"UNKNOWN"));
 text("kpi-api",Number.isFinite(h.api_calls)?h.api_calls:"—");
 text("kpi-telegram",ok?"ACCEPTED":"UNVERIFIED");
 const chip=$("health-chip");chip.textContent=h.state||"UNVERIFIED";chip.className="chip "+(h.state==="FAILED"?"bad":h.state==="WARNING"||h.state==="UNVERIFIED"?"warn":"");
 state("health-research",h.research||"unverified",h.research==="complete"?"good":h.research==="incomplete"?"bad":"warn");
 state("health-telegram",h.telegram||"unverified",ok?"good":"warn");
 state("health-futu",h.futu||"unverified",h.futu==="recent_smoke_test_passed"?"good":"warn");
 state("health-tokens",Number.isFinite(h.tokens)?h.tokens.toLocaleString("en-US")+" tokens":"未驗證",h.tokens>0?"good":"warn");
 text("health-date",h.day||"—");
}
function models(){
 const f=data.model_status?.fincept||{},k=data.model_status?.kronos||{};
 text("fincept-mae",Number.isFinite(f.mae_pp)?num(f.mae_pp)+" pp":"—");
 text("fincept-base",Number.isFinite(f.baseline_mae_pp)?num(f.baseline_mae_pp)+" pp":"—");
 text("fincept-valid",Number.isFinite(f.valid_windows)?f.valid_windows:"—");
 text("fincept-cutoff","資料截止："+(f.data_cutoff||"未取得")+" · 公開研究快照（非交易回測）");
 text("kronos-mae",Number.isFinite(k.mae_pp)?num(k.mae_pp)+" pp":"—");
 text("kronos-valid",Number.isFinite(k.valid_windows)?k.valid_windows:"—");
 text("kronos-infer",k.generated_at?date(k.generated_at):"未取得");
 for(const [id,key] of [["fincept-source","fincept_report"],["kronos-source","kronos_report"],["health-source","health_workflow"]]){
 const url=data.links?.[key];if(typeof url==="string"&&url.startsWith("https://github.com/"))$(id).href=url;
 }
}
function ideas(){
 const r=data.daily_recommendations||{},valid=r.state==="RESEARCH_ONLY";
 text("ideas-action",valid?"今日決策："+(r.action||"等待"):"今日暫無可核實建議");
 const chip=$("ideas-state");chip.textContent=valid?"RESEARCH ONLY":"UNAVAILABLE";chip.className="chip "+(valid?"warn":"bad");
 text("ideas-reason",r.reason||"當日研究資料未齊。");
 text("ideas-date","研究日期："+(r.analysis_date||"未取得")+" · HKT · 並非即時訊號");
 const list=$("ideas-list");list.replaceChildren();
 const stocks=valid&&Array.isArray(r.stocks)?r.stocks:[];
 for(const item of stocks){
  const card=node("article","panel pad idea-card");
  const name=data.stocks.find(s=>s.ticker===item.ticker.slice(-4))?.name||"";
  const h=node("h2",null,item.ticker+" "+name+" · "+item.rating);
  const status=node("div","tagline",item.complete?"四分析員齊備 · "+(item.strategy||"等待"):"研究未完成 · 不做");
  card.append(h,node("p",null,item.summary||"研究證據不足"),status);list.append(card);
 }
 if(!stocks.length)list.append(node("div","panel pad","當日並無通過資料驗證嘅股票研究建議；不會使用舊報告代替。"));
 text("ideas-option","主推期權：暫無可執行合約。即使出現條件式 Short Put / Short Call 方向，仍需即時期權鏈、支撐阻力、事件日曆及帳戶風控獨立確認。");
}
function replayTrace(){
 const seq=lastTrace.filter(ev=>["GRAPH_STARTED","GRAPH_FINISHED","REPORT_OBSERVED","GRAPH_FAILED"].includes(ev.kind)).slice(-24);
 if(!seq.length)return;
 const button=$("spider-replay");button.disabled=true;button.textContent="▶ 回放歷史紀錄中…";
 const clear=()=>document.querySelectorAll(".spider-desk,.spider-chief,.spider-terminal").forEach(el=>el.classList.remove("replay-hot"));
 replayTimers.forEach(clearTimeout);replayTimers=[];clear();
 const aliases={market:"market",social:"sentiment",news:"news",fundamentals:"fundamental"};
 seq.forEach((ev,i)=>replayTimers.push(setTimeout(()=>{
  clear();
  if(ev.kind==="REPORT_OBSERVED"&&aliases[ev.role]){
   document.querySelector('.spider-desk[data-agent="'+aliases[ev.role]+'"]')?.classList.add("replay-hot");
  }else if(ev.kind==="GRAPH_STARTED")document.querySelector(".spider-chief")?.classList.add("replay-hot");
  else document.querySelector(".spider-terminal")?.classList.add("replay-hot");
 },i*550)));
 replayTimers.push(setTimeout(()=>{clear();button.disabled=false;button.textContent="▶ 歷史事件回放";},seq.length*550+450));
}
function normalizeHK(value){
 const m=String(value||"").trim().toUpperCase().match(/^(?:HK[.])?([0-9]{1,5})(?:[.]HK)?$/);
 const n=m?Number(m[1]):0;
 return n>0&&n<=99999?String(n).padStart(4,"0"):null;
}
function lookup(){
 if(!data)return;
 const kind=$("lookup-type").value, entered=$("lookup-code").value.trim().toUpperCase();
 let underlying=null, contract=null;
 if(kind==="stock"){underlying=normalizeHK(entered)}
 else{
   // Option symbols are broker/exchange specific: do not guess an underlying from their digits.
   contract=/^[A-Z0-9.\-]{3,28}$/.test(entered)?entered:null;
   underlying=normalizeHK($("lookup-underlying").value);
 }
 const result=$("lookup-content");result.replaceChildren();
 const add=(heading,body)=>{const unit=node("div","lookup-section");unit.append(node("b",null,heading),node("p",null,body));result.append(unit);};
 lookupUnderlying=underlying||"";
 $("lookup-copy").disabled=!underlying;
 if(!underlying||(kind==="option"&&!contract)){
   text("lookup-title","請檢查輸入代號");
   text("lookup-status","INVALID / UNVERIFIED");
   add("格式提示",kind==="option"?"期權合約代號只可包含英文字母、數字、連字號或句點，並必須輸入有效香港正股代號。":"請輸入香港正股數字代號，例如 700、0700、HK.00700。");
   text("lookup-source","沒有產生投資建議；沒有觸發任何外部分析。");
   return;
 }
 const stock=data.stocks.find(x=>Number(x.ticker)===Number(underlying)),r=data.daily_recommendations||{};
 const research=r.state==="RESEARCH_ONLY"&&r.analysis_date===data.meta.generated_at.slice(0,10)
  ?(r.stocks||[]).find(x=>Number(x.ticker)===Number(underlying)):null;
 const name=stock?.name||"未列入公開觀察名單";
 text("lookup-title",(kind==="option"?"Option "+contract+" · ":"")+"HK."+String(Number(underlying)).padStart(5,"0")+(stock?" · "+name:""));
 text("lookup-status",research?.complete?"RESEARCH RECORDED · NOT LIVE":stock?"WATCHLIST SNAPSHOT · NOT LIVE":"NO VERIFIED STOCK RESEARCH");
 if(kind==="option")add("合約識別與風控","你輸入嘅合約 "+contract+" 尚未有已驗證期權鏈、行使價、到期日、Bid/Ask、Delta、IV、OI 或保證金。不能判斷合約價格是否合理，亦不提供買賣或開倉指示。請先在 Futu / HKEX 核實合約身份及條款。");
 if(research&&research.complete){
  add("四分析員結論",research.rating+" · "+(research.summary||"沒有可用研究摘要。"));
  add("研究方向",research.strategy||"未有合格期權方向。");
 }else add("四分析員結論","本次快照沒有該正股同日完整四分析員研究。即使模型有預測，亦不等同確認買入／賣出。");
 if(stock){
  for(const model of ["fincept","kronos"]){
   const m=stock[model],v=m?.forecast_return_pct;
   add(model==="fincept"?"Fincept 歷史預測":"Kronos 歷史預測",
       m?.status==="FORECAST_ONLY"&&Number.isFinite(v)
       ?(v>=0?"+":"")+num(v)+"%（五個交易日預測；資料截至 "+(m.data_cutoff||"未取得")+"；非即市或已驗證回報）"
       :"目前沒有可核實預測。");
  }
  const b=stock.backtest||{};
  if(Number.isFinite(b.kronos_mae_pp)&&Number.isFinite(b.baseline_mae_pp))
   add("模型可靠性","Kronos 歷史 MAE "+num(b.kronos_mae_pp)+"pp；不變價格基準 "+num(b.baseline_mae_pp)+"pp。須比較基準誤差，不能單憑預測方向落單。");
 }
 add("投資評論／風險",kind==="option"?"暫不確認任何期權交易機會。必須覆核合約到期、Delta、價差、IV、成交量、OI、支撐阻力、事件日曆及可承受保證金；本頁不連接真實持倉。":"現有資料可供研究觀察，但不足以形成有即市依據的投資決策；先核實行情、企業事件和個人風險承受能力。");
 text("lookup-source","來源：TradeAgent-HK GitHub 每日公開快照 · "+date(data.meta.generated_at)+" HKT · 非即時報價。按代號輸入不會自動執行 TradingAgents。");
}
function spider(){
 const e=data.agent_events||{},h=data.health||{},r=data.daily_recommendations||{};
 const trusted=e.mode==="DAILY_SNAPSHOT_NOT_LIVE"&&e.day===h.day;
 const states=new Map((trusted&&Array.isArray(e.agents)?e.agents:[]).map(a=>[a.role,a]));
 for(const role of ["market","fundamental","news","sentiment"]){
  const a=states.get(role), el=$("spider-"+role);
  const label=a&&a.state==="COMPLETED"?"COMPLETED":"UNVERIFIED";
  el.textContent=label;el.title=a?.detail||"無獨立工作流證據";
  el.closest(".spider-desk").classList.toggle("confirmed",label==="COMPLETED");
 }
 text("spider-chief-status",trusted&&e.research_complete?"當日研究已通過審核":"當日研究未證實完成");
 text("spider-research",trusted&&e.research_complete?"AUDITED":"UNVERIFIED");
 text("spider-risk",r.state==="RESEARCH_ONLY"&&r.analysis_date===h.day?r.action:"WAIT");
 text("spider-telegram",trusted&&h.telegram==="api_acknowledged"?"API ACK":"UNVERIFIED");
 text("spider-ledger",trusted&&Number.isFinite(e.token_count)?"TOTAL TOKENS · "+e.token_count.toLocaleString("en-US"):"TOKEN LEDGER · UNVERIFIED");
 const list=$("spider-events");list.replaceChildren();
 const trace=Array.isArray(e.trace)?e.trace:[];
 lastTrace=trace;$("spider-replay").disabled=trace.length===0;
 const recentTicker=trace.length?trace[trace.length-1].ticker:null;
 const found=new Set(trace.filter(ev=>ev.ticker===recentTicker&&ev.kind==="REPORT_OBSERVED").map(ev=>ev.role));
 const verifiedCount=["market","social","news","fundamentals"].filter(role=>found.has(role)).length;
 text("spider-progress-label",recentTicker?recentTicker+" · "+verifiedCount+" / 4 reports":"0 / 4 · UNVERIFIED");
 $("spider-progress-fill").style.width=(verifiedCount*25)+"%";
 const roleAliases={market:"market",social:"sentiment",news:"news",fundamentals:"fundamental"};
 for(const ev of trace){
  if(ev.kind!=="REPORT_OBSERVED"||ev.ticker!==recentTicker||!roleAliases[ev.role])continue;
  const desk=$("spider-"+roleAliases[ev.role]);
  desk.textContent="REPORT OBSERVED";desk.title="Output verified at "+(ev.timestamp_hkt||"unknown")+"; node start time not measured";
  desk.closest(".spider-desk").classList.add("confirmed");
 }
 const observations=trusted&&Array.isArray(e.observations)?e.observations:[];
 const allowed=["daily_research","telegram","research_decision"];
 for(const event of observations.slice(0,8)){
  if(!allowed.includes(event.component)||event.day!==h.day||typeof event.detail!=="string")continue;
  const card=node("div","spider-event");
  const header=node("div","spider-event-header");
  header.append(node("b",null,event.component.replaceAll("_"," ").toUpperCase()),node("span",null,event.state||"UNVERIFIED"));
  card.append(header,node("p",null,event.detail));
  if(typeof event.source==="string"&&event.source.startsWith("https://github.com/nunufung/TradeAgent-HK/")){
   const link=node("a",null,"GITHUB EVIDENCE ↗");link.href=event.source;link.target="_blank";link.rel="noopener noreferrer";card.append(link);
  }
  list.append(card);
 }
 for(const ev of trace.slice(-14).reverse()){
  if(!["RUN_STARTED","GRAPH_STARTED","GRAPH_FINISHED","GRAPH_FAILED","REPORT_OBSERVED","REPORT_MISSING","RUN_FINISHED"].includes(ev.kind))continue;
  const card=node("div","spider-event");
  const hdr=node("div","spider-event-header");
  hdr.append(node("b",null,ev.kind.replaceAll("_"," ")+" · "+ev.ticker),node("span",null,ev.timestamp_hkt||""));
  card.append(hdr,node("p",null,ev.role?"Agent role: "+ev.role+" · verified graph-output observation":"TradingAgents graph execution event"));
  list.prepend(card);
 }
 if(!list.childElementCount)list.append(node("div","spider-event","沒有可核實嘅當日事件紀錄。"));
}
function commandCenter(){
 const h=data.health||{},r=data.daily_recommendations||{},m=data.model_status||{};
 const sameDay=r.state==="RESEARCH_ONLY"&&r.analysis_date===h.day;
 const research=h.research==="complete"?"COMPLETE":h.research==="incomplete"?"INCOMPLETE":"UNVERIFIED";
 const status=(id,value,verified)=>{const el=$(id);el.textContent=value;el.classList.toggle("verified",Boolean(verified))};
 text("command-snapshot",date(data.meta.generated_at));
 text("command-stocks",data.stocks.length);
 text("command-research",research);
 text("command-research-day",(h.day||"日期未驗證")+" · "+(h.state||"UNVERIFIED"));
 text("command-option",sameDay&&r.action==="不做"?"NO TRADE":"WAIT");
 text("command-delivery",h.telegram==="api_acknowledged"?"ACCEPTED":"UNVERIFIED");
 const complete=sameDay&&r.stocks.some(x=>x.complete);
 for(const id of ["agent-market","agent-fundamental","agent-news","agent-sentiment"])text(id,complete?"報告記錄齊備":"未有完整同日紀錄");
 text("command-decision-state",complete?"同日四分析員研究已記錄 · 未核實交易條件":"當日證據不足 / RESEARCH UNVERIFIED");
 text("command-stock-idea",sameDay&&r.stocks.length?r.stocks.length+" 隻研究標的":"沒有已確認同日研究");
 text("command-option-idea","期權決策："+(sameDay?r.action:"等待")+" · 未獲開倉授權");
 text("command-telegram-route",h.telegram==="api_acknowledged"?"Telegram API 已接受":"Telegram 未驗證");
 status("service-deepseek",research,research==="COMPLETE"&&h.api_calls>0);
 status("service-kronos",m.kronos?.generated_at?"ARCHIVED FORECAST":"UNAVAILABLE",false);
 status("service-fincept",m.fincept?.data_cutoff?"DATED FORECAST":"UNAVAILABLE",false);
 status("service-futu",h.futu||"UNVERIFIED",h.futu==="recent_smoke_test_passed");
 status("service-telegram",h.telegram==="api_acknowledged"?"API ACCEPTED":"UNVERIFIED",h.telegram==="api_acknowledged");
 status("service-snapshot","EXPORTED",true);
 const list=$("command-shortlist");list.replaceChildren();
 if(sameDay&&r.stocks.length){
  for(const stock of r.stocks.slice(0,3)){
   const item=node("div","command-item");
   item.append(node("b",null,stock.ticker+" · "+stock.rating),node("small",null,stock.summary||"研究摘要未提供"));
   list.append(item);
  }
 }else list.append(node("div","command-item","當日尚未有已核實建議。歷史預測不會冒充即日買賣訊號。"));
}
function initStocks(){
 const select=$("chart-stock");select.replaceChildren();
 const options=data.stocks.filter(s=>s.fincept?.status==="FORECAST_ONLY"||s.kronos?.status==="FORECAST_ONLY");
 options.forEach(s=>{const o=node("option",null,s.ticker+" · "+s.name);o.value=s.ticker;select.append(o)});
 if(options.length)select.value=(options.find(s=>s.ticker==="0388")||options[0]).ticker;
 chart();
}
function plot(values,labels){
 const svg=$("forecast-chart");svg.replaceChildren();
 const make=(tag,attrs,content)=>{const n=document.createElementNS(NS,tag);Object.entries(attrs||{}).forEach(([key,val])=>n.setAttribute(key,String(val)));if(content!==undefined)n.textContent=String(content);svg.append(n);return n};
 if(!Array.isArray(values)||values.length<2||!values.every(Number.isFinite)){
 make("text",{x:330,y:120,fill:"#91a8c4","text-anchor":"middle"},"此模型未有可核證預測資料");return;
 }
 let min=Math.min(...values),max=Math.max(...values);const p=Math.max((max-min)*.25,Math.abs(max)*.0006,.002);min-=p;max+=p;
 const x=i=>55+i*550/(values.length-1),y=v=>194-(v-min)/(max-min)*156;
 for(let i=0;i<4;i++)make("line",{x1:53,x2:612,y1:32+i*54,y2:32+i*54,stroke:"#28384f","stroke-dasharray":"4 6"});
 const pts=values.map((v,i)=>x(i)+","+y(v)).join(" ");
 make("polygon",{points:pts+" 605,205 55,205",fill:"rgba(68,205,199,.09)"});
 make("polyline",{points:pts,fill:"none",stroke:"#63e3d5","stroke-width":3.2,"stroke-linecap":"round","stroke-linejoin":"round"});
 values.forEach((v,i)=>{make("circle",{cx:x(i),cy:y(v),r:4,stroke:"#a0fff0","stroke-width":2,fill:"#172a38"});make("text",{x:x(i),y:236,fill:"#8ba0bd","text-anchor":"middle","font-size":11},(labels[i]||("D"+(i+1))).slice(5))});
 make("text",{x:55,y:18,fill:"#a4b7cf","font-size":11},"HKD "+num(max));
 make("text",{x:55,y:207,fill:"#a4b7cf","font-size":11},num(min));
}
function chart(){
 if(!data)return;
 const s=data.stocks.find(v=>v.ticker===$("chart-stock").value),model=$("chart-model").value;
 if(!s){plot([],[]);return}
 const f=s[model]||{},v=f.forecast_return_pct;
 text("chart-stock-name",s.name+" · "+s.ticker);
 text("chart-change",Number.isFinite(v)?(v>=0?"+":"")+num(v)+"%":"無可用預測");
 $("chart-change").className="chart-return "+(v<0?"negative":"");
 plot(f.prices||[],f.sessions||[]);
 text("chart-caption",(model==="fincept"?"Fincept ARIMA":"Kronos Small")+" · "+(f.status||"UNAVAILABLE")+" · 歷史資料截止 "+(f.data_cutoff||"未取得")+" · 非實時報價或已驗證交易訊號。");
}
function table(){
 if(!data)return;
 const q=$("search-stock").value.trim().toLowerCase(),g=$("group-filter").value,b=$("stocks-body");b.replaceChildren();
 const rows=data.stocks.filter(s=>(g==="all"||s.group===g)&&(s.ticker.includes(q)||(s.name||"").toLowerCase().includes(q)));
 for(const s of rows){
 const tr=node("tr"),first=node("td");first.append(node("span","ticker",s.ticker),node("span","stock-name",s.name));tr.append(first);
 const group=node("td");group.append(node("span","group-pill",s.group));tr.append(group);
 for(const m of ["fincept","kronos"]){const v=s[m]?.forecast_return_pct;tr.append(node("td",Number.isFinite(v)?v<0?"negative":"positive":"",Number.isFinite(v)?(v>=0?"+":"")+num(v)+"%":"—"))}
 const v=s.backtest?.kronos_mae_pp;tr.append(node("td",null,Number.isFinite(v)?num(v)+" pp":"—"));
 tr.append(node("td",null,s.fincept?.data_cutoff||s.kronos?.data_cutoff||"未取得"));b.append(tr);
 }
 if(!rows.length){const td=node("td",null,"沒有符合條件的股票");td.colSpan=6;const tr=node("tr");tr.append(td);b.append(tr)}
 text("table-count","Showing "+rows.length+" / "+data.stocks.length+" stocks · 公開研究資料，非富途即市報價");
}
async function load(){
 $("refresh").disabled=true;
 try{
 const r=await fetch("./data/dashboard.json?v="+Date.now(),{cache:"no-store"});
 if(!r.ok)throw new Error("Snapshot fetch failed");
 const payload=await r.json();
 if(payload.schema_version!==1||!Array.isArray(payload.stocks)||!payload.meta)throw Error("Invalid schema");
 data=payload;$("error").classList.add("hidden");text("snapshot-time",date(payload.meta.generated_at)+" HKT");
 health();models();ideas();commandCenter();spider();initStocks();table();if($("lookup-code").value.trim())lookup();
 }catch(e){
 text("error","Dashboard 資料未部署或暫時無法讀取。請檢查 GitHub Actions Dashboard Sync artifact。沒有資料時不會顯示模擬交易結果。");
 $("error").classList.remove("hidden");
 }finally{$("refresh").disabled=false}
}
nav();load();
})();