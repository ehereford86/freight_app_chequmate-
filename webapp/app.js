/*
  Chequmate Freight App UI
  - same-origin API calls (works local + Render)
  - ALWAYS renders UI (prevents blank white page)
  - login/register stores token if your auth endpoints return one
*/

const API_BASE = ""; // same-origin

function $(sel){ return document.querySelector(sel); }
function esc(s){ return String(s ?? "").replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function getToken(){ return localStorage.getItem("token") || ""; }
function setToken(t){ localStorage.setItem("token", t); }
function clearToken(){ localStorage.removeItem("token"); }

function setStatus(txt){
  const el = $("#status");
  if(el) el.textContent = txt || "";
}

function setOutput(txt){
  const el = $("#output");
  if(!el) return;
  el.textContent = txt || "";
}

async function apiFetch(path, opts={}){
  const headers = Object.assign({}, opts.headers || {});
  const tok = getToken();
  if(tok) headers["Authorization"] = `Bearer ${tok}`;

  const res = await fetch(API_BASE + path, {
    method: opts.method || "GET",
    headers,
    body: opts.body || undefined
  });

  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }

  if(!res.ok){
    const msg = data?.detail || data?.error || data?.message || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

async function apiPostJson(path, payload){
  return apiFetch(path, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
}

function renderShell(){
  $("#app").innerHTML = `
    <div class="page">
      <header class="topbar">
        <div class="brand">
          <img class="logo" src="/webapp/assets/chequmate-logo.png" alt="Chequmate" />
          <div class="brandtext">
            <div class="title">Chequmate Freight</div>
            <div class="subtitle">Broker · Dispatcher · Driver</div>
          </div>
        </div>

        <div class="right">
          <div class="pill" id="whoami">Not logged in</div>
        </div>
      </header>

      <div class="grid">
        <section class="card">
          <h2>Login</h2>
          <div class="row">
            <input id="login_user" placeholder="Username" autocomplete="username" />
            <input id="login_pass" type="password" placeholder="Password" autocomplete="current-password" />
          </div>
          <div class="row">
            <button class="btn" id="loginBtn">Login</button>
            <button class="btn2" id="logoutBtn" style="display:none;">Logout</button>
          </div>
          <div class="muted" id="loginMsg"></div>
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
            <button class="btn" id="regBtn">Register</button>
          </div>
          <div class="muted" id="regMsg"></div>
        </section>

        <section class="card span2">
          <h2>Rate + Fuel Surcharge Calculator</h2>

          <div class="formgrid">
            <label>Miles
              <input id="miles" type="number" step="1" value="650" />
            </label>

            <label>Linehaul rate ($/mile)
              <input id="linehaul_rate" type="number" step="0.01" value="3.00" />
            </label>

            <label>Deadhead miles
              <input id="deadhead_miles" type="number" step="1" value="75" />
            </label>

            <label>Deadhead rate ($/mile)
              <input id="deadhead_rate" type="number" step="0.01" value="0.00" />
            </label>

            <label>Detention ($)
              <input id="detention" type="number" step="0.01" value="0.00" />
            </label>

            <label>Lumper fee ($)
              <input id="lumper_fee" type="number" step="0.01" value="0.00" />
            </label>

            <label>Extra stop fee ($)
              <input id="extra_stop_fee" type="number" step="0.01" value="0.00" />
            </label>
          </div>

          <div class="row">
            <button class="btn" id="calcBtn">Calculate</button>
            <div class="muted" id="status">Ready.</div>
          </div>

          <h3>Output</h3>
          <pre class="output" id="output">Waiting...</pre>
        </section>
      </div>
    </div>
  `;
}

function money(n){
  const x = Number(n);
  if(!Number.isFinite(x)) return "$0.00";
  return x.toLocaleString(undefined, {style:"currency", currency:"USD"});
}

function formatResult(data){
  // Make a human-readable output first, then raw JSON below.
  const total = data?.breakdown?.total ?? data?.breakdown?.subtotal ?? 0;
  const linehaul = data?.breakdown?.linehaul_total ?? 0;
  const fuel = data?.breakdown?.fuel_total ?? 0;
  const deadhead = data?.breakdown?.deadhead_total ?? 0;
  const acc = data?.breakdown?.accessorials_total ?? 0;

  const diesel = data?.fuel?.diesel_price;
  const fspm = data?.fuel?.fuel_surcharge_per_mile;

  let out = "";
  out += `TOTAL: ${money(total)}\n`;
  out += `Linehaul: ${money(linehaul)}\n`;
  out += `Deadhead: ${money(deadhead)}\n`;
  out += `Fuel: ${money(fuel)}\n`;
  out += `Accessorials: ${money(acc)}\n\n`;

  if(diesel != null) out += `Diesel price: ${diesel}\n`;
  if(fspm != null) out += `Fuel surcharge per mile: ${fspm}\n`;
  if(data?.fuel?.error) out += `Fuel note: ${data.fuel.error}\n`;

  out += `\n--- RAW ---\n`;
  out += JSON.stringify(data, null, 2);
  return out;
}

async function refreshWhoAmI(){
  const who = $("#whoami");
  const logoutBtn = $("#logoutBtn");
  const loginBtn = $("#loginBtn");

  const tok = getToken();
  if(!tok){
    if(who) who.textContent = "Not logged in";
    if(logoutBtn) logoutBtn.style.display = "none";
    if(loginBtn) loginBtn.style.display = "";
    return;
  }

  try{
    // try common endpoints — if you don't have /auth/me yet, this will fail silently.
    const me = await apiFetch("/auth/me");
    const role = me?.role || me?.user?.role || "user";
    const name = me?.username || me?.user?.username || "User";
    if(who) who.textContent = `${name} (${role})`;
  }catch{
    // token exists but endpoint missing or token invalid
    if(who) who.textContent = "Logged in (token set)";
  }

  if(logoutBtn) logoutBtn.style.display = "";
  if(loginBtn) loginBtn.style.display = "none";
}

function bindHandlers(){
  $("#logoutBtn")?.addEventListener("click", () => {
    clearToken();
    $("#loginMsg").textContent = "Logged out.";
    refreshWhoAmI();
  });

  $("#loginBtn")?.addEventListener("click", async () => {
    $("#loginMsg").textContent = "";
    try{
      const username = ($("#login_user")?.value || "").trim();
      const password = $("#login_pass")?.value || "";

      if(!username || !password) throw new Error("Enter username + password.");

      // Try typical login shapes
      const res = await apiPostJson("/auth/login", {username, password});

      // support multiple token response styles
      const token =
        res?.access_token ||
        res?.token ||
        res?.jwt ||
        res?.data?.access_token ||
        "";

      if(!token) throw new Error("Login succeeded but no token was returned.");

      setToken(token);
      $("#loginMsg").textContent = "Logged in.";
      refreshWhoAmI();

    }catch(e){
      $("#loginMsg").textContent = String(e.message || e);
    }
  });

  $("#regBtn")?.addEventListener("click", async () => {
    $("#regMsg").textContent = "";
    try{
      const username = ($("#reg_user")?.value || "").trim();
      const password = $("#reg_pass")?.value || "";
      const role = $("#reg_role")?.value || "driver";

      if(!username || !password) throw new Error("Enter username + password.");

      const res = await apiPostJson("/auth/register", {username, password, role});
      $("#regMsg").textContent = "Registered. Now login.";

      // Some APIs auto-login on register:
      const token = res?.access_token || res?.token || "";
      if(token){
        setToken(token);
        $("#regMsg").textContent = "Registered + logged in.";
        refreshWhoAmI();
      }
    }catch(e){
      $("#regMsg").textContent = String(e.message || e);
    }
  });

  $("#calcBtn")?.addEventListener("click", async () => {
    try{
      setStatus("Calculating...");
      const miles = Number($("#miles")?.value || 0);
      const linehaul_rate = Number($("#linehaul_rate")?.value || 0);
      const deadhead_miles = Number($("#deadhead_miles")?.value || 0);
      const deadhead_rate = Number($("#deadhead_rate")?.value || 0);
      const detention = Number($("#detention")?.value || 0);
      const lumper_fee = Number($("#lumper_fee")?.value || 0);
      const extra_stop_fee = Number($("#extra_stop_fee")?.value || 0);

      const qs = new URLSearchParams({
        miles: String(miles),
        linehaul_rate: String(linehaul_rate),
        deadhead_miles: String(deadhead_miles),
        deadhead_rate: String(deadhead_rate),
        detention: String(detention),
        lumper_fee: String(lumper_fee),
        extra_stop_fee: String(extra_stop_fee)
      });

      const data = await apiFetch(`/calculate-rate?${qs.toString()}`);
      setOutput(formatResult(data));
      setStatus("Done.");
    }catch(e){
      setStatus("Error.");
      setOutput(`ERROR: ${String(e.message || e)}`);
    }
  });
}

function boot(){
  renderShell();
  bindHandlers();
  refreshWhoAmI();
  setOutput("Ready. Enter values and press Calculate.");
}

if(document.readyState === "loading"){
  document.addEventListener("DOMContentLoaded", boot);
}else{
  boot();
}
