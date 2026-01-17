// Chequmate Freight UI (Calculator first, clean output)
// Build stamp helps us confirm Render is serving the right file.
const BUILD = "CALC_UI_v1_2026-01-17";
const API_BASE = ""; // same-origin

function $(sel){ return document.querySelector(sel); }
function esc(s){ return String(s ?? "").replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function num(v){ const n = Number(v); return Number.isFinite(n) ? n : 0; }
function money(v){
  const n = Number(v);
  if (!Number.isFinite(n)) return "$0.00";
  return n.toLocaleString(undefined, { style:"currency", currency:"USD" });
}
function milesFmt(v){
  const n = Number(v);
  if (!Number.isFinite(n)) return "0";
  return n.toLocaleString();
}

async function apiGet(path){
  const res = await fetch(API_BASE + path, { method: "GET" });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw:text }; }
  if (!res.ok){
    const msg = data?.detail || data?.error || ("HTTP " + res.status);
    throw new Error(msg);
  }
  return data;
}

function appShell(){
  $("#app").innerHTML = `
    <div class="container">
      <div class="topbar">
        <div class="brand">
          <div class="logo"><img src="/webapp/assets/chequmate-logo.png" alt="Chequmate"/></div>
          <div>
            <h1>Freight App</h1>
            <div class="sub">Calculator • Dispatcher • Driver testing UI</div>
          </div>
        </div>
        <div class="badge" title="Build stamp">${esc(BUILD)}</div>
      </div>

      <div class="grid">
        <div class="card">
          <h2>Calculator</h2>

          <div class="row">
            <div class="field">
              <label>Miles</label>
              <input id="miles" type="number" step="1" value="650" />
            </div>
            <div class="field">
              <label>Linehaul rate ($/mile)</label>
              <input id="linehaul_rate" type="number" step="0.01" value="3.00" />
            </div>
          </div>

          <div class="row">
            <div class="field">
              <label>Deadhead miles</label>
              <input id="deadhead_miles" type="number" step="1" value="75" />
            </div>
            <div class="field">
              <label>Deadhead rate ($/mile)</label>
              <input id="deadhead_rate" type="number" step="0.01" value="0" />
            </div>
          </div>

          <div class="row">
            <div class="field">
              <label>Detention ($)</label>
              <input id="detention" type="number" step="1" value="0" />
            </div>
            <div class="field">
              <label>Lumper ($)</label>
              <input id="lumper_fee" type="number" step="1" value="0" />
            </div>
          </div>

          <div class="row">
            <div class="field">
              <label>Extra stop ($)</label>
              <input id="extra_stop_fee" type="number" step="1" value="0" />
            </div>
            <div class="field">
              <label>Fuel surcharge (auto)</label>
              <input id="fuel_status" type="text" value="Auto from EIA" disabled />
            </div>
          </div>

          <div class="actions">
            <button class="primary" id="btnCalc">Calculate</button>
            <button class="secondary" id="btnToggleRaw">Show raw JSON</button>
          </div>

          <div class="alert small">
            Tip: If fuel is unavailable, totals still calculate — fuel shows $0 and an explanation.
          </div>
        </div>

        <div class="card">
          <h2>Results</h2>

          <div class="kpis">
            <div class="kpi">
              <div class="label">Total</div>
              <div class="value" id="kpiTotal">$0.00</div>
            </div>
            <div class="kpi">
              <div class="label">Fuel (est.)</div>
              <div class="value" id="kpiFuel">$0.00</div>
            </div>
          </div>

          <table class="table">
            <tr><td>Linehaul</td><td id="rowLinehaul">$0.00</td></tr>
            <tr><td>Deadhead</td><td id="rowDeadhead">$0.00</td></tr>
            <tr><td>Fuel</td><td id="rowFuel">$0.00</td></tr>
            <tr><td>Accessorials</td><td id="rowAcc">$0.00</td></tr>
            <tr><td>Subtotal</td><td id="rowSub">$0.00</td></tr>
            <tr><td>Total</td><td id="rowTotal">$0.00</td></tr>
          </table>

          <div class="alert" id="fuelNote" style="display:none;"></div>

          <div id="rawWrap" style="display:none;">
            <div class="raw" id="rawOut"></div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function setResults(data){
  const b = data?.breakdown || {};
  const f = data?.fuel || {};

  $("#kpiTotal").textContent = money(b.total ?? 0);
  $("#kpiFuel").textContent  = money(b.fuel_total ?? 0);

  $("#rowLinehaul").textContent = money(b.linehaul_total ?? 0);
  $("#rowDeadhead").textContent = money(b.deadhead_total ?? 0);
  $("#rowFuel").textContent     = money(b.fuel_total ?? 0);
  $("#rowAcc").textContent      = money(b.accessorials_total ?? 0);
  $("#rowSub").textContent      = money(b.subtotal ?? 0);
  $("#rowTotal").textContent    = money(b.total ?? 0);

  // Fuel note
  const noteEl = $("#fuelNote");
  if (f?.error){
    noteEl.style.display = "block";
    noteEl.textContent = `Fuel note: ${f.error}`;
  } else {
    noteEl.style.display = "none";
    noteEl.textContent = "";
  }

  // Raw JSON (for debugging)
  $("#rawOut").textContent = JSON.stringify(data, null, 2);
}

async function runCalc(){
  const miles = num($("#miles").value);
  const linehaul_rate = num($("#linehaul_rate").value);
  const deadhead_miles = num($("#deadhead_miles").value);
  const deadhead_rate = num($("#deadhead_rate").value);
  const detention = num($("#detention").value);
  const lumper_fee = num($("#lumper_fee").value);
  const extra_stop_fee = num($("#extra_stop_fee").value);

  const qs =
    `miles=${encodeURIComponent(miles)}` +
    `&linehaul_rate=${encodeURIComponent(linehaul_rate)}` +
    `&deadhead_miles=${encodeURIComponent(deadhead_miles)}` +
    `&deadhead_rate=${encodeURIComponent(deadhead_rate)}` +
    `&detention=${encodeURIComponent(detention)}` +
    `&lumper_fee=${encodeURIComponent(lumper_fee)}` +
    `&extra_stop_fee=${encodeURIComponent(extra_stop_fee)}`;

  $("#btnCalc").disabled = true;
  $("#btnCalc").textContent = "Calculating...";

  try{
    const data = await apiGet(`/calculate-rate?${qs}`);
    setResults(data);
  } catch (e){
    $("#rawWrap").style.display = "block";
    $("#rawOut").textContent = String(e?.message || e);
    $("#fuelNote").style.display = "block";
    $("#fuelNote").textContent = "Error: " + String(e?.message || e);
  } finally {
    $("#btnCalc").disabled = false;
    $("#btnCalc").textContent = "Calculate";
  }
}

function wire(){
  $("#btnCalc").addEventListener("click", runCalc);
  $("#btnToggleRaw").addEventListener("click", () => {
    const wrap = $("#rawWrap");
    const on = wrap.style.display !== "none";
    wrap.style.display = on ? "none" : "block";
    $("#btnToggleRaw").textContent = on ? "Show raw JSON" : "Hide raw JSON";
  });

  // Auto-run once
  runCalc();
}

window.addEventListener("DOMContentLoaded", () => {
  appShell();
  wire();
  console.log("UI BUILD:", BUILD);
});