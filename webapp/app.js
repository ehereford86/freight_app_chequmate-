/* Chequmate Freight App UI
   - Default: formatted calculator + results (NO raw JSON)
   - Raw JSON only when user clicks "Show raw JSON"
   - Same-origin API calls (works local + Render)
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
  return n.toLocaleString(undefined, { style:"currency", currency:"USD" });
}
function fixed(v, d=2){
  return num(v, 0).toFixed(d);
}

function getToken(){ return localStorage.getItem("token") || ""; }
function setToken(t){ localStorage.setItem("token", t); }
function clearToken(){ localStorage.removeItem("token"); }

async function apiFetch(path, opts={}){
  const headers = Object.assign({}, opts.headers || {});
  const t = getToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch(API_BASE + path, Object.assign({}, opts, { headers }));
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok){
    const msg = data?.detail || data?.error || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function setStatus(txt){
  const el = $("#statusText");
  if (el) el.textContent = txt || "";
}

function render(){
  const token = getToken();
  const loggedIn = !!token;

  $("#app").innerHTML = `
    <div class="page">
      <header class="topbar">
        <div class="brand">
          <img class="logo" src="/webapp/assets/chequmate-logo.png" alt="Chequmate" />
          <div class="brandtext">
            <div class="title">Freight App</div>
            <div class="subtitle">Calculator · Dispatcher · Driver testing UI</div>
          </div>
        </div>

        <div class="right">
          <div class="pill" id="statusPill">${loggedIn ? "Logged in" : "Not logged in"}</div>
          <div class="pill small" id="statusText">Ready.</div>
        </div>
      </header>

      <section class="panel">
        <div class="panelTitle">Account</div>

        <div class="grid2">
          <div class="card">
            <div class="cardTitle">Login</div>
            <label class="lbl">Username</label>
            <input id="login_user" class="in" placeholder="username" autocomplete="username"/>
            <label class="lbl">Password</label>
            <input id="login_pass" class="in" placeholder="password" type="password" autocomplete="current-password"/>
            <div class="row">
              <button id="loginBtn" class="btn">Login</button>
              <button id="logoutBtn" class="btn ghost">Logout</button>
            </div>
            <div class="hint">If you don’t have an account yet, register below.</div>
          </div>

          <div class="card">
            <div class="cardTitle">Register</div>
            <label class="lbl">Username</label>
            <input id="reg_user" class="in" placeholder="username" autocomplete="username"/>
            <label class="lbl">Password</label>
            <input id="reg_pass" class="in" placeholder="password" type="password" autocomplete="new-password"/>
            <label class="lbl">Role</label>
            <select id="reg_role" class="in">
              <option value="broker">Broker</option>
              <option value="dispatcher">Dispatcher</option>
              <option value="driver">Driver</option>
            </select>
            <button id="regBtn" class="btn">Create account</button>
            <div class="hint">Broker / Dispatcher / Driver accounts all start here.</div>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panelTitle">Calculator</div>

        <div class="grid2">
          <div class="card">
            <label class="lbl">Miles</label>
            <input id="miles" class="in" value="1375" />

            <label class="lbl">Deadhead miles</label>
            <input id="deadhead_miles" class="in" value="75" />

            <label class="lbl">Detention ($)</label>
            <input id="detention" class="in" value="0" />

            <label class="lbl">Extra stop ($)</label>
            <input id="extra_stop_fee" class="in" value="0" />
          </div>

          <div class="card">
            <label class="lbl">Linehaul rate ($/mile)</label>
            <input id="linehaul_rate" class="in" value="3.00" />

            <label class="lbl">Deadhead rate ($/mile)</label>
            <input id="deadhead_rate" class="in" value="0" />

            <label class="lbl">Lumper ($)</label>
            <input id="lumper_fee" class="in" value="0" />

            <label class="lbl">Fuel surcharge (auto)</label>
            <div class="pill wide">Auto from EIA</div>
          </div>
        </div>

        <div class="row">
          <button id="calcBtn" class="btn">Calculate</button>
          <button id="toggleRawBtn" class="btn ghost">Show raw JSON</button>
        </div>

        <div class="hint">
          Tip: If fuel is unavailable, totals still calculate — fuel shows $0 and an explanation.
        </div>
      </section>

      <section class="panel">
        <div class="panelTitle">Results</div>

        <div class="grid2">
          <div class="card">
            <div class="mini">Total</div>
            <div class="big" id="totalBig">$0.00</div>
          </div>
          <div class="card">
            <div class="mini">Fuel (est.)</div>
            <div class="big" id="fuelBig">$0.00</div>
          </div>
        </div>

        <div class="card">
          <div class="rows" id="lineItems"></div>
        </div>

        <div class="card" id="rawCard" style="display:none;">
          <div class="cardTitle">Raw JSON</div>
          <pre class="code" id="rawJson"></pre>
        </div>
      </section>
    </div>
  `;

  wireUp();
}

function wireUp(){
  $("#loginBtn").onclick = doLogin;
  $("#logoutBtn").onclick = () => { clearToken(); setStatus("Logged out."); render(); };
  $("#regBtn").onclick = doRegister;
  $("#calcBtn").onclick = doCalc;

  let rawVisible = false;
  $("#toggleRawBtn").onclick = () => {
    rawVisible = !rawVisible;
    $("#rawCard").style.display = rawVisible ? "block" : "none";
    $("#toggleRawBtn").textContent = rawVisible ? "Hide raw JSON" : "Show raw JSON";
  };
}

async function doRegister(){
  try{
    setStatus("Registering…");
    const body = {
      username: ($("#reg_user").value || "").trim(),
      password: $("#reg_pass").value || "",
      role: $("#reg_role").value || "broker",
    };
    if (!body.username || !body.password) throw new Error("Username + password required");

    // Try common endpoint names (your backend may differ)
    const data = await tryPost(["/auth/register", "/register", "/auth/signup", "/signup"], body);
    setStatus("Account created. Now login.");
    // Some backends return token on register:
    if (data?.token){ setToken(data.token); setStatus("Registered + logged in."); render(); }
  } catch(e){
    setStatus(`Register failed: ${e.message}`);
  }
}

async function doLogin(){
  try{
    setStatus("Logging in…");
    const body = {
      username: ($("#login_user").value || "").trim(),
      password: $("#login_pass").value || "",
    };
    if (!body.username || !body.password) throw new Error("Username + password required");

    const data = await tryPost(["/auth/login", "/login", "/auth/token", "/token"], body);
    if (!data?.token) throw new Error("No token returned from server");
    setToken(data.token);
    setStatus("Logged in.");
    render();
  } catch(e){
    setStatus(`Login failed: ${e.message}`);
  }
}

async function tryPost(paths, body){
  let lastErr = null;
  for (const p of paths){
    try{
      return await apiFetch(p, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch(e){
      lastErr = e;
    }
  }
  throw lastErr || new Error("No matching endpoint");
}

async function doCalc(){
  try{
    setStatus("Calculating…");

    const payload = {
      miles: num($("#miles").value, 0),
      linehaul_rate: num($("#linehaul_rate").value, 0),
      deadhead_miles: num($("#deadhead_miles").value, 0),
      deadhead_rate: num($("#deadhead_rate").value, 0),
      detention: num($("#detention").value, 0),
      lumper_fee: num($("#lumper_fee").value, 0),
      extra_stop_fee: num($("#extra_stop_fee").value, 0),
    };

    // Try common calculator endpoints
    const data = await tryGet([
      `/pricing/calc?miles=${payload.miles}&linehaul_rate=${payload.linehaul_rate}&deadhead_miles=${payload.deadhead_miles}&deadhead_rate=${payload.deadhead_rate}&detention=${payload.detention}&lumper_fee=${payload.lumper_fee}&extra_stop_fee=${payload.extra_stop_fee}`,
      `/pricing/calculate?miles=${payload.miles}&linehaul_rate=${payload.linehaul_rate}&deadhead_miles=${payload.deadhead_miles}&deadhead_rate=${payload.deadhead_rate}&detention=${payload.detention}&lumper_fee=${payload.lumper_fee}&extra_stop_fee=${payload.extra_stop_fee}`,
      `/calc?miles=${payload.miles}&linehaul_rate=${payload.linehaul_rate}&deadhead_miles=${payload.deadhead_miles}&deadhead_rate=${payload.deadhead_rate}&detention=${payload.detention}&lumper_fee=${payload.lumper_fee}&extra_stop_fee=${payload.extra_stop_fee}`,
    ]);

    // Always keep formatted view as the primary output:
    renderResults(data);

    // Raw JSON only exists in the hidden raw card:
    $("#rawJson").textContent = JSON.stringify(data, null, 2);

    setStatus("Done.");
  } catch(e){
    setStatus(`Calc failed: ${e.message}`);
  }
}

async function tryGet(paths){
  let lastErr = null;
  for (const p of paths){
    try{
      return await apiFetch(p, { method:"GET" });
    } catch(e){
      lastErr = e;
    }
  }
  throw lastErr || new Error("No matching endpoint");
}

function renderResults(data){
  // backend shapes vary; support common patterns
  const breakdown = data?.breakdown || data?.result || data || {};
  const total = breakdown.total ?? breakdown.grand_total ?? data?.total ?? 0;
  const fuelTotal = breakdown.fuel_total ?? data?.fuel?.fuel_total ?? data?.fuel_total ?? 0;

  $("#totalBig").textContent = money(total);
  $("#fuelBig").textContent = money(fuelTotal);

  // Line items: keep the “last screenshot” style (simple labeled rows)
  const linehaul = breakdown.linehaul_total ?? data?.linehaul_total ?? 0;
  const deadhead = breakdown.deadhead_total ?? data?.deadhead_total ?? 0;
  const detention = breakdown.detention_total ?? data?.detention_total ?? breakdown.detention ?? 0;
  const lumper = breakdown.lumper_total ?? data?.lumper_total ?? breakdown.lumper_fee ?? 0;
  const extra = breakdown.extra_stop_total ?? data?.extra_stop_total ?? breakdown.extra_stop_fee ?? 0;

  const rows = [
    ["Linehaul", money(linehaul)],
    ["Deadhead", money(deadhead)],
    ["Detention", money(detention)],
    ["Lumper", money(lumper)],
    ["Extra stop", money(extra)],
    ["Fuel", money(fuelTotal)],
  ];

  $("#lineItems").innerHTML = rows.map(([k,v]) => `
    <div class="rowline">
      <div class="k">${esc(k)}</div>
      <div class="v">${esc(v)}</div>
    </div>
  `).join("");

  // Optional fuel note
  const fuelErr = data?.fuel?.error || data?.fuel_error || null;
  if (fuelErr){
    $("#lineItems").insertAdjacentHTML("beforeend", `
      <div class="rowline note">
        <div class="k">Fuel note</div>
        <div class="v">${esc(String(fuelErr))}</div>
      </div>
    `);
  }
}

// Boot
document.addEventListener("DOMContentLoaded", render);
