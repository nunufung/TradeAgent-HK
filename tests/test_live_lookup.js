const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');

function setup(quoteFetch){
 const elements=new Map();
 function element(id){
  if(!elements.has(id))elements.set(id,{textContent:'',value:'',dataset:{},children:[],listeners:{},
   classList:{toggle(){},add(){},remove(){}},
   append(...nodes){this.children.push(...nodes)},replaceChildren(...nodes){this.children=nodes},
   addEventListener(name,fn){this.listeners[name]=fn},
   querySelector(){return element('submit')},click(){}});
  return elements.get(id);
 }
 element('lookup-type').value='stock';
 const fetch=async (url,options)=>{
  const body=url==='/api/session'?{owner:false}:await quoteFetch(JSON.parse(options.body));
  return {ok:true,json:async()=>body};
 };
 const context=vm.createContext({document:{getElementById:element,createElement:()=>element(Symbol()),querySelector:()=>element('nav')},
  fetch,AbortController,URLSearchParams,location:{search:''},setTimeout,clearTimeout});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../dashboard/space/assets/live-lookup.js'),'utf8'),context);
 const submit=code=>{element('lookup-code').value=code;return element('lookup-form').listeners.submit({preventDefault(){},stopImmediatePropagation(){}})};
 const contents=id=>{const all=e=>[e.textContent,...e.children.map(all)].join(' ');return all(element(id))};
 return {element,submit,contents};
}
function result(code='HK.00700',source='Yahoo Finance'){
 return {packet_id:'packet',quote:{code,name:'Test company',source,price:500,quote_at:'2026-10-30T06:00:00Z',retrieved_at:'2026-10-30T06:01:00Z',fallback_reason:'Futu offline'},
  technical:{quote_state:'DELAYED',change_pct:2,sma20:490,rsi14:55,support20:470,resistance20:510,commentary:'Calculated from provider candles'},research_available:false,research_note:'Owner sign-in needed for four analysts'};
}
const tick=()=>new Promise(r=>setImmediate(r));
test('stock submit renders actual provider, quote and separate technical commentary',async()=>{
 const app=setup(async()=>result());app.submit('700');await tick();await tick();
 assert.match(app.contents('lookup-content'),/500/);
 assert.match(app.contents('lookup-content'),/Yahoo Finance/);
 assert.match(app.contents('lookup-content'),/Futu offline/);
 assert.match(app.contents('live-research'),/Owner sign-in needed/);
 assert.equal(app.element('lookup-code').dataset.underlying,'0700');
});
test('a late response for an earlier ticker never replaces the newer result',async()=>{
 let first,second;
 const app=setup(body=>new Promise(resolve=>{if(body.code==='700')first=resolve;else second=resolve}));
 app.submit('700');app.submit('5');
 second(result('HK.00005'));await tick();await tick();
 first(result('HK.00700'));await tick();await tick();
 assert.match(app.contents('lookup-title'),/HK.00005/);
 assert.equal(app.element('lookup-code').dataset.underlying,'0005');
});
