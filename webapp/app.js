/* Chequmate Freight App UI
   - Same-origin API calls (Render + local)
   - Clean UI: totals + formatted breakdown
   - Raw JSON is hidden by default (only shows if you click "Show raw JSON")
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
function fixed(v, d=2){
  const n = num(v, 0);
  return n.toFixed(d);
}

function setStatus(text){
  const el = $("#statusText");
  if (el) el.textContent = text || "";
}

function show(el){ if (el) el.style.display = ""; }
function hide(el){ if (el) el.style.display = "none"; }

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

async function apiPost(path, body){
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }

  if (!res.ok){
    const msg = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

// ------------------------------------
// UI RENDER
// ------------------------------------
function render(){
  const root = $("#app");
  if (!root) return;

  root.innerHTML = `
    <div class="page">
      <header class="topbar">
        <div class="brand">
          <img class="logo" src="/webapp/assets/chequmate-logo.png" alt="Chequmate" />
          <div class="brandtext">
            <div class="title">Chequmate Freight</div>
            <div class="subtitle">Broker · Dispatcher · Driver</div>
          </div>
        </div>
        <div class="pill" id="statusText">Ready.</div>
      </header>

      <!-- Auth -->
      <div class="grid2">
        <section class="card">
          <h2>Login</h2>
          <div class="row">
            <input id="login_user" placeholder="Username" autocomplete="username" />
            <input id="login_pass" type="password" placeholder="Password" autocomplete="current-password" />
          </div>
          <div class="row">
            <button class="btn" id="btnLogin">Login</button>
            <button class="btn2" id="btnLogout">Logout</button>
          </div>
          <div class="hint" id="loginMsg"></div>
        </section>

        <section class="card">
          <h2>Register</h2>
          <div class="row">
            <input id="reg_user" placeholder="Username" autocomplete="username" />
            <input id="reg_pass" type="password" placeholder="Password" autocomplete="new-password" />
          </div>
          <div class="row">
            <select id="reg_role">
              <option value="broker">Broker</option>
              <option value="dispatcher">Dispatcher</option>
              <option value="driver">Driver</option>
            </select>
            <button class="btn" id="btnRegister">Register</button>
          </div>
          <div class="hint" id="regMsg"></div>
        </section>
      </div>

      <!-- Calculator -->
      <section class="card">
        <div class="cardhead">
          <h2>Rate + Fuel Surcharge Calculator</h2>
          <div class="row" style="justify-content:flex-end;">
            <button class="btn2" id="btnToggleRaw">Show raw JSON</button>
          </div>
        </div>

        <div class="grid2">
          <div>
            <label>Miles</label>
            <input id="miles" inputmode="decimal" value="1375" />
          </div>
          <div>
            <label>Linehaul rate ($/mile)</label>
            <input id="linehaul_rate" inputmode="decimal" value="0.55" />
          </div>

          <div>
            <label>Deadhead miles</label>
            <input id="deadhead_miles" inputmode="decimal" value="75" />
          </div>
          <div>
            <label>Deadhead rate ($/mile)</label>
            <input id="deadhead_rate" inputmode="decimal" value="0" />
          </div>

          <div>
            <label>Detention ($)</label>
            <input id="detention" inputmode="decimal" value="0" />
          </div>
          <div>
            <label>Lumper fee ($)</label>
            <input id="lumper_fee" inputmode="decimal" value="0" />
          </div>

          <div>
            <label>Extra stop fee ($)</label>
            <input id="extra_stop_fee" inputmode="decimal" value="0" />
          </div>
          <div>
            <label>Fuel surcharge</label>
            <div class="pill" style="text-align:center;">Auto from EIA (if available)</div>
          </div>
        </div>

        <div class="row" style="margin-top:14px;">
          <button class="btn" id="btnCalc">Calculate</button>
          <div class="hint" id="calcMsg"></div>
        </div>
      </section>

      <!-- Results -->
      <section class="card" id="resultsCard">
        <h2>Results</h2>

        <div class="grid2">
          <div class="stat">
            <div class="statlabel">Total</div>
            <div class="statvalue" id="statTotal">$0.00</div>
          </div>
          <div class="stat">
            <div class="statlabel">Fuel (est.)</div>
            <div class="statvalue" id="statFuel">$0.00</div>
          </div>
        </div>

        <div class="lines" id="breakdownLines"></div>

        <details class="details" id="detailsBox">
          <summary>Details</summary>
          <div class="detailsBody" id="detailsBody"></div>
        </details>

        <pre class="rawjson" id="rawBox" style="display:none;"></pre>
      </section>
    </div>
  `;

  wireUp();
}

function wireUp(){
  // Auth: if your API endpoints exist, these will work.
  // If your backend uses different routes, these will fail safely with a message.
  $("#btnLogin")?.addEventListener("click", async () => {
    const u = $("#login_user")?.value?.trim();
    const p = $("#login_pass")?.value ?? "";
    $("#loginMsg").textContent = "";
    if (!u || !p){ $("#loginMsg").textContent = "Enter username + password."; return; }

    try{
      setStatus("Logging in…");
      const data = await apiPost("/auth/login", { username: u, password: p });
      // token storage if your backend returns token
      if (data?.token) localStorage.setItem("token", data.token);
      $("#loginMsg").textContent = "Logged in.";
      setStatus("Logged in.");
    }catch(e){
      $("#loginMsg").textContent = String(e.message || e);
      setStatus("Login failed.");
    }
  });

  $("#btnLogout")?.addEventListener("click", () => {
    localStorage.removeItem("token");
    $("#loginMsg").textContent = "Logged out.";
    setStatus("Logged out.");
  });

  $("#btnRegister")?.addEventListener("click", async () => {
    const u = $("#reg_user")?.value?.trim();
    const p = $("#reg_pass")?.value ?? "";
    const r = $("#reg_role")?.value ?? "broker";
    $("#regMsg").textContent = "";
    if (!u || !p){ $("#regMsg").textContent = "Enter username + password."; return; }

    try{
      setStatus("Registering…");
      await apiPost("/auth/register", { username: u, password: p, role: r });
      $("#regMsg").textContent = "Registered. You can login now.";
      setStatus("Registered.");
    }catch(e){
      $("#regMsg").textContent = String(e.message || e);
      setStatus("Register failed.");
    }
  });

  // Calculator
  $("#btnCalc")?.addEventListener("click", runCalc);

  // Raw JSON toggle
  $("#btnToggleRaw")?.addEventListener("click", () => {
    const raw = $("#rawBox");
    if (!raw) return;
    const isHidden = raw.style.display === "none" || raw.style.display === "";
    if (isHidden){
      show(raw);
      $("#btnToggleRaw").textContent = "Hide raw JSON";
    } else {
      hide(raw);
      $("#btnToggleRaw").textContent = "Show raw JSON";
    }
  });
}

async function runCalc(){
  $("#calcMsg").textContent = "";
  setStatus("Calculating…");

  const miles = num($("#miles").value, 0);
  const linehaul_rate = num($("#linehaul_rate").value, 0);
  const deadhead_miles = num($("#deadhead_miles").value, 0);
  const deadhead_rate = num($("#deadhead_rate").value, 0);
  const detention = num($("#detention").value, 0);
  const lumper_fee = num($("#lumper_fee").value, 0);
  const extra_stop_fee = num($("#extra_stop_fee").value, 0);

  const qs = new URLSearchParams({
    miles: String(miles),
    linehaul_rate: String(linehaul_rate),
    deadhead_miles: String(deadhead_miles),
    deadhead_rate: String(deadhead_rate),
    detention: String(detention),
    lumper_fee: String(lumper_fee),
    extra_stop_fee: String(extra_stop_fee),
  });

  try{
    const data = await apiGet(`/calculate-rate?${qs.toString()}`);

    // Always stash raw JSON (but keep hidden unless user asks)
    const rawBox = $("#rawBox");
    if (rawBox) rawBox.textContent = JSON.stringify(data, null, 2);

    renderResults(data);
    setStatus("Done.");
  }catch(e){
    $("#calcMsg").textContent = String(e.message || e);
    setStatus("Error.");
  }
}

function renderResults(data){
  const breakdown = data?.breakdown || {};
  const fuel = data?.fuel || {};
  const inputs = data?.inputs || {};

  const total = num(breakdown.total, 0);
  const fuel_total = num(breakdown.fuel_total, 0);

  $("#statTotal").textContent = money(total);
  $("#statFuel").textContent = money(fuel_total);

  // Breakdown lines (clean, no raw JSON dump)
  const lines = [
    ["Linehaul", money(breakdown.linehaul_total)],
    ["Deadhead", money(breakdown.deadhead_total)],
    ["Fuel", money(breakdown.fuel_total)],
    ["Accessorials", money(breakdown.accessorials_total)],
  ];

  $("#breakdownLines").innerHTML = `
    <div class="line">
      <div class="k">Subtotal</div>
      <div class="v">${money(breakdown.subtotal)}</div>
    </div>
    ${lines.map(([k,v]) => `
      <div class="line">
        <div class="k">${esc(k)}</div>
        <div class="v">${esc(v)}</div>
      </div>
    `).join("")}
    <div class="line total">
      <div class="k">Total</div>
      <div class="v">${money(breakdown.total)}</div>
    </div>
  `;

  // Details (still readable; hides API key/source junk)
  const diesel = fuel?.diesel_price == null ? "—" : fixed(fuel.diesel_price, 3);
  const fspm = fuel?.fuel_surcharge_per_mile == null ? "—" : fixed(fuel.fuel_surcharge_per_mile, 4);
  const fuelNote = fuel?.error ? esc(fuel.error) : "OK";

  $("#detailsBody").innerHTML = `
    <div class="detailsGrid">
      <div class="detailBlock">
        <div class="detailTitle">Inputs</div>
        <div class="detailRow"><span>Miles</span><span>${esc(inputs.miles)}</span></div>
        <div class="detailRow"><span>Linehaul rate</span><span>${esc(inputs.linehaul_rate)}</span></div>
        <div class="detailRow"><span>Deadhead miles</span><span>${esc(inputs.deadhead_miles)}</span></div>
        <div class="detailRow"><span>Deadhead rate</span><span>${esc(inputs.deadhead_rate)}</span></div>
        <div class="detailRow"><span>Detention</span><span>${esc(inputs.detention)}</span></div>
        <div class="detailRow"><span>Lumper</span><span>${esc(inputs.lumper_fee)}</span></div>
        <div class="detailRow"><span>Extra stop</span><span>${esc(inputs.extra_stop_fee)}</span></div>
      </div>

      <div class="detailBlock">
        <div class="detailTitle">Fuel</div>
        <div class="detailRow"><span>Diesel price</span><span>${esc(diesel)}</span></div>
        <div class="detailRow"><span>Fuel surcharge / mile</span><span>${esc(fspm)}</span></div>
        <div class="detailRow"><span>Base price</span><span>${esc(fuel.base_price ?? "—")}</span></div>
        <div class="detailRow"><span>Multiplier</span><span>${esc(fuel.multiplier_used ?? "—")}</span></div>
        <div class="detailRow"><span>Status</span><span>${fuel?.error ? `<span class="bad">${fuelNote}</span>` : `<span class="good">${fuelNote}</span>`}</span></div>
      </div>
    </div>
  `;
}

document.addEventListener("DOMContentLoaded", render);