const API_BASE = ""; // same-origin

function $(sel){ return document.querySelector(sel); }
function setText(el, txt){ if(el) el.textContent = (txt ?? ""); }

function fmtMoney(n){
  const x = Number(n);
  if (!isFinite(x)) return "$0.00";
  return x.toLocaleString(undefined,{style:"currency",currency:"USD"});
}
function numVal(id){
  const el = document.getElementById(id);
  if(!el) return 0;
  const v = String(el.value ?? "").trim();
  const x = Number(v);
  return isFinite(x) ? x : 0;
}

async function postJSON(path, body){
  const r = await fetch(API_BASE + path, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });
  const text = await r.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw:text }; }
  if(!r.ok){
    const msg = (data && (data.detail || data.message)) ? (data.detail || data.message) : `HTTP ${r.status}`;
    throw new Error(msg);
  }
  return data;
}

function showCalcStatus(msg){
  const el = $("#calcStatus");
  if(!el) return;
  el.classList.toggle("bad", !!msg);
  setText(el, msg || "");
}

function showResults(payload){
  // Expected payload.breakdown totals
  const b = payload?.breakdown || {};
  setText($("#resTotal"), fmtMoney(b.total));
  setText($("#resFuel"), fmtMoney(b.fuel_total));

  // Optional detailed rows (left label / right amount)
  const rows = [
    ["Linehaul", b.linehaul_total],
    ["Deadhead", b.deadhead_total],
    ["Fuel", b.fuel_total],
    ["Accessorials", b.accessorials_total],
    ["Subtotal", b.subtotal],
    ["Total", b.total],
  ];

  const list = $("#resList");
  if(list){
    list.innerHTML = "";
    for(const [label, val] of rows){
      const row = document.createElement("div");
      row.className = "rowline";
      const l = document.createElement("div");
      l.className = "rowlabel";
      l.textContent = label;
      const r = document.createElement("div");
      r.className = "rowvalue";
      r.textContent = fmtMoney(val);
      row.appendChild(l);
      row.appendChild(r);
      list.appendChild(row);
    }
  }

  // Raw JSON drawer
  const raw = $("#rawJson");
  if(raw){
    raw.textContent = JSON.stringify(payload, null, 2);
  }
}

async function doCalculate(){
  showCalcStatus("");
  const body = {
    miles: numVal("miles"),
    linehaul_rate: numVal("linehaul_rate"),
    deadhead_miles: numVal("deadhead_miles"),
    deadhead_rate: numVal("deadhead_rate"),
    detention: numVal("detention"),
    lumper_fee: numVal("lumper_fee"),
    extra_stop_fee: numVal("extra_stop_fee"),
    fuel_mode: (document.getElementById("fuel_mode")?.value || "auto")
  };

  try{
    // FIX: use the real API route
    const data = await postJSON("/calculate-rate", body);
    showResults(data);
  }catch(e){
    showCalcStatus(`Calc failed: ${e.message || "Not Found"}`);
    // Keep UI stable: show zeros, don’t dump raw text into layout
    showResults({breakdown:{linehaul_total:0,deadhead_total:0,fuel_total:0,accessorials_total:0,subtotal:0,total:0}});
  }
}

function toggleRaw(){
  const box = $("#rawWrap");
  if(!box) return;
  box.classList.toggle("hidden");
}

function init(){
  const btn = $("#btnCalc");
  if(btn) btn.addEventListener("click", doCalculate);

  const rawBtn = $("#btnRaw");
  if(rawBtn) rawBtn.addEventListener("click", toggleRaw);

  // default hide raw
  const box = $("#rawWrap");
  if(box) box.classList.add("hidden");
}

document.addEventListener("DOMContentLoaded", init);
