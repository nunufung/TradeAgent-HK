(()=>{
"use strict";
const $=id=>document.getElementById(id),NS="http://www.w3.org/2000/svg";
let data=null;
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
 health();models();ideas();commandCenter();initStocks();table();
 }catch(e){
 text("error","Dashboard 資料未部署或暫時無法讀取。請檢查 GitHub Actions Dashboard Sync artifact。沒有資料時不會顯示模擬交易結果。");
 $("error").classList.remove("hidden");
 }finally{$("refresh").disabled=false}
}
nav();load();
})();