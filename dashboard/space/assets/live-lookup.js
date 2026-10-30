(()=>{
"use strict";
const $=id=>document.getElementById(id);
let generation=0,controller=null;
const node=(tag,text)=>{const el=document.createElement(tag);el.textContent=text;return el};
const num=x=>Number.isFinite(x)?x.toLocaleString('en-US',{maximumFractionDigits:2}):'未取得';
const date=x=>x?new Date(x).toLocaleString('zh-HK',{timeZone:'Asia/Hong_Kong'})+' HKT':'未取得';
function section(target,title,body){
 const el=node('div','');el.className='lookup-section';el.append(node('b',title),node('p',body));target.append(el);
}
async function api(path,body,signal){
 const r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',
  headers:body?{'Content-Type':'application/json','X-TradeAgent-Request':'1'}:{},
  body:body?JSON.stringify(body):undefined,signal});
 const result=await r.json().catch(()=>({}));
 if(!r.ok)throw Error(typeof result.detail==='string'?result.detail:'服務暫時無法讀取，請稍後重試。');
 return result;
}
async function session(){
 try{
  const s=await api('/api/session');
  $('pair-mac').classList.toggle('hidden',!s.owner);
  $('live-login').href=s.owner?s.standalone_url:'/auth/login';
  $('live-login').textContent=s.owner?'開啟獨立分析頁 ↗':'擁有者登入／開啟獨立分析頁 ↗';
  $('live-connection').textContent=s.owner
   ?'已登入 lewisf · '+(s.futu_connected?'Futu connector 已連線':'Futu connector 未連線，使用公開行情')+' · '+(s.research_configured?'DeepSeek 已設定':'DeepSeek 未設定')
   :'公開行情可直接查詢；登入 lewisf 後可用私人 Futu 連線及四分析員。登入會在獨立頁面完成。';
 }catch(e){$('live-connection').textContent='行情服務尚未可用：'+e.message;}
}
async function research(packetId,seq,signal){
 const box=$('live-research');box.classList.remove('hidden');box.replaceChildren(node('h2','四分析員研究'),node('p','正在啟動 Market、Fundamental、News、Sentiment；完成前不視為研究結論。'));
 try{
  const started=await api('/api/research',{packet_id:packetId},signal);
  for(let i=0;i<310;i++){
   if(seq!==generation)return;
   const job=await api('/api/research/'+encodeURIComponent(started.job_id),null,signal);
   if(seq!==generation)return;
   if(job.state==='FAILED')throw Error(job.error);
   if(job.state==='COMPLETED'){
    const result=job.result;box.replaceChildren(node('h2',result.complete?'四分析員研究已完成':'四分析員研究未齊備'));
    section(box,'行情及分析時間',result.quote_source+' · 報價 '+date(result.quote_at)+' · 分析 '+date(result.generated_at));
    for(const [role,report] of Object.entries(result.reports||{}))section(box,role,report||'該分析員未產生報告。');
    section(box,'綜合研究結論',result.summary||'未取得綜合結論。');section(box,'研究邊界',result.boundary);return;
   }
   await new Promise(resolve=>setTimeout(resolve,2000));
  }
  throw Error('研究尚未完成，請稍後重新查詢。');
 }catch(e){if(seq===generation&&e.name!=='AbortError')box.replaceChildren(node('h2','四分析員尚未完成'),node('p',e.message));}
}
async function lookup(raw){
 const seq=++generation;
 if(controller)controller.abort();controller=new AbortController();
 const signal=controller.signal;
 const timeout=setTimeout(()=>controller.abort(),45000);
 const content=$('lookup-content'),submit=$('lookup-form').querySelector('button[type="submit"]');
 $('live-research').classList.add('hidden');$('lookup-code').dataset.underlying='';
 content.replaceChildren(node('p','正在取得行情；Futu 不可用時會切換公開資料……'));
 $('lookup-title').textContent=raw+' · 查詢中';$('lookup-status').textContent='REQUESTING MARKET DATA';$('lookup-source').textContent='';submit.textContent='更新中…';
 try{
  const result=await api('/api/lookup',{code:raw},signal);
  if(seq!==generation)return;
  clearTimeout(timeout);
  const q=result.quote,t=result.technical;
  $('lookup-title').textContent=q.code+' · '+q.name;
  $('lookup-status').textContent=q.source+(q.fallback_reason?' · PUBLIC FALLBACK':' · FUTU')+' · '+t.quote_state;
  $('lookup-code').dataset.underlying=String(Number(q.code.slice(3))).padStart(4,'0');$('lookup-copy').disabled=false;
  content.replaceChildren();
  section(content,'最新可用價格','HK$ '+num(q.price)+' · 較上次收市 '+(Number.isFinite(t.change_pct)?num(t.change_pct)+'%':'未取得'));
  section(content,'來源及時間',q.source+' · 報價 '+date(q.quote_at)+' · 取得 '+date(q.retrieved_at)+' · 延遲 '+(Number.isFinite(q.delay_minutes)?q.delay_minutes+'分鐘':'未獲供應商確認'));
  if(q.fallback_reason)section(content,'資料來源切換',q.fallback_reason);
  section(content,'技術指標','SMA20：'+num(t.sma20)+' · RSI14（簡單平均）：'+num(t.rsi14)+' · 20日收市價範圍：'+num(t.support20)+' – '+num(t.resistance20));
  section(content,'即席技術評論',t.commentary);
  $('lookup-source').textContent='此處係本次取得嘅行情及技術計算，與其他頁面嘅每日快照分開。'+result.research_note;
  if(result.research_available)void research(result.packet_id,seq,signal);
  else{
   const box=$('live-research');box.classList.remove('hidden');box.replaceChildren(node('h2','四分析員研究'),node('p',result.research_note));
   const link=node('a','登入 lewisf 並開啟分析頁 ↗');link.href='/auth/login';link.target='_blank';link.rel='noopener noreferrer';box.append(link);
  }
  void session();
 }catch(e){
  if(seq!==generation)return;
  $('lookup-status').textContent='DATA UNAVAILABLE';
  content.replaceChildren(node('p',e.name==='AbortError'?'行情查詢逾時，請稍後重試。':e.message));
  $('lookup-source').textContent='沒有以舊快照或模擬數據冒充本次行情。';
 }finally{clearTimeout(timeout);if(seq===generation)submit.textContent='取得行情及分析 →';}
}
$('lookup-form').addEventListener('submit',e=>{
 if($('lookup-type').value!=='stock'){generation++;controller?.abort();$('lookup-code').dataset.underlying='';$('live-research').classList.add('hidden');return;}
 e.preventDefault();e.stopImmediatePropagation();void lookup($('lookup-code').value.trim());
},true);
$('pair-mac').addEventListener('click',async()=>{
 try{
  const result=await api('/api/device/code',{});const el=$('pair-code');el.classList.remove('hidden');
  el.textContent='在 Mac connector 嘅隱藏提示貼上此配對碼（5分鐘有效；請勿分享）：'+result.code;
 }catch(e){$('live-connection').textContent=e.message;}
});
if(new URLSearchParams(location.search).get('view')==='lookup')document.querySelector('.nav[data-view="lookup"]').click();
void session();
})();
