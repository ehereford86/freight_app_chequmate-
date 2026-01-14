const API_BASE = ""; // same-origin (works locally + via ngrok)

function $(sel){ return document.querySelector(sel); }
function esc(s){ return String(s ?? "").replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function getToken(){ return localStorage.getItem("token") || ""; }
function setToken(t){ localStorage.setItem("token", t); }
function clearToken(){ localStorage.removeItem("token"); }

async function apiGet(path){
  const token = getToken();
  const res = await fetch(API_BASE + path, {
    headers: token ? { "Authorization": "Bearer " + token } : {}
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if(!res.ok){
    const msg = data?.detail || data?.error || ("HTTP " + res.status);
    throw new Error(msg);
  }
  return data;
}

function statusChip(label, kind){
  return `<span class="status ${kind}">${esc(label)}</span>`;
}

function renderShell(user){
  const role = user?.role || "guest";
  const bs = user?.broker_status || "none";
  const mc = user?.mc_number || "";
  const roleBadge = role === "guest" ? "Not logged in" : `Role: ${role}`;
  const brokerBadge =
    bs === "approved" ? statusChip("Broker: approved", "good") :
    bs === "pending" ? statusChip("Broker: pending", "warn") :
    bs === "rejected" ? statusChip("Broker: rejected", "bad") :
    statusChip("Broker: none", "bad");

  $("#app").innerHTML = `
    <div class="container">
      <div class="topbar">
        <div class="brand">
          <div class="logo"></div>
          <div>
            <h1>Freight App</h1>
            <div class="muted">Broker • Dispatcher • Driver testing UI</div>
          </div>
        </div>
        <div class="btns">
          <span class="badge">${esc(roleBadge)}</span>
          ${role !== "guest" ? `<span class="badge">MC: ${esc(mc || "-")}</span>` : ""}
          ${role !== "guest" ? brokerBadge : ""}
          ${role !== "guest" ? `<button class="secondary" id="btnLogout">Logout</button>` : ""}
        </div>
      </div>

      <div class="row" style="margin-top:16px">
        <div class="card" id="leftCard"></div>
        <div class="card" id="rightCard"></div>
      </div>

      <div class="row">
        <div class="card" id="calcCard"></div>
        <div class="card" id="outCard"></div>
      </div>
    </div>
  `;

  if(role !== "guest"){
    $("#btnLogout").onclick = () => { clearToken(); boot(); };
  }
}

function renderAuth(){
  $("#leftCard").innerHTML = `
    <h2>Login</h2>
    <div class="muted">Token is stored in the browser.</div>
    <hr />
    <div class="field">
      <label>Username</label>
      <input id="loginUser" placeholder="username" />
    </div>
    <div class="field">
      <label>Password</label>
      <input id="loginPass" type="password" placeholder="password" />
    </div>
    <div class="btns">
      <button id="btnLogin">Login</button>
    </div>
    <hr />
    <h2>Register (Dispatcher/Driver only)</h2>
    <div class="muted">Brokers must onboard with an MC number.</div>
    <hr />
    <div class="field">
      <label>Username</label>
      <input id="regUser" placeholder="new username" />
    </div>
    <div class="field">
      <label>Password</label>
      <input id="regPass" type="password" placeholder="new password" />
    </div>
    <div class="field">
      <label>Role</label>
      <select id="regRole">
        <option value="dispatcher">dispatcher</option>
        <option value="driver">driver</option>
      </select>
    </div>
    <div class="btns">
      <button class="secondary" id="btnRegister">Register</button>
    </div>
  `;

  $("#rightCard").innerHTML = `
    <h2>System</h2>
    <div class="muted">Basic health checks.</div>
    <hr />
    <div class="btns">
      <button class="secondary" id="btnHome">Ping API</button>
      <button class="secondary" id="btnFuel">Fuel Surcharge</button>
    </div>
    <hr />
    <pre id="sysOut">Ready.</pre>
  `;

  $("#calcCard").innerHTML = `
    <h2>Rate Calculator</h2>
    <div class="muted">Login optional for calculation.</div>
    <hr />
    ${calcFormHtml()}
    <div class="btns">
      <button id="btnCalc">Calculate</button>
    </div>
  `;

  $("#outCard").innerHTML = `
    <h2>Output</h2>
    <div class="muted">API responses show here.</div>
    <hr />
    <pre id="out">Ready.</pre>
  `;

  $("#btnHome").onclick = async () => {
    try { $("#sysOut").textContent = JSON.stringify(await apiGet("/"), null, 2); }
    catch(e){ $("#sysOut").textContent = e.message; }
  };

  $("#btnFuel").onclick = async () => {
    try { $("#sysOut").textContent = JSON.stringify(await apiGet("/fuel-surcharge"), null, 2); }
    catch(e){ $("#sysOut").textContent = e.message; }
  };

  $("#btnLogin").onclick = async () => {
    try{
      const u = $("#loginUser").value.trim();
      const p = $("#loginPass").value;
      if(!u || !p) throw new Error("Username and password required");
      const data = await apiGet(`/login?username=${encodeURIComponent(u)}&password=${encodeURIComponent(p)}`);
      setToken(data.access_token);
      boot();
    }catch(e){
      $("#sysOut").textContent = e.message;
    }
  };

  $("#btnRegister").onclick = async () => {
    try{
      const u = $("#regUser").value.trim();
      const p = $("#regPass").value;
      const r = $("#regRole").value;
      if(!u || !p) throw new Error("Username and password required");
      const data = await apiGet(`/register?username=${encodeURIComponent(u)}&password=${encodeURIComponent(p)}&role=${encodeURIComponent(r)}`);
      $("#sysOut").textContent = JSON.stringify(data, null, 2);
    }catch(e){
      $("#sysOut").textContent = e.message;
    }
  };

  $("#btnCalc").onclick = doCalc;
}

function calcFormHtml(){
  return `
    <div class="field"><label>Miles</label><input id="miles" type="number" step="0.1" value="500" /></div>
    <div class="field"><label>Linehaul Rate ($/mi)</label><input id="linehaul_rate" type="number" step="0.01" value="2.50" /></div>
    <div class="field"><label>Deadhead Miles</label><input id="deadhead_miles" type="number" step="0.1" value="0" /></div>
    <div class="field"><label>Deadhead Rate ($/mi)</label><input id="deadhead_rate" type="number" step="0.01" value="0" /></div>

    <hr />
    <div class="muted">Broker fees (optional)</div>
    <div class="field"><label>Broker Margin Percent (0.10 = 10%)</label><input id="broker_margin_percent" type="number" step="0.01" value="0.10" /></div>
    <div class="field"><label>Broker Fee Flat</label><input id="broker_fee_flat" type="number" step="0.01" value="0" /></div>

    <hr />
    <div class="muted">Accessorials (optional)</div>
    <div class="field"><label>Detention</label><input id="detention" type="number" step="0.01" value="0" /></div>
    <div class="field"><label>Lumper</label><input id="lumper_fee" type="number" step="0.01" value="0" /></div>
    <div class="field"><label>Extra Stop</label><input id="extra_stop_fee" type="number" step="0.01" value="0" /></div>
  `;
}

async function doCalc(){
  try{
    const q = new URLSearchParams();
    const fields = [
      "miles","linehaul_rate","deadhead_miles","deadhead_rate",
      "broker_margin_percent","broker_fee_flat",
      "detention","lumper_fee","extra_stop_fee"
    ];
    for(const f of fields){
      const v = document.getElementById(f).value;
      if(v !== "" && v !== null) q.set(f, v);
    }
    const data = await apiGet("/calculate-rate?" + q.toString());
    $("#out").textContent = JSON.stringify(data, null, 2);
  }catch(e){
    $("#out").textContent = e.message;
  }
}

function adminPanelHtml(){
  return `
    <div class="btns">
      <button class="secondary" id="btnListReq">List Requests</button>
    </div>
    <hr />
    <div class="field">
      <label>Approve Username</label>
      <input id="admUser" placeholder="e.g. broker_tester" />
    </div>
    <div class="field">
      <label>MC Number</label>
      <input id="admMC" placeholder="e.g. 001864" />
    </div>
    <div class="field">
      <label>Role</label>
      <select id="admRole">
        <option value="broker">broker</option>
        <option value="broker_carrier">broker_carrier</option>
      </select>
    </div>
    <div class="btns">
      <button id="btnApprove">Approve Broker</button>
      <button class="danger" id="btnReject">Reject Broker</button>
    </div>
    <hr />
    <div id="reqTable"></div>
  `;
}

function renderReqTable(rows){
  if(!Array.isArray(rows) || rows.length === 0){
    $("#reqTable").innerHTML = `<div class="muted">No requests.</div>`;
    return;
  }
  const html = `
    <table class="table">
      <thead>
        <tr><th>Username</th><th>Role</th><th>MC</th><th>Status</th></tr>
      </thead>
      <tbody>
        ${rows.map(r => `
          <tr>
            <td>${esc(r.username)}</td>
            <td>${esc(r.role)}</td>
            <td>${esc(r.mc_number)}</td>
            <td>${esc(r.broker_status)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  $("#reqTable").innerHTML = html;
}

function wireAdminButtons(){
  $("#btnListReq").onclick = async () => {
    try{
      const data = await apiGet("/admin/list-broker-requests");
      $("#out").textContent = JSON.stringify(data, null, 2);
      renderReqTable(data);
    }catch(e){
      $("#out").textContent = e.message;
    }
  };

  $("#btnApprove").onclick = async () => {
    try{
      const u = $("#admUser").value.trim();
      const mc = $("#admMC").value.trim();
      const r = $("#admRole").value;
      if(!u || !mc) throw new Error("username + mc_number required");
      const data = await apiGet(`/admin/approve-broker?username=${encodeURIComponent(u)}&mc_number=${encodeURIComponent(mc)}&role=${encodeURIComponent(r)}`);
      $("#out").textContent = JSON.stringify(data, null, 2);
    }catch(e){
      $("#out").textContent = e.message;
    }
  };

  $("#btnReject").onclick = async () => {
    try{
      const u = $("#admUser").value.trim();
      if(!u) throw new Error("username required");
      const data = await apiGet(`/admin/reject-broker?username=${encodeURIComponent(u)}`);
      $("#out").textContent = JSON.stringify(data, null, 2);
    }catch(e){
      $("#out").textContent = e.message;
    }
  };
}

function renderLoggedIn(user){
  const role = user.role;

  $("#leftCard").innerHTML = `
    <h2>Account</h2>
    <div class="muted">Logged in as <b>${esc(user.username)}</b>.</div>
    <hr />
    <div class="muted">Broker onboarding</div>
    <div class="field">
      <label>MC Number</label>
      <input id="mcIn" placeholder="e.g. 001864" value="${esc(user.mc_number || "")}" />
    </div>
    <div class="btns">
      <button id="btnOnboard">Submit MC / Verify</button>
    </div>
    <hr />
    <div class="muted">
      FMCSA is currently blocking (403) from your environment, so onboarding will go <b>pending</b>.
      Admin can approve for testing.
    </div>
  `;

  $("#rightCard").innerHTML = `
    <h2>Admin</h2>
    <div class="muted">Visible only if role = admin.</div>
    <hr />
    ${role === "admin" ? adminPanelHtml() : `<div class="muted">Not an admin.</div>`}
    <hr />
    <pre id="sysOut">Ready.</pre>
  `;

  $("#calcCard").innerHTML = `
    <h2>Rate Calculator</h2>
    <div class="muted">Uses current fuel surcharge + accessorials.</div>
    <hr />
    ${calcFormHtml()}
    <div class="btns">
      <button id="btnCalc">Calculate</button>
      <button class="secondary" id="btnFuel">Fuel Surcharge</button>
      <button class="secondary" id="btnVerifyToken">Verify Token</button>
      ${(role === "broker" || role === "broker_carrier") ? `<button class="secondary" id="btnVerifyBroker">Verify Broker (FMCSA)</button>` : ""}
    </div>
  `;

  $("#outCard").innerHTML = `
    <h2>Output</h2>
    <div class="muted">API responses show here.</div>
    <hr />
    <pre id="out">Ready.</pre>
  `;

  $("#btnOnboard").onclick = async () => {
    try{
      const mc = $("#mcIn").value.trim();
      if(!mc) throw new Error("MC number required");
      const data = await apiGet("/broker-onboard?mc_number=" + encodeURIComponent(mc));
      $("#out").textContent = JSON.stringify(data, null, 2);
      boot();
    }catch(e){
      $("#out").textContent = e.message;
    }
  };

  $("#btnCalc").onclick = doCalc;

  $("#btnFuel").onclick = async () => {
    try { $("#out").textContent = JSON.stringify(await apiGet("/fuel-surcharge"), null, 2); }
    catch(e){ $("#out").textContent = e.message; }
  };

  $("#btnVerifyToken").onclick = async () => {
    try { $("#out").textContent = JSON.stringify(await apiGet("/verify-token"), null, 2); }
    catch(e){ $("#out").textContent = e.message; }
  };

  const vb = document.getElementById("btnVerifyBroker");
  if(vb){
    vb.onclick = async () => {
      try { $("#out").textContent = JSON.stringify(await apiGet("/verify-broker"), null, 2); }
      catch(e){ $("#out").textContent = e.message; }
    };
  }

  if(role === "admin"){
    wireAdminButtons();
  }
}

async function boot(){
  let user = null;
  renderShell(null);

  const token = getToken();
  if(token){
    try{
      user = await apiGet("/verify-token");
    }catch(e){
      clearToken();
      user = null;
    }
  }

  renderShell(user);

  if(!user){
    renderAuth();
  }else{
    renderLoggedIn(user);
  }
}

boot();
