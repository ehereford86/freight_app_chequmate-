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
  .controls{display:grid;grid-template-columns:1fr 120px;gap:10px;width:100%;align-items:center;max-width:740px}
  input{
    width:100%;padding:10px 10px;border-radius:12px;border:1px solid var(--border);
    background:rgba(15,23,48,.9);color:var(--text);outline:none;
  }
  button{
    width:auto;
    padding:8px 12px;
    border-radius:12px;
    border:1px solid var(--border);
    background:rgba(77,210,255,.14);
    color:var(--text);
    outline:none;
    cursor:pointer;
  }
  button:hover{filter:brightness(1.05)}
  button:disabled{opacity:.45;cursor:not-allowed}
  .btn-ghost{background:rgba(255,255,255,.06)}
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
  .badge{
    padding:6px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.14);
    font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:.6px;
    background:rgba(77,255,136,.14);color:var(--ok);
  }
  .toast{
    position:fixed;right:14px;bottom:14px;background:rgba(15,23,48,.94);
    border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:10px 12px;
    max-width:520px;display:none;box-shadow:var(--shadow);z-index:40;
  }
  .modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;align-items:center;justify-content:center;z-index:30}
  .modal{
    width:min(860px, calc(100vw - 24px));
    background:rgba(18,26,51,.94);border:1px solid rgba(255,255,255,.14);
    border-radius:18px;box-shadow:var(--shadow);padding:14px;
    max-height:calc(100vh - 28px);
    overflow:auto;
  }
  .divider{height:1px;background:rgba(255,255,255,.08);margin:12px 0}
</style>
"""

COMMON_JS = r"""
<script>
  function esc(s){ if(s===null||s===undefined) return ""; return String(s); }
  function normalize(s){ return (s||"").toLowerCase(); }
  function toast(msg){
    const el=document.getElementById("toast");
    el.textContent=msg; el.style.display="block";
    setTimeout(()=>{ el.style.display="none"; }, 3200);
  }
  function token(){ return localStorage.getItem("token") || ""; }
  function username(){ return localStorage.getItem("username") || ""; }
  function setAuth(t,u){ if(t) localStorage.setItem("token", t); if(u) localStorage.setItem("username", u); }
  function clearAuth(){ localStorage.removeItem("token"); localStorage.removeItem("username"); }
  function authHeaders(){ const t=token(); return t ? {"Authorization":"Bearer "+t} : {}; }

  async function apiGET(path){
    const res = await fetch(path, { headers: { ...authHeaders() }});
    const j = await res.json().catch(()=>null);
    if(!res.ok) throw new Error(j?.detail || ("HTTP "+res.status));
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
      window.__BOOT && window.__BOOT();
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

DISPATCHER_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Dispatcher Board</title>
  """ + BASE_CSS + r"""
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div>
      <div class="title">Dispatcher Board</div>
      <div class="subtitle">Published loads only · first dispatcher to assign “claims” the load</div>
    </div>
    <div class="controls">
      <input id="q" placeholder="Search: ref, pickup, delivery, shipper, driver..." />
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
        <div class="title" style="font-size:16px;">Dispatcher Login</div>
      </div>
      <div class="right" style="min-width:340px;">
        <input id="login_user" placeholder="username (e.g. dispatcher1)"/>
        <input id="login_pass" placeholder="password" type="password"/>
        <button onclick="doLogin()">Login</button>
      </div>
    </div>
  </div>

  <div class="grid" id="grid"></div>
</div>

<div class="modal-backdrop" id="backdropAssign">
  <div class="modal">
    <div class="row">
      <div class="left">
        <h3 style="margin:0;">Assign Driver</h3>
        <div class="small muted" id="assignMeta"></div>
      </div>
      <div class="right">
        <button class="btn-ghost" onclick="closeAssign()">Close</button>
      </div>
    </div>
    <div class="divider"></div>
    <div class="kvs">
      <div class="kv" style="grid-column:1/-1;">
        <div class="k">Driver username</div>
        <input id="assign_driver_username" placeholder="driver1"/>
      </div>
    </div>
    <div style="height:12px;"></div>
    <div class="row">
      <div class="small muted">Calls POST /dispatcher/loads/{id}/assign-driver</div>
      <div class="right"><button class="btn-ghost" onclick="assignNow()">Assign</button></div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

""" + COMMON_JS + r"""
<script>
  let ALL = [];
  let ASSIGN_LOAD_ID = null;

  function countsChip(){
    document.getElementById("counts").innerHTML = `Published loads: <b>${ALL.length}</b>`;
  }

  function render(rows){
    const grid=document.getElementById("grid");
    if(!rows.length){
      grid.innerHTML = `<div class="card"><div class="muted">No published loads found (or you are not logged in).</div></div>`;
      return;
    }

    const myUser = normalize(username() || "");

    grid.innerHTML = rows.map(l=>{
      const owner = (l.dispatcher_username || "").trim();
      const ownerNorm = normalize(owner);
      const canAssign = (!owner) || (ownerNorm === myUser);

      const ownerChip = owner
        ? `<span class="chip">Dispatcher: <b>${esc(owner)}</b></span>`
        : `<span class="chip">Dispatcher: <b>Unclaimed</b></span>`;

      const btnText = owner ? "Assign Driver" : "Claim & Assign";
      const disabledAttr = canAssign ? "" : "disabled";

      return `
      <div class="card">
        <div class="row">
          <div class="left">
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
              <span class="badge">published</span>
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
              ${ownerChip}
              <span class="chip">Driver: <b>${esc(l.driver_username||"—")}</b></span>
              <span class="chip">Pay: <b>${fmtMoney(l.driver_pay)}</b></span>
              <span class="chip">Fuel: <b>${fmtMoney(l.fuel_surcharge)}</b></span>
              ${(!canAssign && owner) ? `<span class="chip">Locked: <b>${esc(owner)}</b> owns it</span>` : ``}
            </div>
          </div>

          <div class="right">
            <button class="btn-ghost" onclick="openAssign(${l.id}, '${esc(owner)}')" ${disabledAttr}>${btnText}</button>
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
        const hay=[l.shipper_name,l.customer_ref,l.pickup_address,l.delivery_address,l.driver_username,l.status,l.dispatcher_username]
          .map(x=>normalize(esc(x))).join(" | ");
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
      const j = await apiGET("/dispatcher/loads");
      ALL = j.loads || [];
      countsChip();
      applyFilters();
    }catch(e){
      toast("Failed to load dispatcher loads: "+e.message);
    }
  }

  function openAssign(load_id, owner){
    const myUser = normalize(username() || "");
    const ownerNorm = normalize(owner || "");
    if(owner && ownerNorm !== myUser){
      toast(`Locked: dispatcher '${owner}' owns this load`);
      return;
    }

    ASSIGN_LOAD_ID = load_id;
    const note = owner ? `Owned by <b>${esc(owner)}</b>` : `Unclaimed — assigning will claim it to <b>${esc(username()||"you")}</b>`;
    document.getElementById("assignMeta").innerHTML = `Load #<b>${load_id}</b> · ${note}`;
    document.getElementById("assign_driver_username").value = "driver1";
    document.getElementById("backdropAssign").style.display="flex";
  }

  function closeAssign(){
    ASSIGN_LOAD_ID=null;
    document.getElementById("backdropAssign").style.display="none";
  }

  async function assignNow(){
    if(!ASSIGN_LOAD_ID) return;
    try{
      const driver_username = (document.getElementById("assign_driver_username").value||"").trim();
      if(!driver_username){ toast("Enter driver username"); return; }
      await apiPOST(`/dispatcher/loads/${ASSIGN_LOAD_ID}/assign-driver`, { driver_username });
      toast("Assigned");
      closeAssign();
      await refreshLoads();
    }catch(e){
      toast("Assign failed: "+e.message);
    }
  }

  // Modal exits: click backdrop + ESC
  function hookModalExit(backdropId, closeFn){
    const bd = document.getElementById(backdropId);
    bd.addEventListener("click", (e)=>{
      if(e.target === bd) closeFn();
    });
  }

  document.addEventListener("keydown", (e)=>{
    if(e.key === "Escape"){
      if(document.getElementById("backdropAssign").style.display === "flex") closeAssign();
    }
  });

  hookModalExit("backdropAssign", closeAssign);

  window.__BOOT = function(){ refreshLoads(); };

  document.getElementById("refreshBtn").addEventListener("click", refreshLoads);
  document.getElementById("q").addEventListener("input", applyFilters);

  showLoginIfNeeded();
  refreshLoads();
</script>
</body>
</html>
"""

@router.get("/dispatcher-ui", response_class=HTMLResponse)
def dispatcher_ui():
    return DISPATCHER_HTML
