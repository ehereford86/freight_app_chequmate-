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
  .controls{display:grid;grid-template-columns:160px 1fr 160px 120px;gap:10px;width:100%;align-items:center;max-width:740px}
  select,input,textarea{
    width:100%;padding:10px 10px;border-radius:12px;border:1px solid var(--border);
    background:rgba(15,23,48,.9);color:var(--text);outline:none;
    box-sizing:border-box;
  }
  textarea{min-height:110px;resize:vertical}
  button{
    width:auto;
    padding:8px 12px;
    border-radius:12px;
    border:1px solid var(--border);
    background:rgba(77,210,255,.14);
    color:var(--text);
    outline:none;
    cursor:pointer;
    white-space:nowrap;
    box-sizing:border-box;
  }
  button:hover{filter:brightness(1.05)}
  button:disabled{opacity:.45;cursor:not-allowed}
  .btn-danger{background:rgba(255,77,77,.16)}
  .btn-ghost{background:rgba(255,255,255,.06)}
  .btn-ok{background:rgba(77,255,136,.14);border-color:rgba(77,255,136,.25)}
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
  .chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center}
  .chip{
    padding:6px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.10);
    background:var(--chip);font-size:12px;color:var(--muted);
  }
  .badge{
    padding:6px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.14);
    font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:.6px
  }
  .b-pending{background:rgba(255,210,77,.14);color:var(--warn)}
  .b-published{background:rgba(77,255,136,.14);color:var(--ok)}
  .b-pulled{background:rgba(255,77,77,.12);color:var(--danger)}
  .muted{color:var(--muted)}
  .small{font-size:12px}
  .divider{height:1px;background:rgba(255,255,255,.08);margin:12px 0}
  .toast{
    position:fixed;right:14px;bottom:14px;background:rgba(15,23,48,.94);
    border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:10px 12px;
    max-width:520px;display:none;box-shadow:var(--shadow);z-index:60;
  }

  .formgrid{
    display:grid;
    grid-template-columns:repeat(4, minmax(0, 1fr));
    gap:10px;
  }
  .formgrid .full{grid-column:1/-1}

  .section-title{
    font-weight:800;
    letter-spacing:.2px;
    margin:0;
  }

  details{
    border:1px solid rgba(255,255,255,.10);
    border-radius:12px;
    padding:10px;
    background:rgba(255,255,255,.04);
  }
  summary{cursor:pointer;color:var(--muted);font-weight:800}
</style>
"""

COMMON_JS = r"""
<script>
  const SHOW_BILLING_UI = false;

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
  function fmtPct(v){
    if(v===null||v===undefined||v==="") return "—";
    const n = Number(v);
    if(!isFinite(n)) return "—";
    const pct = (Math.abs(n) <= 1.0) ? (n*100.0) : n;
    return pct.toFixed(2) + "%";
  }

  function titleCaseWords(s){
    return String(s||"")
      .replace(/[_\.]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .split(" ")
      .map(w => w ? (w[0].toUpperCase() + w.slice(1)) : "")
      .join(" ");
  }

  function prettyLabel(key){
    const k = String(key||"").trim();
    const special = {
      "diesel_price": "Diesel Price",
      "period": "Fuel Week (Period)",
      "series_id": "EIA Series",
      "fuel_source": "Fuel Source",
      "mpg": "MPG",
      "fuel_total": "Fuel Total",
      "fuel_per_mile": "Fuel Per Mile",
      "fuel_surcharge_per_mile": "Fuel Surcharge Per Mile",
      "carrier_cost_per_total_mile": "Carrier Cost Per Total Mile",
      "carrier_margin_pct": "Carrier Margin",
      "broker_margin_pct": "Broker Margin",
      "dispatch_pct": "Dispatch Percentage",
      "detention_per_hour": "Detention Per Hour",
      "driver_reason_threshold": "Driver Reason Threshold",
      "broker_rate": "Broker Rate (All-In)",
      "all_in": "All-In",
      "linehaul": "Linehaul",
      "driver_pay": "Driver Pay",
      "fuel_surcharge": "Fuel Surcharge",
      "carrier_total": "Carrier Total",
      "carrier_cost_est": "Carrier Cost Estimate",
      "dispatcher_cut": "Dispatcher Cut",
      "broker_profit": "Broker Profit",
      "broker_margin": "Broker Margin"
    };

    const stripped = k
      .replace(/^market_assumptions\./, "")
      .replace(/^policy_defaults\./, "")
      .replace(/^selected\./, "")
      .replace(/^breakdown\./, "")
      .replace(/^fuel\./, "");

    if(special[stripped]) return special[stripped];
    return titleCaseWords(stripped);
  }

  function isMoneyKey(key){
    const k = String(key||"").toLowerCase();
    return k.includes("price") || k.includes("total") || k.includes("cost") || k.includes("pay") || k.includes("profit") || k.includes("surcharge") || k.includes("fee") || k.includes("linehaul") || k.includes("rate");
  }
  function isPctKey(key){
    const k = String(key||"").toLowerCase();
    return k.includes("pct") || k.includes("margin") || k.includes("percentage") || k.endsWith("_pct");
  }
  function fmtValueByKey(key, val){
    if(val===null || val===undefined || val==="") return "—";
    if(typeof val === "boolean") return val ? "true" : "false";
    if(typeof val === "number"){
      if(isPctKey(key)) return fmtPct(val);
      if(isMoneyKey(key)) return fmtMoney(val);
      return String(val);
    }
    const n = Number(val);
    if(isFinite(n) && String(val).trim() !== ""){
      if(isPctKey(key)) return fmtPct(n);
      if(isMoneyKey(key)) return fmtMoney(n);
      return String(n);
    }
    return esc(val);
  }
</script>
"""

BROKER_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Broker Loads</title>
  """ + BASE_CSS + r"""
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div>
      <div class="title">Broker Loads</div>
    </div>
    <div class="controls">
      <select id="visFilter">
        <option value="all">All</option>
        <option value="pending">Pending</option>
        <option value="published">Published</option>
        <option value="pulled">Pulled</option>
      </select>
      <input id="q" placeholder="Search: shipper, ref, pickup, delivery, dispatcher, driver..." />
      <select id="mineFilter">
        <option value="all">All loads</option>
        <option value="mine">Created by me</option>
      </select>
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
        <div class="title" style="font-size:16px;">Broker Login</div>
      </div>
      <div class="right" style="min-width:340px;">
        <input id="login_user" placeholder="username (e.g. broker3)"/>
        <input id="login_pass" placeholder="password" type="password"/>
        <button onclick="doLogin()">Login</button>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:12px;">
    <div class="row">
      <div class="left">
        <div class="title" style="font-size:16px;">Create Pending Load</div>
      </div>
    </div>
    <div class="divider"></div>
    <div class="kvs">
      <div class="kv"><div class="k">Shipper Name</div><input id="c_shipper_name" placeholder="Test Shipper"/></div>
      <div class="kv"><div class="k">Customer Ref</div><input id="c_customer_ref" placeholder="PO-1234"/></div>
      <div class="kv"><div class="k">Pickup Address</div><input id="c_pickup_address" placeholder="123 Start St, Dallas, TX 75201"/></div>
      <div class="kv"><div class="k">Pickup Appt</div><input id="c_pickup_appt" placeholder="YYYY-MM-DD HH:MM"/></div>
      <div class="kv"><div class="k">Delivery Address</div><input id="c_delivery_address" placeholder="789 End Ave, Houston, TX 77002"/></div>
      <div class="kv"><div class="k">Delivery Appt</div><input id="c_delivery_appt" placeholder="YYYY-MM-DD HH:MM"/></div>
      <div class="kv"><div class="k">Dispatcher Username (optional)</div><input id="c_dispatcher_username" placeholder="dispatcher1"/></div>
      <div class="kv"><div class="k">Initial Driver Pay</div><input id="c_driver_pay" placeholder="0.00"/></div>
      <div class="kv"><div class="k">Initial Fuel Surcharge</div><input id="c_fuel_surcharge" placeholder="0.00"/></div>
      <div class="kv" style="grid-column:1/-1;">
        <div class="k">Ratecon Terms (clean document)</div>
        <textarea id="c_ratecon_terms" placeholder="Carrier-facing terms only."></textarea>
      </div>
    </div>
    <div style="height:10px;"></div>
    <div class="row">
      <div class="right">
        <button id="createBtn">Create Pending Load</button>
      </div>
    </div>
  </div>

  <!-- Broker Negotiation Calculator (collapsed by default) -->
  <div class="card" style="margin-top:12px;">
    <details id="negCalc">
      <summary>Negotiation Calculator</summary>

      <div style="height:12px;"></div>

      <div class="row">
        <div class="left">
          <div class="muted small">Calculate and optionally apply driver pay + fuel surcharge to a selected load.</div>
        </div>
        <div class="right">
          <button class="btn-ghost" onclick="openHistory()">History</button>
          <button class="btn-ghost" onclick="clearNegotiate()">Clear</button>
        </div>
      </div>

      <div class="divider"></div>

      <div class="formgrid">
        <div class="full">
          <div class="muted small">Load</div>
          <select id="n_load_id"></select>
        </div>

        <div>
          <div class="muted small">Apply to load?</div>
          <select id="n_apply">
            <option value="false">false (calculate only)</option>
            <option value="true">true (apply driver_pay + fuel_surcharge)</option>
          </select>
        </div>

        <div>
          <div class="muted small">Fuel pricing</div>
          <select id="n_fuel_mode">
            <option value="national">national (EIA US avg)</option>
            <option value="origin_state">origin state (requires mapping)</option>
          </select>
        </div>

        <div>
          <div class="muted small">Auto miles</div>
          <button class="btn-ghost" style="width:100%;" onclick="autoMiles()">Auto Miles (route + buffer)</button>
        </div>

        <div>
          <div class="muted small">Loaded miles</div>
          <input id="n_loaded_miles" placeholder="239"/>
        </div>

        <div>
          <div class="muted small">Total miles</div>
          <input id="n_total_miles" placeholder="260"/>
        </div>

        <div>
          <div class="muted small">Driver CPM (loaded miles)</div>
          <input id="n_driver_cpm" placeholder="4.25"/>
        </div>

        <div class="full">
          <div class="muted small">Auto miles info</div>
          <div class="chip" id="autoMilesInfo">Not routed yet</div>
        </div>

        <div class="full">
          <div class="muted small">Override reason (optional)</div>
          <input id="n_override_reason" placeholder="Reason if pushing beyond thresholds"/>
        </div>

        <div class="full">
          <div class="muted small">Accessorials (optional)</div>
          <div class="formgrid" style="grid-template-columns:160px 1fr 140px 120px;">
            <select id="a_type">
              <option value="lumper">Lumper</option>
              <option value="tarp">Tarp</option>
              <option value="accessories">Accessories</option>
              <option value="breakdown">Breakdown</option>
              <option value="detention">Detention (hours)</option>
              <option value="layover">Layover (days)</option>
            </select>
            <input id="a_note" placeholder="Note (optional)"/>
            <input id="a_qty" placeholder="Qty (hours/days)" />
            <input id="a_amt" placeholder="$ Amount" />
          </div>
          <div style="height:8px;"></div>
          <div class="row">
            <div class="right"><button class="btn-ghost" onclick="addAccessorial()">Add Item</button></div>
          </div>

          <div id="a_list" style="margin-top:10px;"></div>
        </div>

        <div class="full">
          <button onclick="runNegotiate()">Run Calculator</button>
        </div>
      </div>

      <div style="height:12px;"></div>
      <div class="muted small">Result (clean)</div>
      <div id="negCleanOut" style="margin-top:10px;"></div>
    </details>
  </div>

  <div class="grid" id="grid"></div>
</div>

<div class="toast" id="toast"></div>

""" + COMMON_JS + r"""
<script>
  function badge(visibility){
    const v=(visibility||"").toLowerCase();
    if(v==="pending") return `<span class="badge b-pending">pending</span>`;
    if(v==="pulled") return `<span class="badge b-pulled">pulled</span>`;
    return `<span class="badge b-published">published</span>`;
  }

  let ALL = [];
  let ACCESSORIALS = [];
  let ROUTE_META = { origin_state: null };

  function countsChip(){
    const c={pending:0,published:0,pulled:0};
    for(const l of ALL){
      const v=normalize(l.visibility);
      if(v==="pending") c.pending++;
      else if(v==="pulled") c.pulled++;
      else c.published++;
    }
    document.getElementById("counts").innerHTML =
      `Total <b>${ALL.length}</b> — Pending <b>${c.pending}</b> · Published <b>${c.published}</b> · Pulled <b>${c.pulled}</b>`;
  }

  function applyFilters(){
    const vis=document.getElementById("visFilter").value;
    const mine=document.getElementById("mineFilter").value;
    const q=normalize((document.getElementById("q").value||"").trim());
    const myUser=normalize(localStorage.getItem("username")||"");

    let rows=ALL.slice();
    if(vis!=="all") rows=rows.filter(l=>normalize(l.visibility)===vis);
    if(mine==="mine" && myUser) rows=rows.filter(l=>normalize(l.created_by)===myUser);
    if(q){
      rows=rows.filter(l=>{
        const hay=[
          l.shipper_name,l.customer_ref,l.pickup_address,l.delivery_address,
          l.dispatcher_username,l.driver_username,l.status,l.visibility
        ].map(x=>normalize(esc(x))).join(" | ");
        return hay.includes(q);
      });
    }
    render(rows);
  }

  function render(rows){
    const grid=document.getElementById("grid");
    if(!rows.length){
      grid.innerHTML=`<div class="card"><div class="muted">No loads match your filters.</div></div>`;
      return;
    }
    grid.innerHTML = rows.map(l=>{
      const v=normalize(l.visibility);
      const canEdit = (v==="pending");
      const terms = esc(l.ratecon_terms);
      const preview = terms ? terms.slice(0,220)+(terms.length>220?"…":"") : "(none)";

      const billingChips = (!SHOW_BILLING_UI) ? "" : `
        ${l.invoice_number ? `<span class="chip">Invoice #: <b>${esc(l.invoice_number)}</b></span>` : ""}
        ${l.paid_at ? `<span class="chip">Paid: <b>${esc(l.paid_at)}</b></span>` : ""}
      `;

      return `
      <div class="card">
        <div class="row">
          <div class="left">
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
              ${badge(l.visibility)}
              <div class="mono">Load #${l.id}</div>
              <div class="chip">Status: <b>${esc(l.status||"")||"—"}</b></div>
              ${l.customer_ref ? `<div class="chip">Ref: <b>${esc(l.customer_ref)}</b></div>`:""}
              ${l.created_by ? `<div class="chip">Created: <b>${esc(l.created_by)}</b></div>`:""}
            </div>

            <div class="kvs">
              <div class="kv">
                <div class="k">Pickup</div>
                <div class="v">${esc(l.pickup_address||"")||"—"}</div>
                ${l.pickup_appt ? `<div class="muted small">Appt: ${esc(l.pickup_appt)}</div>`:""}
              </div>
              <div class="kv">
                <div class="k">Delivery</div>
                <div class="v">${esc(l.delivery_address||"")||"—"}</div>
                ${l.delivery_appt ? `<div class="muted small">Appt: ${esc(l.delivery_appt)}</div>`:""}
              </div>
            </div>

            <div class="chips">
              ${l.shipper_name ? `<span class="chip">Shipper: <b>${esc(l.shipper_name)}</b></span>`:""}
              <span class="chip">Dispatcher: <b>${esc(l.dispatcher_username||"—")}</b></span>
              <span class="chip">Driver: <b>${esc(l.driver_username||"—")}</b></span>
              <span class="chip">Driver Pay: <b>${fmtMoney(l.driver_pay)}</b></span>
              <span class="chip">Fuel: <b>${fmtMoney(l.fuel_surcharge)}</b></span>
              ${billingChips}
            </div>

            <div class="divider"></div>
            <div class="small muted"><b>Ratecon Terms</b> (preview)</div>
            <div class="mono" style="margin-top:6px;white-space:pre-wrap;">${esc(preview)}</div>
          </div>

          <div class="right">
            <button class="btn-ok" onclick="publishLoad(${l.id})" ${canEdit?"":"disabled"}>Publish</button>
            <button class="btn-danger" onclick="cancelLoad(${l.id})" ${canEdit?"":"disabled"}>Cancel</button>
            <button class="btn-danger" onclick="deleteLoad(${l.id})" ${canEdit?"":"disabled"}>Delete</button>
          </div>
        </div>
      </div>`;
    }).join("");
  }

  async function refreshLoads(){
    showLoginIfNeeded();
    if(!token()){
      ALL=[];
      countsChip();
      render([]);
      fillNegotiateLoads();
      return;
    }
    try{
      const j = await apiGET("/broker/loads");
      ALL = j.loads || [];
      countsChip();
      fillNegotiateLoads();
      applyFilters();
    }catch(e){
      toast("Failed to load broker loads: "+e.message);
    }
  }

  function fillNegotiateLoads(){
    const sel = document.getElementById("n_load_id");
    if(!sel) return;
    const current = sel.value;
    if(!ALL.length){
      sel.innerHTML = `<option value="">(no loads)</option>`;
      return;
    }
    const opts = [`<option value="">(select a load)</option>`].concat(
      ALL.map(l=>{
        const ref = l.customer_ref ? ` · ${esc(l.customer_ref)}` : "";
        const sh = l.shipper_name ? ` · ${esc(l.shipper_name)}` : "";
        return `<option value="${l.id}">#${l.id}${ref}${sh}</option>`;
      })
    );
    sel.innerHTML = opts.join("");
    if(current) sel.value = current;
  }

  async function publishLoad(id){
    try{
      const ok = confirm("Publish this load? Pending -> Published.");
      if(!ok) return;
      await apiPOST(`/broker/loads/${id}/publish`, {});
      toast("Published");
      await refreshLoads();
    }catch(e){
      toast("Publish failed: "+e.message);
    }
  }

  async function cancelLoad(id){
    try{
      const reason = prompt("Cancel reason?") || "Canceled by broker";
      await apiPOST(`/broker/loads/${id}/cancel`, { reason });
      toast("Canceled (pulled)");
      await refreshLoads();
    }catch(e){ toast("Cancel failed: "+e.message); }
  }

  async function deleteLoad(id){
    try{
      const ok = confirm("HARD DELETE this pending load? This will remove it from the DB.");
      if(!ok) return;
      await apiPOST(`/broker/loads/${id}/delete`, { reason: "Hard delete by broker" });
      toast("Deleted (hard)");
      await refreshLoads();
    }catch(e){ toast("Delete failed: "+e.message); }
  }

  function renderAccessorials(){
    const el = document.getElementById("a_list");
    if(!el) return;
    if(!ACCESSORIALS.length){
      el.innerHTML = `<div class="muted small">(no items)</div>`;
      return;
    }
    el.innerHTML = ACCESSORIALS.map((a, idx)=>{
      const type = esc(a.type);
      const note = a.note ? ` · ${esc(a.note)}` : "";
      const qty = (a.qty !== null && a.qty !== undefined && a.qty !== "") ? ` · Qty: <b>${esc(a.qty)}</b>` : "";
      const amt = ` · Amount: <b>${fmtMoney(a.amount)}</b>`;
      return `
        <div class="kv" style="margin-top:8px; display:flex; align-items:center; justify-content:space-between; gap:10px;">
          <div class="v"><b>${titleCaseWords(type)}</b>${note}${qty}${amt}</div>
          <button class="btn-danger" style="width:auto;" onclick="removeAccessorial(${idx})">✕</button>
        </div>
      `;
    }).join("");
  }

  function addAccessorial(){
    const type = (document.getElementById("a_type").value||"").trim();
    const note = (document.getElementById("a_note").value||"").trim() || null;
    const qtyRaw = (document.getElementById("a_qty").value||"").trim();
    const amtRaw = (document.getElementById("a_amt").value||"").trim();

    const amount = Number(amtRaw || 0);
    const qty = qtyRaw ? Number(qtyRaw) : null;

    if(!type){ toast("Select a type"); return; }
    if(!isFinite(amount) || amount < 0){ toast("Bad amount"); return; }

    if((type==="detention" || type==="layover") && (qty===null || !isFinite(qty) || qty < 0)){
      toast("Qty required for detention/layover");
      return;
    }

    ACCESSORIALS.push({ type, note, qty, amount });
    document.getElementById("a_note").value="";
    document.getElementById("a_qty").value="";
    document.getElementById("a_amt").value="";
    renderAccessorials();
  }

  function removeAccessorial(i){
    ACCESSORIALS.splice(i, 1);
    renderAccessorials();
  }

  function clearNegotiate(){
    if(document.getElementById("n_loaded_miles")) document.getElementById("n_loaded_miles").value="";
    if(document.getElementById("n_total_miles")) document.getElementById("n_total_miles").value="";
    if(document.getElementById("n_override_reason")) document.getElementById("n_override_reason").value="";
    if(document.getElementById("n_driver_cpm")) document.getElementById("n_driver_cpm").value="";
    ACCESSORIALS = [];
    ROUTE_META = { origin_state: null };
    document.getElementById("autoMilesInfo").textContent = "Not routed yet";
    renderAccessorials();
    if(document.getElementById("negCleanOut")) document.getElementById("negCleanOut").innerHTML="";
    toast("Cleared");
  }

  function summarizeAccessorials(){
    let lumper_fee = 0;
    let detention_hours = 0;
    let breakdown_fee = 0;
    let layover_days = 0;
    let layover_per_day = 0;

    for(const a of ACCESSORIALS){
      const t = String(a.type||"").toLowerCase();
      const amt = Number(a.amount||0);
      const qty = (a.qty===null || a.qty===undefined || a.qty==="") ? null : Number(a.qty);

      if(t==="detention"){
        detention_hours += Number(qty || 0);
      }else if(t==="layover"){
        layover_days += Math.floor(Number(qty || 0));
        layover_per_day = Number(amt || 0);
      }else if(t==="breakdown"){
        breakdown_fee += amt;
      }else{
        lumper_fee += amt;
      }
    }
    return {
      lumper_fee: Number(lumper_fee.toFixed(2)),
      detention_hours: Number(detention_hours.toFixed(2)),
      breakdown_fee: Number(breakdown_fee.toFixed(2)),
      layover_days: Math.max(0, parseInt(layover_days || 0, 10)),
      layover_per_day: Number((layover_per_day || 0).toFixed(2))
    };
  }

  function kvCard(title, obj, keyPrefix){
    const keys = Object.keys(obj || {});
    if(!keys.length) return "";
    const items = keys.map(k=>{
      const label = prettyLabel((keyPrefix ? (keyPrefix + "." + k) : k));
      const val = fmtValueByKey(k, obj[k]);
      return `<div class="kv"><div class="k">${esc(label)}</div><div class="v"><b>${esc(val)}</b></div></div>`;
    }).join("");
    return `
      <div class="card" style="margin-top:10px;">
        <div class="row"><div class="left"><div class="title" style="font-size:16px;">${esc(title)}</div></div></div>
        <div class="divider"></div>
        <div class="kvs">${items}</div>
      </div>
    `;
  }

  function renderNegotiateResultClean(j){
    const ok = !!j?.ok;
    const applied = !!j?.apply_to_load;

    const summary = {
      load_id: j?.load_id,
      broker_mc: j?.broker_mc,
      applied: applied,
      warnings: (j?.warnings && j.warnings.length) ? j.warnings.join(", ") : "none"
    };

    const selected = j?.selected || {};
    const fuel = j?.fuel || {};
    const defaults = j?.policy_defaults || {};
    const market = j?.market_assumptions || {};
    const breakdown = j?.breakdown || {};

    const out = `
      <div class="chips" style="margin-top:8px;">
        <span class="chip">${ok ? "OK" : "NOT OK"}</span>
        <span class="chip">${applied ? "Applied" : "Not Applied"}</span>
        ${fuel?.source ? `<span class="chip">Fuel Source: <b>${esc(fuel.source)}</b></span>` : ``}
        ${fuel?.period ? `<span class="chip">Fuel Week: <b>${esc(fuel.period)}</b></span>` : ``}
        ${fuel?.origin_state ? `<span class="chip">Origin State: <b>${esc(fuel.origin_state)}</b></span>` : ``}
      </div>

      ${kvCard("Summary", summary, "")}
      ${kvCard("Selected (Broker-Controlled)", selected, "selected")}
      ${kvCard("Fuel", fuel, "fuel")}
      ${kvCard("Policy Defaults", defaults, "policy_defaults")}
      ${kvCard("Market Assumptions", market, "market_assumptions")}
      ${kvCard("Breakdown", breakdown, "breakdown")}
    `;

    const outEl = document.getElementById("negCleanOut");
    if(outEl) outEl.innerHTML = out;
  }

  async function autoMiles(){
    const loadId = (document.getElementById("n_load_id").value||"").trim();
    if(!loadId){ toast("No load selected"); return; }

    try{
      const j = await apiPOST(`/broker/loads/${loadId}/route-miles`, { country:"US" });

      if(j?.loaded_miles){
        document.getElementById("n_loaded_miles").value = String(j.loaded_miles);
      }
      if(j?.total_miles){
        document.getElementById("n_total_miles").value = String(j.total_miles);
      }

      const os = j?.meta?.origin_geocode?.state_abbreviation || null;
      ROUTE_META.origin_state = os;

      const info = `loaded=${j.loaded_miles} · total=${j.total_miles} · dh=${j.deadhead_buffer_pct} · origin=${os||"?"}`;
      document.getElementById("autoMilesInfo").textContent = info;
      toast("Miles routed + filled");
    }catch(e){
      toast("Auto miles failed: " + (e.message||""));
    }
  }

  async function runNegotiate(){
    const loadId = (document.getElementById("n_load_id").value||"").trim();
    if(!loadId){ toast("No load selected"); return; }

    const loaded = (document.getElementById("n_loaded_miles").value||"").trim();
    const total = (document.getElementById("n_total_miles").value||"").trim();
    if(!loaded || !total){ toast("Loaded miles + Total miles required"); return; }

    const apply = (document.getElementById("n_apply").value||"false") === "true";
    const override_reason = (document.getElementById("n_override_reason").value||"").trim() || null;
    const driver_cpm_raw = (document.getElementById("n_driver_cpm").value||"").trim();
    const fuel_mode = (document.getElementById("n_fuel_mode").value||"national").trim();

    const acc = summarizeAccessorials();

    const payload = {
      loaded_miles: Number(loaded),
      total_miles: Number(total),
      apply_to_load: apply,
      lumper_fee: acc.lumper_fee,
      detention_hours: acc.detention_hours,
      breakdown_fee: acc.breakdown_fee,
      layover_days: acc.layover_days,
      layover_per_day: acc.layover_per_day,
      fuel_mode: fuel_mode
    };

    if(fuel_mode === "origin_state"){
      payload.origin_state = ROUTE_META.origin_state;
    }

    if(driver_cpm_raw !== ""){
      payload.driver_loaded_mile_pay = Number(driver_cpm_raw);
    }
    if(override_reason) payload.override_reason = override_reason;

    try{
      const j = await apiPOST(`/broker/loads/${loadId}/negotiate`, payload);
      renderNegotiateResultClean(j);
      toast(apply ? "Calculated + applied to load" : "Calculated (not applied)");
      await refreshLoads();
    }catch(e){
      toast(e.message || "Negotiate failed");
    }
  }

  window.__BOOT = function(){ refreshLoads(); };

  document.getElementById("refreshBtn").addEventListener("click", refreshLoads);
  document.getElementById("visFilter").addEventListener("change", applyFilters);
  document.getElementById("mineFilter").addEventListener("change", applyFilters);
  document.getElementById("q").addEventListener("input", applyFilters);
  document.getElementById("createBtn").addEventListener("click", async function(){
    try{
      const body = {
        shipper_name: (document.getElementById("c_shipper_name").value||"").trim() || null,
        customer_ref: (document.getElementById("c_customer_ref").value||"").trim() || null,
        pickup_address: (document.getElementById("c_pickup_address").value||"").trim(),
        pickup_appt: (document.getElementById("c_pickup_appt").value||"").trim() || null,
        delivery_address: (document.getElementById("c_delivery_address").value||"").trim(),
        delivery_appt: (document.getElementById("c_delivery_appt").value||"").trim() || null,
        dispatcher_username: (document.getElementById("c_dispatcher_username").value||"").trim() || null,
        driver_pay: Number(document.getElementById("c_driver_pay").value||0),
        fuel_surcharge: Number(document.getElementById("c_fuel_surcharge").value||0),
        ratecon_terms: (document.getElementById("c_ratecon_terms").value||"").trim() || null
      };
      const j = await apiPOST("/broker/loads/create", body);
      toast("Created pending load #" + j.load_id);
      await refreshLoads();
    }catch(e){
      toast("Create failed: " + e.message);
    }
  });

  renderAccessorials();
  showLoginIfNeeded();
  refreshLoads();
</script>
</body>
</html>
"""

@router.get("/broker-ui", response_class=HTMLResponse)
def broker_ui():
    return BROKER_HTML
