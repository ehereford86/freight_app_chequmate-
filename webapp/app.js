/*
  UI requirements (what you asked for):
  1) Keep Login + Register on the page.
  2) Calculator stays 2-column layout.
  3) Results are NOT raw text:
     - 2 stat cards: Total + Fuel (est.)
     - Breakdown rows: label left, value right
  4) Calls real backend route: GET /calculate-rate (per your OpenAPI).
*/

const API_BASE = ""; // same-origin

const $ = (sel) => document.querySelector(sel);

const num = (v, fallback=0) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

const money = (v) => {
  const n = num(v, 0);
  return n.toLocaleString(undefined, { style:"currency", currency:"USD" });
};

const getToken = () => localStorage.getItem("token") || "";
const setToken = (t) => localStorage.setItem("token", t);
const clearToken = () => localStorage.removeItem("token");

function setStatus(text){
  const el = $("#statusPill");
  if(el) el.textContent = text;
}

function setAuthBadge(){
  const el = $("#authBadge");
  if(!el) return;
  el.textContent = getToken() ? "Logged in" : "Not logged in";
}

async function apiGet(path){
  const headers = {};
  const tok = getToken();
  if(tok) headers["Authorization"] = `Bearer ${tok}`;

  const res = await fetch(API_BASE + path, { method:"GET", headers });
  const txt = await res.text();

  let data;
  try { data = JSON.parse(txt); } catch { data = { raw: txt }; }

  if(!res.ok){
    throw new Error(data?.detail || data?.error || `HTTP ${res.status}`);
  }
  return data;
}

async function apiPost(path, body){
  const headers = { "Content-Type":"application/json" };
  const tok = getToken();
  if(tok) headers["Authorization"] = `Bearer ${tok}`;

  const res = await fetch(API_BASE + path, {
    method:"POST",
    headers,
    body: JSON.stringify(body || {})
  });

  const txt = await res.text();
  let data;
  try { data = JSON.parse(txt); } catch { data = { raw: txt }; }

  if(!res.ok){
    throw new Error(data?.detail || data?.error || `HTTP ${res.status}`);
  }
  return data;
}

function kvRow(label, value){
  return `
    <div class="kv">
      <div class="k">${label}</div>
      <div class="v">${value}</div>
    </div>
  `;
}

function readCalcInputs(){
  return {
    miles: num($("#miles").value, 0),
    linehaul_rate: num($("#linehaul_rate").value, 0),
    deadhead_miles: num($("#deadhead_miles").value, 0),
    deadhead_rate: num($("#deadhead_rate").value, 0),
    detention: num($("#detention").value, 0),
    lumper_fee: num($("#lumper_fee").value, 0),
    extra_stop_fee: num($("#extra_stop_fee").value, 0),
  };
}

function buildQuery(obj){
  const p = new URLSearchParams();
  for(const [k,v] of Object.entries(obj)){
    p.set(k, String(v));
  }
  return p.toString();
}

function normalizeResponse(data){
  // Your API has evolved; this makes UI stable.
  // Expected common shapes:
  //  - { breakdown:{...}, fuel:{...}, ... }
  //  - { total:..., fuel_total:..., linehaul_total:... }
  //  - { breakdown:{ total, linehaul_total, deadhead_total, fuel_total, accessorials_total, subtotal } }

  const breakdown = data.breakdown || data.totals || data || {};
  const fuelObj = data.fuel || {};

  const total =
    data.total ??
    breakdown.total ??
    breakdown.grand_total ??
    0;

  const fuel =
    fuelObj.fuel_total ??
    fuelObj.total ??
    breakdown.fuel_total ??
    breakdown.fuel ??
    0;

  const linehaul =
    breakdown.linehaul_total ??
    breakdown.linehaul ??
    0;

  const deadhead =
    breakdown.deadhead_total ??
    breakdown.deadhead ??
    0;

  const accessorials =
    breakdown.accessorials_total ??
    breakdown.accessorials ??
    0;

  const subtotal =
    breakdown.subtotal ??
    0;

  return { total, fuel, linehaul, deadhead, accessorials, subtotal, raw:data };
}

function renderResults(data){
  const n = normalizeResponse(data);

  $("#totalStat").textContent = money(n.total);
  $("#fuelStat").textContent  = money(n.fuel);

  const rows = [];
  rows.push(kvRow("Linehaul", money(n.linehaul)));
  rows.push(kvRow("Deadhead", money(n.deadhead)));
  rows.push(kvRow("Fuel", money(n.fuel)));
  if(num(n.accessorials,0) !== 0) rows.push(kvRow("Accessorials", money(n.accessorials)));
  if(num(n.subtotal,0) !== 0) rows.push(kvRow("Subtotal", money(n.subtotal)));
  rows.push(`<div class="divider"></div>`);
  rows.push(kvRow("Total", money(n.total)));

  $("#breakdown").innerHTML = rows.join("");
  $("#raw").textContent = JSON.stringify(n.raw, null, 2);
}

async function doCalculate(){
  try{
    setStatus("CALC_UI_v1_2026-01-17");
    const q = buildQuery(readCalcInputs());
    const data = await apiGet(`/calculate-rate?${q}`);
    renderResults(data);
  }catch(err){
    setStatus(`Calc failed: ${err.message}`);
    // Keep the SAME formatted layout, just show zeros
    $("#totalStat").textContent = money(0);
    $("#fuelStat").textContent  = money(0);
    $("#breakdown").innerHTML = kvRow("Total", money(0));
    $("#raw").textContent = "";
  }
}

async function doRegister(){
  const u = ($("#reg_username").value || "").trim();
  const p = ($("#reg_password").value || "").trim();
  const r = $("#reg_role").value || "driver";

  if(!u || !p){
    setStatus("Register failed: missing username/password");
    return;
  }

  try{
    const data = await apiPost("/register", { username:u, password:p, role:r });
    if(data?.token) setToken(data.token);
    setAuthBadge();
    setStatus("Registered");
  }catch(err){
    setStatus(`Register failed: ${err.message}`);
  }
}

async function doLogin(){
  const u = ($("#login_username").value || "").trim();
  const p = ($("#login_password").value || "").trim();

  if(!u || !p){
    setStatus("Login failed: missing username/password");
    return;
  }

  try{
    const data = await apiPost("/login", { username:u, password:p });
    if(data?.token){
      setToken(data.token);
      setAuthBadge();
      setStatus("Logged in");
    }else{
      setStatus("Login failed: no token returned");
    }
  }catch(err){
    setStatus(`Login failed: ${err.message}`);
  }
}

function doLogout(){
  clearToken();
  setAuthBadge();
  setStatus("Logged out");
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

        <div class="rightPills">
          <div class="pill" id="authBadge">Not logged in</div>
          <div class="pill" id="statusPill">CALC_UI_v1_2026-01-17</div>
        </div>
      </header>

      <!-- AUTH -->
      <section class="card">
        <div class="cardHeaderRow">
          <h2>Login</h2>
          <button class="btn2" id="logoutBtn" type="button">Logout</button>
        </div>

        <div class="form2">
          <div class="field">
            <label>Username</label>
            <input id="login_username" placeholder="Username" />
          </div>
          <div class="field">
            <label>Password</label>
            <input id="login_password" type="password" placeholder="Password" />
          </div>
        </div>

        <div class="btnrow">
          <button class="btn" id="loginBtn" type="button">Login</button>
        </div>

        <div style="height:14px"></div>

        <h2>Register</h2>
        <div class="form2">
          <div class="field">
            <label>Username</label>
            <input id="reg_username" placeholder="Username" />
          </div>
          <div class="field">
            <label>Password</label>
            <input id="reg_password" type="password" placeholder="Password" />
          </div>
          <div class="field">
            <label>Role</label>
            <select id="reg_role">
              <option value="broker">Broker</option>
              <option value="dispatcher">Dispatcher</option>
              <option value="driver" selected>Driver</option>
            </select>
          </div>
          <div class="field">
            <label>&nbsp;</label>
            <button class="btn" id="registerBtn" type="button">Register</button>
          </div>
        </div>
      </section>

      <!-- CALCULATOR (2-column like your screenshot) -->
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
          <button class="btn" id="calcBtn" type="button">Calculate</button>
          <button class="btn2" id="rawBtn" type="button">Show raw JSON</button>
        </div>

        <div class="hint">
          Tip: If fuel is unavailable, totals still calculate — fuel shows $0 and an explanation.
        </div>

        <div class="resultsTitle">Results</div>

        <!-- Two stat cards (Total + Fuel est.) -->
        <div class="statGrid">
          <div class="stat">
            <div class="statLabel">Total</div>
            <div class="statValue" id="totalStat">$0.00</div>
          </div>

          <div class="stat">
            <div class="statLabel">Fuel (est.)</div>
            <div class="statValue" id="fuelStat">$0.00</div>
          </div>
        </div>

        <!-- Breakdown rows: label left, value right -->
        <div class="breakdown" id="breakdown">
          ${kvRow("Total", money(0))}
        </div>

        <pre class="raw" id="raw" style="display:none;"></pre>
      </section>
    </div>
  `;

  $("#calcBtn").addEventListener("click", doCalculate);

  $("#rawBtn").addEventListener("click", () => {
    const el = $("#raw");
    el.style.display = (el.style.display === "none") ? "block" : "none";
  });

  $("#loginBtn").addEventListener("click", doLogin);
  $("#registerBtn").addEventListener("click", doRegister);
  $("#logoutBtn").addEventListener("click", doLogout);

  setAuthBadge();
  setStatus("CALC_UI_v1_2026-01-17");
}

document.addEventListener("DOMContentLoaded", render);
