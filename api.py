from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

HTML_PAGE = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>收租Agent - TradeAgent-HK</title>
<style>body{font-family: -apple-system, sans-serif; padding:20px; max-width:400px; margin:auto;}input{width:100%;padding:12px;margin:8px 0;border:1px solid #ccc;border-radius:8px;}button{width:100%;padding:14px;background:#25D366;color:white;border:none;border-radius:8px;font-size:16px;font-weight:bold;} .card{background:#f5f5f5;padding:15px;border-radius:10px;margin-top:15px;}</style>
</head><body>
<h2>TradeAgent-HK 收租計算器</h2>
<p>前面 Meta AI，後面 DeepSeek + GitHub hk_screener.py 真計算</p>

<h3>1. 收租 Covered Call (有正股)</h3>
<input id="ticker1" placeholder="股票 0700.HK / 9988.HK / 3690.HK" value="9988.HK">
<input id="shares" type="number" placeholder="股數 例如 200" value="200">
<input id="cost" type="number" placeholder="成本價 例如 105" value="105">
<input id="current" type="number" placeholder="現價 例如 108.5" value="108.5">
<button onclick="calcRent()">計收租幾多</button>
<div id="rentResult" class="card" style="display:none"></div>

<h3 style="margin-top:30px">2. Bull Spread (無貨想衝)</h3>
<input id="ticker2" placeholder="股票" value="9988.HK">
<input id="long" type="number" placeholder="Long Strike 例如 110" value="110">
<input id="short" type="number" placeholder="Short Strike 例如 120" value="120">
<input id="debit" type="number" placeholder="Debit 成本 例如 2.5" value="2.5">
<button onclick="calcSpread()">計 Max賺/蝕 R/R</button>
<div id="spreadResult" class="card" style="display:none"></div>

<script>
function calcRent(){
  let t=document.getElementById('ticker1').value;
  let s=document.getElementById('shares').value;
  let c=document.getElementById('cost').value;
  let cur=document.getElementById('current').value;
  fetch(`/rent?ticker=${t}&shares=${s}&cost=${c}&current=${cur}`).then(r=>r.json()).then(d=>{
    document.getElementById('rentResult').style.display='block';
    document.getElementById('rentResult').innerHTML = 
      `<b>${d.ticker} 
