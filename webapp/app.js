/*
  Chequmate Freight App UI
  - Keeps Login + Register
  - Keeps Calculator
  - Results formatted (NO raw text unless you click "Show raw JSON"):
      * two stat cards: Total + Fuel (est.)
      * breakdown rows: label left, value right
  - Uses backend route: GET /calculate-rate (per your OpenAPI)
*/

const API_BASE = ""; // same-origin

function $(sel){ return document.querySelector(sel); }
function num(v, fallback=0){
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}
function money(v){
  const n = num(v, 0);
  return n.toLocaleString(undefined, { style:"currency", currency:"USD" });
}

function getToken(){ return localStorage.getItem("token") || ""; }
function setToken(t){ localStorage.setItem("token", t); }
function clearToken(){ localStorage.removeItem("token"); }

async function apiGet(path){
  const headers = {};
  const token = getToken();
  if(token) headers["Authorization"] = `Bearer ${token}`;

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
  const token = getToken();
  if(token) headers["Authorization"] = `Bearer ${token}`;

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

function setStatusPill(text){
  const el = $("#statusPill");
  if(el) el.textContent = text;
}

function setAuthBadge(){
  const token = getToken();
  const badge = $("#authBadge");
  if(!badge) return;
  badge.textContent = token ? "Logged in" : "Not logged in";
}

function buildQuery(){
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

function kvRow(label, value){
  return `
    <div class="kv">
      <div class="k">${label}</div>
      <div class="v">${value}</div>
    </div>
  `;
}

function applyResults(data){
  // Accept multiple response shapes without breaking UI
  const breakdown = data.breakdown || data.totals || data || {};

  const total =
    data.total ?? breakdown.total ?? breakdown.grand_total ?? 0;

  const fuel =
    (data.fuel && (data.fuel.fuel_total ?? data.fuel.total ?? data.fuel.est ?? 0)) ??
    breakdown.fuel_total ?? breakdown.fuel ?? 0;

  const linehaul =
    breakdown.linehaul_total ?? breakdown.linehaul ?? 0;

  const deadhead =
    breakdown.deadhead_total ?? breakdown.deadhead ?? 0;

  const accessorials =
    breakdown.accessorials_total ?? breakdown.accessorials ?? 0;

  const subtotal =
    breakdown.subtotal ?? 0;

  $("#totalStat").textContent = money(total);
  $("#fuelStat").textContent  = money(fuel);

  const rows = [];
  rows.push(kvRow("Linehaul", money(linehaul)));
  rows.push(kvRow("Deadhead", money(deadhead)));
  rows.push(kvRow("Fuel", money(fuel)));
  if(num(accessorials,0) !== 0) rows.push(kvRow("Accessorials", money(accessorials)));
  if(num(subtotal,0) !== 0) rows.push(kvRow("Subtotal", money(subtotal)));
  rows.push(`<div class="divider"></div>`);
  rows.push(kvRow("Total", money(total)));

  $("#breakdown").innerHTML = rows.join("");

  $("#raw").textContent = JSON.stringify(data, null, 2);
}

async function doCalculate(){
  try{
    setStatusPill("CALC_UI_v1_2026-01-17");
    const data = await apiGet(`/calculate-rate?${buildQuery()}`);
    applyResults(data);
  }catch(err){
    setStatusPill(`Calc failed: ${err.message}`);
    // Keep layout, just show zeros
    $("#totalStat").textContent = money(0);
    $("#fuelStat").textContent  = money(0);
    $("#breakdown").innerHTML = kvRow("Total", money(0));
    $("#raw").textContent = "";
  }
}

async function doRegister(){
  const u = ($("#reg_username")?.value || "").trim();
  const p = ($("#reg_password")?.value || "").trim();
  const r = $("#reg_role")?.value || "driver";

  if(!u || !p){
    setStatusPill("Register failed: missing username/password");
    return;
  }

  try{
    const data = await apiPost("/register", { username:u, password:p, role:r });
    // Many backends return token on register; if not, user can login
    if(data?.token) setToken(data.token);
    setAuthBadge();
    setStatusPill("Registered");
  }catch(err){
    setStatusPill(`Register failed: ${err.message}`);
  }
}

async function doLogin(){
  const u = ($("#login_username")?.value || "").trim();
  const p = ($("#login_password")?.value || "").trim();

  if(!u || !p){
    setStatusPill("Login failed: missing username/password");
    return;
  }

  try{
    const data = await apiPost("/login", { username:u, password:p });
    if(data?.token){
      setToken(data.token);
      setAuthBadge();
      setStatusPill("Logged in");
    }else{
      setStatusPill("Login failed: no token returned");
    }
  }catch(err){
    setStatusPill(`Login failed: ${err.message}`);
  }
}

function doLogout(){
  clearToken();
  setAuthBadge();
  setStatusPill("Logged out");
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

      <!-- AUTH (keep login/register on the page) -->
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

      <!-- CALCULATOR -->
      <section class="card">
        <h2>Calculator</h2>

        <!-- 2-column grid like your screenshot -->
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

        <!-- EXACT: two stat cards -->
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

        <!-- EXACT: breakdown rows (label left, value right) -->
        <div class="breakdown" id="breakdown">
          ${kvRow("Total", money(0))}
        </div>

        <pre class="raw" id="raw" style="display:none;"></pre>
      </section>
    </div>
  `;

  // wire up buttons
  $("#calcBtn").addEventListener("click", doCalculate);
  $("#rawBtn").addEventListener("click", () => {
    const el = $("#raw");
    el.style.display = (el.style.display === "none") ? "block" : "none";
  });

  $("#loginBtn").addEventListener("click", doLogin);
  $("#registerBtn").addEventListener("click", doRegister);
  $("#logoutBtn").addEventListener("click", doLogout);

  setAuthBadge();
}

document.addEventListener("DOMContentLoaded", render);
