/* Chequmate Freight App UI
   - Same-origin API calls (Render + local)
   - Clean UI: shows totals + a collapsible Details section
   - No broker fields, no raw JSON dump unless you expand Details
*/

const API_BASE = ""; // same-origin

function $(sel){ return document.querySelector(sel); }
function esc(s){ return String(s ?? "").replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function num(v, fallback=0){
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}
function money(v){
  const n = num(v, 0);
  return n.toLocaleString(undefined, { style: "currency", currency: "USD" });
}
function fixed(v, d=3){
  const n = num(v, 0);
  return n.toFixed(d);
}

async function apiGet(path){
  const res = await fetch(API_BASE + path, { method: "GET" });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok){
    const msg = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function render(){
  $("#app").innerHTML = `
    <div class="page">
      <header class="topbar">
        <div class="brand">
          <img class="logo" src="/webapp/assets/chequmate-logo.png" alt="Chequmate" />
          <div class="brandtext">
            <div class="title">Freight App</div>
            <div class="subtitle">Rate + Fuel Surcharge Calculator</div>
          </div>
        </div>
        <div class="status" id="status">Ready</div>
      </header>

      <main class="main">
        <section class="card">
          <h2>Inputs</h2>

          <div class="grid">
            <label class="field">
              <span>Miles</span>
              <input id="miles" inputmode="decimal" placeholder="650" />
            </label>

            <label class="field">
              <span>Linehaul rate ($/mile)</span>
              <input id="linehaul_rate" inputmode="decimal" placeholder="3.00" />
            </label>

            <label class="field">
              <span>Deadhead miles</span>
              <input id="deadhead_miles" inputmode="decimal" placeholder="75" />
            </label>

            <label class="field">
              <span>Deadhead rate ($/mile)</span>
              <input id="deadhead_rate" inputmode="decimal" placeholder="0.00" />
            </label>

            <label class="field">
              <span>Detention ($)</span>
              <input id="detention" inputmode="decimal" placeholder="0" />
            </label>

            <label class="field">
              <span>Lumper ($)</span>
              <input id="lumper_fee" inputmode="decimal" placeholder="0" />
            </label>

            <label class="field">
              <span>Extra stop ($)</span>
              <input id="extra_stop_fee" inputmode="decimal" placeholder="0" />
            </label>
          </div>

          <div class="actions">
            <button id="calcBtn" class="btn">Calculate</button>
            <button id="fillBtn" class="btn ghost">Fill example</button>
          </div>
        </section>

        <section class="card">
          <h2>Results</h2>

          <div id="result" class="result">
            <div class="muted">Run a calculation to see results.</div>
          </div>

          <details class="details" id="detailsWrap">
            <summary>Details (raw JSON)</summary>
            <pre id="jsonBox" class="code"></pre>
          </details>
        </section>
      </main>

      <footer class="footer">
        <span class="muted">Tip: if diesel price is unavailable, fuel surcharge will be $0 and the app will continue normally.</span>
      </footer>
    </div>
  `;
}

function setStatus(msg, kind="ok"){
  const el = $("#status");
  if (!el) return;
  el.textContent = msg;
  el.className = `status ${kind}`;
}

function fillExample(){
  $("#miles").value = "650";
  $("#linehaul_rate").value = "3.00";
  $("#deadhead_miles").value = "75";
  $("#deadhead_rate").value = "0.00";
  $("#detention").value = "0";
  $("#lumper_fee").value = "0";
  $("#extra_stop_fee").value = "0";
}

function renderResult(data){
  const inputs = data?.inputs || {};
  const fuel = data?.fuel || {};
  const breakdown = data?.breakdown || {};

  const diesel = fuel?.diesel_price;
  const fsc = fuel?.fuel_surcharge_per_mile;

  const dieselLine = (diesel === null || diesel === undefined)
    ? `<div class="kv"><span>Diesel price</span><span class="warn">Unavailable</span></div>`
    : `<div class="kv"><span>Diesel price</span><span>$${fixed(diesel, 3)}</span></div>`;

  const fscLine = (fsc === null || fsc === undefined)
    ? `<div class="kv"><span>Fuel surcharge / mile</span><span class="warn">Unavailable</span></div>`
    : `<div class="kv"><span>Fuel surcharge / mile</span><span>$${fixed(fsc, 4)}</span></div>`;

  const html = `
    <div class="resultGrid">
      <div class="panel">
        <h3>Summary</h3>
        <div class="kv"><span>Total</span><span class="big">${money(breakdown.total)}</span></div>
        <div class="kv"><span>Subtotal</span><span>${money(breakdown.subtotal)}</span></div>
      </div>

      <div class="panel">
        <h3>Line Items</h3>
        <div class="kv"><span>Linehaul</span><span>${money(breakdown.linehaul_total)}</span></div>
        <div class="kv"><span>Deadhead</span><span>${money(breakdown.deadhead_total)}</span></div>
        <div class="kv"><span>Fuel</span><span>${money(breakdown.fuel_total)}</span></div>
        <div class="kv"><span>Accessorials</span><span>${money(breakdown.accessorials_total)}</span></div>
      </div>

      <div class="panel">
        <h3>Fuel</h3>
        ${dieselLine}
        ${fscLine}
        <div class="kv"><span>Base price</span><span>$${fixed(fuel.base_price ?? 1.25, 2)}</span></div>
        <div class="kv"><span>Multiplier</span><span>${fixed(fuel.multiplier_used ?? 0.06, 3)}</span></div>
      </div>

      <div class="panel">
        <h3>Inputs Used</h3>
        <div class="kv"><span>Miles</span><span>${esc(inputs.miles)}</span></div>
        <div class="kv"><span>Linehaul rate</span><span>${esc(inputs.linehaul_rate)}</span></div>
        <div class="kv"><span>Deadhead miles</span><span>${esc(inputs.deadhead_miles)}</span></div>
      </div>
    </div>
  `;

  $("#result").innerHTML = html;
  $("#jsonBox").textContent = JSON.stringify(data, null, 2);
}

async function onCalculate(){
  try{
    setStatus("Calculating…", "work");

    const miles = num($("#miles").value);
    const linehaul_rate = num($("#linehaul_rate").value);
    const deadhead_miles = num($("#deadhead_miles").value);
    const deadhead_rate = num($("#deadhead_rate").value);
    const detention = num($("#detention").value);
    const lumper_fee = num($("#lumper_fee").value);
    const extra_stop_fee = num($("#extra_stop_fee").value);

    // Basic guardrails (no crashing, just clear errors)
    if (miles <= 0) throw new Error("Miles must be greater than 0.");
    if (linehaul_rate <= 0) throw new Error("Linehaul rate must be greater than 0.");

    const qs = new URLSearchParams({
      miles: String(miles),
      linehaul_rate: String(linehaul_rate),
      deadhead_miles: String(deadhead_miles),
      deadhead_rate: String(deadhead_rate),
      detention: String(detention),
      lumper_fee: String(lumper_fee),
      extra_stop_fee: String(extra_stop_fee),
    });

    const data = await apiGet(`/calculate-rate?${qs.toString()}`);
    renderResult(data);
    setStatus("Done", "ok");
  }catch(err){
    setStatus(err?.message || "Error", "bad");
    $("#result").innerHTML = `<div class="error">Error: ${esc(err?.message || "Unknown error")}</div>`;
    $("#jsonBox").textContent = "";
  }
}

function bind(){
  $("#calcBtn").addEventListener("click", onCalculate);
  $("#fillBtn").addEventListener("click", () => {
    fillExample();
    setStatus("Example filled", "ok");
  });

  // Enter key triggers calculate
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter"){
      const active = document.activeElement;
      if (active && active.tagName === "INPUT"){
        e.preventDefault();
        onCalculate();
      }
    }
  });
}

window.addEventListener("DOMContentLoaded", () => {
  render();
  bind();
  fillExample();
});