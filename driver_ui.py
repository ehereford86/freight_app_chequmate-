from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

BASE_CSS = r"""
<style>
  :root{
    --bg:#0b1020;--panel:#121a33;--panel2:#0f1730;--text:#e8eeff;--muted:#a8b3d6;
    --border:rgba(255,255,255,.10);--danger:#ff4d4d;--ok:#4dff88;--warn:#ffd24d;--info:#4dd2ff;
    --chip:rgba(255,255,255,.08);--shadow:0 12px 30px rgba(0,0,0,.35);--radius:14px;
    --mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace;
    --sans:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,"Apple Color Emoji","Segoe UI Emoji";
  }
  body{
    margin:0;
    background: radial-gradient(1200px 600px at 20% 0%, rgba(77,210,255,0.12), transparent 55%),
                radial-gradient(900px 500px at 90% 10%, rgba(255,210,77,0.10), transparent 55%),
                var(--bg);
    color:var(--text);
    font-family:var(--sans);
  }
  .wrap{max-width:1100px;margin:0 auto;padding:22px 16px 60px}
  .topbar{
    display:flex;gap:12px;align-items:center;justify-content:space-between;
    padding:14px 14px;background:rgba(18,26,51,.78);
    border:1px solid var(--border);border-radius:var(--radius);
    box-shadow:var(--shadow);backdrop-filter:blur(10px);
    position:sticky;top:12px;z-index:20;
  }
  .title{font-weight:800;letter-spacing:.3px}
  .subtitle{color:var(--muted);font-size:13px}
  .controls{display:grid;grid-template-columns:1fr auto;gap:10px;width:100%;max-width:520px;align-items:center}

  /* Inputs should fill their container. Buttons should NOT. */
  input,textarea,select{
    width:100%;
    padding:10px 10px;
    border-radius:12px;
    border:1px solid var(--border);
    background:rgba(15,23,48,.9);
    color:var(--text);
    outline:none;
    box-sizing:border-box;
  }
  textarea{min-height:110px;resize:vertical}

  button{
    width:auto;
    padding:8px 10px;
    border-radius:10px;
    border:1px solid var(--border);
    background:rgba(77,210,255,.14);
    color:var(--text);
    cursor:pointer;
    font-size:13px;
    line-height:1.1;
    box-sizing:border-box;
  }
  button:hover{filter:brightness(1.05)}
  button:disabled{opacity:.45;cursor:not-allowed}

  .btn-ghost{background:rgba(255,255,255,.06)}
  .btn-danger{background:rgba(255,77,77,.12);border-color:rgba(255,77,77,.30)}
  .btn-ok{background:rgba(77,255,136,.12);border-color:rgba(77,255,136,.28)}

  .grid{margin-top:14px;display:grid;gap:12px}
  .card{
    background:rgba(18,26,51,.76);border:1px solid var(--border);
    border-radius:var(--radius);box-shadow:var(--shadow);padding:14px;
  }
  .row{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
  .left{flex:1;min-width:0}
  .right{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
  .kvs{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
  .kv{
    background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);
    border-radius:12px;padding:10px;min-height:52px;
  }
  .k{color:var(--muted);font-size:12px;margin-bottom:4px}
  .v{font-size:14px;white-space:pre-wrap;overflow-wrap:anywhere}
  .mono{font-family:var(--mono);font-size:12px}
  .chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  .chip{
    padding:6px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.10);
    background:var(--chip);font-size:12px;color:var(--muted);
  }
  .divider{height:1px;background:rgba(255,255,255,.08);margin:12px 0}
  .toast{
    position:fixed;right:14px;bottom:14px;background:rgba(15,23,48,.94);
    border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:10px 12px;
    max-width:520px;display:none;box-shadow:var(--shadow);z-index:40;
  }
  details{border:1px solid rgba(255,255,255,.10);border-radius:12px;padding:10px;background:rgba(255,255,255,.04)}
  summary{cursor:pointer;color:var(--muted);font-weight:700}
  pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:10px 0 0;font-family:var(--mono);font-size:12px}

  .actions{
    display:flex;
    gap:8px;
    align-items:center;
    flex-wrap:wrap;
    margin-top:10px;
  }
  .actions select{width:auto;min-width:170px}
</style>
"""

COMMON_JS = r"""
<script>
  function esc(s){ if(s===null||s===undefined) return ""; return String(s); }
  function normalize(s){ return (s||"").toLowerCase(); }
  function toast(msg){
    const el=document.getElementById("toast");
    el.textContent=msg;
    el.style.display="block";
    setTimeout(()=>{ el.style.display="none"; }, 3200);
  }
  function token(){ return localStorage.getItem("token") || ""; }
  function username(){ return localStorage.getItem("username") || ""; }
  function setAuth(t,u){
    if(t) localStorage.setItem("token", t);
    if(u) localStorage.setItem("username", u);
  }
  function clearAuth(){
    localStorage.removeItem("token");
    localStorage.removeItem("username");
  }
  function authHeaders(){
    const t=token();
    return t ? {"Authorization":"Bearer "+t} : {};
  }
  async function apiGET(path){
    const res = await fetch(path, { headers: { ...authHeaders() }});
    const j = await res.json().catch(()=>null);
    if(!res.ok) throw new Error
    throw new Error(j?.detail || ("HTTP "+res.status));
    return j;
  }
  async function apiPOST(path, body){
    const res = await fetch(path, {
      method:"POST",
      headers:{ "Content-Type":"application/json", ...authHeaders() },
      body: JSON.stringify(body || {})
    });
    const j = await res.json().catch(()=>null);
    if(!res.ok) throw new Error(j?.detail || ("HTTP "+res.status));
    return j;
  }
  async function doLogin(){
    const u = (document.getElementById("login_user").value || "").trim();
    const p = (document.getElementById("login_pass").value || "").trim();
    if(!u || !p){ toast("Enter username + password"); return; }

    try{
      const res = await fetch("/login", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ username:u, password:p })
      });
      const j = await res.json().catch(()=>null);
      if(!res.ok) throw new Error(j?.detail || "Login failed");
      if(!j || !j.token) throw new Error("Login did not return token");
      setAuth(j.token, u);

      document.getElementById("authChip").innerHTML =
        `Logged in as <b>${esc(u)}</b>`;

      document.getElementById("loginPanel").style.display = "none";
      toast("Logged in");
      window.__DRIVER_BOOT && window.__DRIVER_BOOT();
    }catch(e){
      toast("Login failed: " + e.message);
    }
  }
  function showLoginIfNeeded(){
    const t = token();
    const u = username();
    document.getElementById("authChip").innerHTML =
      t ? `Logged in as <b>${esc(u||"(unknown)")}</b>` : `Not logged in`;
    document.getElementById("loginPanel").style.display = t ? "none" : "block";
  }
  function fmtMoney(v){
    if(v===null||v===undefined||v==="") return "—";
    const n = Number(v);
    if(!isFinite(n)) return "—";
    return "$" + n.toFixed(2);
  }
</script>
"""

HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Driver Loads</title>
  """ + BASE_CSS + r"""
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div>
      <div class="title">Driver Loads</div>
      <div class="subtitle">Assigned loads + driver pay calculator (ZIP-to-ZIP or Actual miles)</div>
    </div>
    <div class="controls">
      <input id="q" placeholder="Search: shipper, ref, pickup, delivery, status..." />
      <button id="refreshBtn" class="btn-ghost">Refresh</button>
    </div>
  </div>

  <div class="chips" style="margin-top:12px;">
    <span class="chip" id="counts">Loading...</span>
    <span class="chip" id="authChip">Not logged in</span>
    <button class="btn-ghost" onclick="clearAuth(); location.reload()">Logout</button>
  </div>

  <div id="loginPanel" class="card" style="margin-top:12px; display:none;">
    <div class="row">
      <div class="left">
        <div class="title" style="font-size:16px;">Driver Login</div>
        <div class="muted small">Login stores token + username in localStorage.</div>
      </div>
      <div class="right" style="min-width:340px;">
        <input id="login_user" placeholder="username (e.g. driver1)"/>
        <input id="login_pass" placeholder="password" type="password"/>
        <button onclick="doLogin()">Login</button>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:12px;">
    <div class="row">
      <div class="left">
        <div class="title" style="font-size:16px;">Driver Pay Calculator</div>
        <div class="muted small">Uses ORS (zip-to-zip routing) if you don’t provide actual miles.</div>
      </div>
      <div class="right">
        <button class="btn-ghost" id="clearCalcBtn">Clear</button>
      </div>
    </div>
    <div class="divider"></div>

    <div class="kvs">
      <div class="kv"><div class="k">Origin ZIP</div><input id="origin_zip" placeholder="75201"/></div>
      <div class="kv"><div class="k">Dest ZIP</div><input id="dest_zip" placeholder="77002"/></div>

      <div class="kv"><div class="k">Actual Miles (optional)</div><input id="actual_miles" placeholder="0"/></div>
      <div class="kv"><div class="k">CPM ($/mile)</div><input id="cpm" placeholder="0.60"/></div>

      <div class="kv"><div class="k">Lumper</div><input id="lumper" placeholder="0"/></div>
      <div class="kv"><div class="k">Breakdown Fee</div><input id="breakdown_fee" placeholder="0"/></div>

      <div class="kv"><div class="k">Detention Hours</div><input id="detention_hours" placeholder="0"/></div>
      <div class="kv"><div class="k">Detention $/hour</div><input id="detention_rate" placeholder="0"/></div>

      <div class="kv"><div class="k">Layover Days</div><input id="layover_days" placeholder="0"/></div>
      <div class="kv"><div class="k">Layover $/day</div><input id="layover_per_day" placeholder="0"/></div>
    </div>

    <div style="height:10px;"></div>
    <div class="row">
      <div class="small muted">If “Actual Miles” is > 0, we use it. Otherwise we route ZIP-to-ZIP.</div>
      <div class="right"><button id="runCalcBtn">Calculate</button></div>
    </div>

    <div style="height:10px;"></div>
    <div id="calcOut"></div>
  </div>

  <div class="grid" id="grid"></div>
</div>

<div class="toast" id="toast"></div>

""" + COMMON_JS + r"""
<script>
  let ALL = [];

  const STATUS_OPTIONS = [
    { value:"accepted", label:"Accepted" },
    { value:"at_pickup", label:"At Pickup" },
    { value:"loaded", label:"Loaded" },
    { value:"in_transit", label:"In Transit" },
    { value:"at_delivery", label:"At Delivery" },
    { value:"delivered", label:"Delivered" }
  ];

  function countsChip(){
    document.getElementById("counts").innerHTML = `Assigned loads: <b>${ALL.length}</b>`;
  }

  function statusSelectHTML(load){
    const cur = String(load.status || "").toLowerCase();
    const opts = STATUS_OPTIONS.map(o=>{
      const sel = (o.value === cur) ? "selected" : "";
      return `<option value="${esc(o.value)}" ${sel}>${esc(o.label)}</option>`;
    }).join("");
    return `
      <select id="status_sel_${load.id}">
        ${opts}
      </select>
    `;
  }

  function render(rows){
    const grid=document.getElementById("grid");
    if(!rows.length){
      grid.innerHTML=`<div class="card"><div class="muted">No assigned loads found (or you are not logged in).</div></div>`;
      return;
    }
    grid.innerHTML = rows.map(l=>{
      const s = String(l.status || "").toLowerCase();
      const showAccept = (s === "assigned");

      return `
      <div class="card">
        <div class="row">
          <div class="left">
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
              <div class="mono">Load #${l.id}</div>
              ${l.customer_ref ? `<div class="chip">Ref: <b>${esc(l.customer_ref)}</b></div>`:""}
              <div class="chip">Status: <b>${esc(l.status||"—")}</b></div>
            </div>

            <div class="kvs">
              <div class="kv">
                <div class="k">Pickup</div>
                <div class="v">${esc(l.pickup_address||"—")}</div>
                ${l.pickup_appt ? `<div class="muted small">Appt: ${esc(l.pickup_appt)}</div>`:""}
              </div>
              <div class="kv">
                <div class="k">Delivery</div>
                <div class="v">${esc(l.delivery_address||"—")}</div>
                ${l.delivery_appt ? `<div class="muted small">Appt: ${esc(l.delivery_appt)}</div>`:""}
              </div>
            </div>

            <div class="chips">
              ${l.shipper_name ? `<span class="chip">Shipper: <b>${esc(l.shipper_name)}</b></span>`:""}
              <span class="chip">Dispatcher: <b>${esc(l.dispatcher_username||"—")}</b></span>
              <span class="chip">Driver Pay: <b>${fmtMoney(l.ratecon_limited?.driver_pay)}</b></span>
              <span class="chip">Fuel: <b>${fmtMoney(l.ratecon_limited?.fuel_surcharge)}</b></span>
            </div>

            <div class="actions">
              ${showAccept ? `<button class="btn-ok" onclick="acceptLoad(${l.id})">Accept</button>` : ""}
              <span class="chip">Update status:</span>
              ${statusSelectHTML(l)}
              <button class="btn-ghost" onclick="updateStatus(${l.id})">Update</button>
            </div>

          </div>
        </div>
      </div>`;
    }).join("");
  }

  function applyFilters(){
    const q=normalize((document.getElementById("q").value||"").trim());
    let rows=ALL.slice();
    if(q){
      rows=rows.filter(l=>{
        const hay=[
          l.shipper_name,l.customer_ref,l.pickup_address,l.delivery_address,l.status
        ].map(x=>normalize(esc(x))).join(" | ");
        return hay.includes(q);
      });
    }
    render(rows);
  }

  async function refreshLoads(){
    showLoginIfNeeded();
    if(!token()){
      ALL=[];
      countsChip();
      render([]);
      return;
    }
    try{
      const j = await apiGET("/driver/loads");
      ALL = j.loads || [];
      countsChip();
      applyFilters();
    }catch(e){
      toast("Failed to load driver loads: "+e.message);
    }
  }

  async function acceptLoad(load_id){
    try{
      await apiPOST(`/driver/loads/${load_id}/accept`, {});
      toast("Accepted");
      await refreshLoads();
    }catch(e){
      toast("Accept failed: " + e.message);
    }
  }

  async function updateStatus(load_id){
    try{
      const el = document.getElementById(`status_sel_${load_id}`);
      const status = (el?.value || "").trim();
      if(!status){ toast("Pick a status"); return; }
      await apiPOST(`/driver/loads/${load_id}/status`, { status });
      toast("Status updated");
      await refreshLoads();
    }catch(e){
      toast("Status update failed: " + e.message);
    }
  }

  async function runCalc(){
    try{
      const cpm = Number(document.getElementById("cpm").value||0);
      const actual_miles = Number(document.getElementById("actual_miles").value||0);

      const body = {
        origin_zip: (document.getElementById("origin_zip").value||"").trim(),
        dest_zip: (document.getElementById("dest_zip").value||"").trim(),
        country: "US",
        actual_miles: actual_miles,
        use_actual_miles: (actual_miles > 0),
        cpm: cpm,
        lumper: Number(document.getElementById("lumper").value||0),
        breakdown_fee: Number(document.getElementById("breakdown_fee").value||0),
        detention_hours: Number(document.getElementById("detention_hours").value||0),
        detention_rate_per_hour: Number(document.getElementById("detention_rate").value||0),
        layover_days: Number(document.getElementById("layover_days").value||0),
        layover_per_day: Number(document.getElementById("layover_per_day").value||0)
      };

      const j = await apiPOST("/driver/pay-calc", body);

      const milesUsed = j?.miles?.miles_used;
      const milesSource = j?.miles?.source;
      const b = j?.breakdown || {};

      document.getElementById("calcOut").innerHTML = `
        <div class="card" style="margin-top:10px;">
          <div class="row">
            <div class="left">
              <div class="title" style="font-size:16px;">Pay Result</div>
              <div class="muted small">Miles source: <b>${esc(milesSource)}</b> — Miles used: <b>${esc(milesUsed)}</b></div>
            </div>
          </div>
          <div class="divider"></div>
          <div class="kvs">
            <div class="kv"><div class="k">Linehaul</div><div class="v"><b>${fmtMoney(b.linehaul)}</b></div></div>
            <div class="kv"><div class="k">Detention</div><div class="v"><b>${fmtMoney(b.detention)}</b></div></div>
            <div class="kv"><div class="k">Layover</div><div class="v"><b>${fmtMoney(b.layover)}</b></div></div>
            <div class="kv"><div class="k">Lumper</div><div class="v"><b>${fmtMoney(b.lumper)}</b></div></div>
            <div class="kv"><div class="k">Breakdown Fee</div><div class="v"><b>${fmtMoney(b.breakdown_fee)}</b></div></div>
            <div class="kv"><div class="k">Total Pay</div><div class="v"><b>${fmtMoney(b.total_pay)}</b></div></div>
          </div>

          <div style="margin-top:10px;">
            <details>
              <summary>Raw JSON</summary>
              <pre>${esc(JSON.stringify(j, null, 2))}</pre>
            </details>
          </div>
        </div>
      `;
      toast("Calculated");
    }catch(e){
      toast("Calc failed: " + e.message);
    }
  }

  window.__DRIVER_BOOT = function(){ refreshLoads(); };

  document.getElementById("refreshBtn").addEventListener("click", refreshLoads);
  document.getElementById("q").addEventListener("input", applyFilters);
  document.getElementById("runCalcBtn").addEventListener("click", runCalc);
  document.getElementById("clearCalcBtn").addEventListener("click", ()=>{ document.getElementById("calcOut").innerHTML=""; });

  showLoginIfNeeded();
  refreshLoads();
</script>
</body>
</html>
"""

@router.get("/driver-ui", response_class=HTMLResponse)
def driver_ui():
    return HTML
