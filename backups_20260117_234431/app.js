const API_BASE = ""; // same-origin

function $(sel){ return document.querySelector(sel); }

function money(n){
  const x = Number(n || 0);
  return x.toLocaleString(undefined, { style: "currency", currency: "USD" });
}

function setText(id, txt){
  const el = document.getElementById(id);
  if (el) el.textContent = txt;
}

function setMsg(id, txt, isErr=false){
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = txt || "";
  el.classList.toggle("err", !!isErr);
  el.classList.toggle("ok", !isErr && !!txt);
}

function getToken(){
  return localStorage.getItem("token") || "";
}
function setToken(t){
  if (t) localStorage.setItem("token", t);
}
function clearToken(){
  localStorage.removeItem("token");
}

function authHeaders(){
  const t = getToken();
  return t ? { "Authorization": "Bearer " + t } : {};
}

async function getJSON(path){
  const r = await fetch(API_BASE + path, {
    method: "GET",
    headers: { ...authHeaders() }
  });
  const txt = await r.text();
  let data = null;
  try { data = txt ? JSON.parse(txt) : null; } catch { data = { detail: txt }; }
  if (!r.ok){
    const msg = (data && (data.detail || data.message)) ? (data.detail || data.message) : ("HTTP " + r.status);
    throw new Error(msg);
  }
  return data;
}

function qs(obj){
  const p = new URLSearchParams();
  for (const [k,v] of Object.entries(obj)){
    p.set(k, String(v ?? ""));
  }
  return p.toString();
}

function readNum(id, fallback=0){
  const el = document.getElementById(id);
  if (!el) return fallback;
  const v = (el.value ?? "").toString().trim();
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

async function doCalculate(){
  setMsg("calcMsg", "");

  const body = {
    miles: readNum("miles", 0),
    linehaul_rate: readNum("linehaul_rate", 0),
    deadhead_miles: readNum("deadhead_miles", 0),
    deadhead_rate: readNum("deadhead_rate", 0),
    detention: readNum("detention", 0),
    lumper_fee: readNum("lumper_fee", 0),
    extra_stop_fee: readNum("extra_stop_fee", 0),
  };

  try{
    // IMPORTANT: endpoint is /calculate-rate (not /calc, not /calculate)
    const data = await getJSON("/calculate-rate?" + qs(body));

    // raw JSON
    const rawBox = $("#rawBox");
    if (rawBox) rawBox.textContent = JSON.stringify(data, null, 2);

    // totals
    const b = (data && data.breakdown) ? data.breakdown : {};
    setText("outTotal", money(b.total));
    setText("outFuel", money(b.fuel_total));
    setText("outFuel2", money(b.fuel_total));
    setText("outLinehaul", money(b.linehaul_total));
    setText("outDeadhead", money(b.deadhead_total));
    setText("outAccessorials", money(b.accessorials_total));
    setText("outSubtotal", money(b.subtotal));

    // fuel messaging (optional)
    const fuel = (data && data.fuel) ? data.fuel : null;
    if (fuel && fuel.error){
      setMsg("calcMsg", "Fuel note: " + fuel.error, false);
    } else {
      setMsg("calcMsg", "Calculated.", false);
    }
  } catch(err){
    setMsg("calcMsg", "Calc failed: " + (err?.message || "Not Found"), true);
  }
}

function toggleRaw(){
  const box = $("#rawWrap");
  if(!box) return;
  box.classList.toggle("hidden");
  const btn = $("#btnRaw");
  if(btn){
    btn.textContent = box.classList.contains("hidden") ? "Show raw JSON" : "Hide raw JSON";
  }
}

async function doLogin(){
  setMsg("loginMsg", "");
  const u = ($("#loginUser")?.value || "").trim();
  const p = ($("#loginPass")?.value || "").trim();
  if (!u || !p){
    setMsg("loginMsg", "Enter username + password.", true);
    return;
  }

  try{
    const data = await getJSON("/login?" + qs({ username: u, password: p }));
    // backend usually returns {token: "..."} or similar
    const token = data?.token || data?.access_token || "";
    if (!token) throw new Error("No token returned");
    setToken(token);

    $("#statusPill") && ($("#statusPill").textContent = "Logged in");
    setMsg("loginMsg", "Logged in.", false);
  } catch(err){
    setMsg("loginMsg", err?.message || "Invalid credentials", true);
  }
}

function doLogout(){
  clearToken();
  $("#statusPill") && ($("#statusPill").textContent = "Not logged in");
  setMsg("loginMsg", "Logged out.", false);
}

async function doRegister(){
  setMsg("regMsg", "");
  const u = ($("#regUser")?.value || "").trim();
  const p = ($("#regPass")?.value || "").trim();
  const role = ($("#regRole")?.value || "driver").trim();

  if (!u || !p){
    setMsg("regMsg", "Enter username + password.", true);
    return;
  }
  if (p.length < 8){
    setMsg("regMsg", "Password must be at least 8 characters.", true);
    return;
  }

  try{
    const data = await getJSON("/register?" + qs({ username: u, password: p, role }));
    const msg = data?.message || "Registered.";
    setMsg("regMsg", msg, false);
  } catch(err){
    setMsg("regMsg", err?.message || "Register failed", true);
  }
}

function init(){
  $("#btnCalc")?.addEventListener("click", doCalculate);
  $("#btnRaw")?.addEventListener("click", toggleRaw);

  $("#btnLogin")?.addEventListener("click", doLogin);
  $("#btnLogout")?.addEventListener("click", doLogout);
  $("#btnRegister")?.addEventListener("click", doRegister);

  // default hide raw
  $("#rawWrap")?.classList.add("hidden");

  // status pill based on stored token
  const hasToken = !!getToken();
  $("#statusPill") && ($("#statusPill").textContent = hasToken ? "Logged in" : "Not logged in");
}

document.addEventListener("DOMContentLoaded", init);
