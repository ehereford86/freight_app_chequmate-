/*
  CALC_UI_v1
  - Same-origin API
  - Layout matches your screenshot:
    * 2-col calculator form
    * buttons row
    * results: two stat cards + left/right breakdown rows
    * raw JSON only when button pressed
*/

const API_BASE = ""; // same-origin

function $(s){ return document.querySelector(s); }
function num(v, f=0){ const n = Number(v); return Number.isFinite(n) ? n : f; }
function money(v){ return num(v,0).toLocaleString(undefined,{style:"currency",currency:"USD"}); }

async function apiGet(path){
  const res = await fetch(API_BASE + path, { method:"GET" });
  const txt = await res.text();
  let data; try{ data = JSON.parse(txt); }catch{ data = { raw: txt }; }
  if(!res.ok){
    throw new Error(data?.detail || data?.error || `HTTP ${res.status}`);
  }
  return data;
}

function qs(){
  const p = new URLSearchParams({
    miles: String(num($("#miles").value, 0)),
    linehaul_rate: String(num($("#linehaul_rate").value, 0)),
    deadhead_miles: String(num($("#deadhead_miles").value, 0)),
    deadhead_rate: String(num($("#deadhead_rate").value, 0)),
    detention: String(num($("#detention").value, 0)),
    lumper_fee: String(num($("#lumper_fee").value, 0)),
    extra_stop_fee: String(num($("#extra_stop_fee").value, 0)),
  });
  return p.toString();
}

function row(label, value){
  return `
    <div class="kv">
      <div class="k">${label}</div>
      <div class="v">${value}</div>
    </div>
  `;
}

function render(){
  $("#app").innerHTML = `
    <div class="page">
      <header class="topbar">
        <div class="brand">
          <img class="logo" src="/webapp/assets/chequmate-logo.png" alt="Chequmate" />
          <div>
            <div class="title">Freight App</div>
            <div class="subtitle">Calculator · Dispatcher · Driver testing UI</div>
          </div>
        </div>
        <div class="pill" id="pill">CALC_UI_v1_2026-01-17</div>
      </header>

      <section class="card">
        <h2>Calculator</h2>

        <div class="form2">
          <div class="field">
            <label>Miles</label>
            <input id="miles" value="1375" />
          </div>

          <div class="field">
            <label>Linehaul rate ($/mile)</label>
            <input id="linehaul_rate" value="3.00" />
          </div>

          <div class="field">
            <label>Deadhead miles</label>
            <input id="deadhead_miles" value="75" />
          </div>

          <div class="field">
            <label>Deadhead rate ($/mile)</label>
            <input id="deadhead_rate" value="0" />
          </div>

          <div class="field">
            <label>Detention ($)</label>
            <input id="detention" value="0" />
          </div>

          <div class="field">
            <label>Lumper ($)</label>
            <input id="lumper_fee" value="0" />
          </div>

          <div class="field">
            <label>Extra stop ($)</label>
            <input id="extra_stop_fee" value="0" />
          </div>

          <div class="field">
            <label>Fuel surcharge (auto)</label>
            <input value="Auto from EIA" disabled />
          </div>
        </div>

        <div class="btnrow">
          <button class="btn" id="calcBtn">Calculate</button>
          <button class="btn2" id="rawBtn">Show raw JSON</button>
        </div>

        <div class="hint">
          Tip: If fuel is unavailable, totals still calculate — fuel shows $0 and an explanation.
        </div>

        <div class="resultsTitle">Results</div>

        <div class="statGrid">
          <div class="stat">
            <div class="statLabel">Total</div>
            <div class="statValue" id="total">$0.00</div>
          </div>
          <div class="stat">
            <div class="statLabel">Fuel (est.)</div>
            <div class="statValue" id="fuel">$0.00</div>
          </div>
        </div>

        <div class="breakdown" id="breakdown"></div>

        <pre class="raw" id="raw" style="display:none;"></pre>
      </section>
    </div>
  `;

  $("#calcBtn").addEventListener("click", calculate);
  $("#rawBtn").addEventListener("click", () => {
    const el = $("#raw");
    el.style.display = (el.style.display === "none") ? "block" : "none";
  });
}

function setPill(ok, msg){
  const el = $("#pill");
  if(!el) return;
  el.textContent = ok ? "CALC_UI_v1_2026-01-17" : `Calc failed: ${msg}`;
}

function applyResults(data){
  const breakdown = data.breakdown || data.totals || {};
  const total = data.total ?? breakdown.total ?? 0;

  // Try common fuel shapes used earlier
  const fuel =
    (data.fuel && (data.fuel.fuel_total ?? data.fuel.total ?? data.fuel.est ?? 0)) ??
    breakdown.fuel_total ?? 0;

  $("#total").textContent = money(total);
  $("#fuel").textContent  = money(fuel);

  const linehaul = breakdown.linehaul_total ?? breakdown.linehaul ?? 0;
  const deadhead = breakdown.deadhead_total ?? breakdown.deadhead ?? 0;
  const acc      = breakdown.accessorials_total ?? breakdown.accessorials ?? 0;
  const subtotal = breakdown.subtotal ?? 0;

  const rows = [];
  rows.push(row("Linehaul", money(linehaul)));
  rows.push(row("Deadhead", money(deadhead)));
  rows.push(row("Fuel", money(fuel)));
  if(acc) rows.push(row("Accessorials", money(acc)));
  if(subtotal) rows.push(row("Subtotal", money(subtotal)));
  rows.push(`<div class="divider"></div>`);
  rows.push(row("Total", money(total)));

  $("#breakdown").innerHTML = rows.join("");

  $("#raw").textContent = JSON.stringify(data, null, 2);
}

async function calculate(){
  try{
    setPill(true, "");
    // IMPORTANT: backend route you showed is /calculate-rate
    const data = await apiGet(`/calculate-rate?${qs()}`);
    applyResults(data);
  }catch(e){
    setPill(false, e.message);
    $("#total").textContent = money(0);
    $("#fuel").textContent = money(0);
    $("#breakdown").innerHTML = row("Total", money(0));
    $("#raw").textContent = "";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  render();
});
