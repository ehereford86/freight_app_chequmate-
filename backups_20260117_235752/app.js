const API_BASE = ""; // same-origin

function $(sel){ return document.querySelector(sel); }
function money(n){
  const v = Number(n || 0);
  return v.toLocaleString(undefined, { style:"currency", currency:"USD" });
}

function setMsg(id, txt){
  const el = $(id);
  if(el) el.textContent = txt || "";
}

function getToken(){ return localStorage.getItem("token") || ""; }
function setToken(t){ localStorage.setItem("token", t); }
function clearToken(){ localStorage.removeItem("token"); }

async function postJSON(path, body, token=""){
  const headers = { "Content-Type": "application/json" };
  if(token) headers["Authorization"] = `Bearer ${token}`;

  const r = await fetch(API_BASE + path, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  let data = null;
  try { data = await r.json(); } catch(e){}

  if(!r.ok){
    const detail = (data && (data.detail || data.message)) ? (data.detail || data.message) : `HTTP ${r.status}`;
    throw new Error(detail);
  }
  return data;
}

// --- AUTH ---
async function doLogin(){
  setMsg("#loginMsg", "");
  try{
    const username = ($("#loginUser")?.value || "").trim();
    const password = ($("#loginPass")?.value || "").trim();
    if(!username || !password) throw new Error("Enter username + password");

    // Your API currently exposes /login (looks like GET in your earlier openapi list),
    // but we’ll call POST first (safer). If it fails, you can adjust to GET later.
    const data = await postJSON("/login", { username, password });

    if(!data || !data.token) throw new Error("No token returned");
    setToken(data.token);
    $("#statusPill").textContent = "Logged in";
    setMsg("#loginMsg", "Logged in.");
  }catch(e){
    $("#statusPill").textContent = "Not logged in";
    setMsg("#loginMsg", `Login failed: ${e.message}`);
  }
}

function doLogout(){
  clearToken();
  $("#statusPill").textContent = "Not logged in";
  setMsg("#loginMsg", "Logged out.");
}

async function doRegister(){
  setMsg("#regMsg", "");
  try{
    const username = ($("#regUser")?.value || "").trim();
    const password = ($("#regPass")?.value || "").trim();
    const role = ($("#regRole")?.value || "driver").trim();
    const mc_number = ($("#regMc")?.value || "").trim();

    if(!username || !password) throw new Error("Enter username + password");
    if(password.length < 8) throw new Error("Password must be at least 8 characters");
    if(role === "broker" && !mc_number) throw new Error("Broker MC# is required");

    const data = await postJSON("/register", { username, password, role, mc_number });
    setMsg("#regMsg", data?.message || "Registered. You can login now.");
  }catch(e){
    setMsg("#regMsg", `Register failed: ${e.message}`);
  }
}

// --- CALC ---
function toggleRaw(){
  const box = $("#rawWrap");
  if(!box) return;
  box.classList.toggle("hidden");
  const btn = $("#btnRaw");
  if(btn){
    btn.textContent = box.classList.contains("hidden") ? "Show raw JSON" : "Hide raw JSON";
  }
}

async function doCalculate(){
  setMsg("#calcMsg", "");
  try{
    const body = {
      miles: Number($("#miles")?.value || 0),
      linehaul_rate: Number($("#linehaulRate")?.value || 0),
      deadhead_miles: Number($("#deadheadMiles")?.value || 0),
      deadhead_rate: Number($("#deadheadRate")?.value || 0),
      detention: Number($("#detention")?.value || 0),
      lumper_fee: Number($("#lumperFee")?.value || 0),
      extra_stop_fee: Number($("#extraStopFee")?.value || 0),
    };

    const token = getToken();

    // IMPORTANT: correct endpoint
    const data = await postJSON("/calculate-rate", body, token);

    // raw
    const rawBox = $("#rawBox");
    if(rawBox) rawBox.textContent = JSON.stringify(data, null, 2);

    const b = data?.breakdown || {};
    const fuel = data?.fuel || {};

    $("#outTotal").textContent = money(b.total);
    $("#outFuel").textContent = money(b.fuel_total);

    $("#outLinehaul").textContent = money(b.linehaul_total);
    $("#outDeadhead").textContent = money(b.deadhead_total);
    $("#outFuelRow").textContent = money(b.fuel_total);

    $("#outAccessorials").textContent = money(b.accessorials_total);
    $("#outSubtotal").textContent = money(b.subtotal);

    // show nice message if fuel missing
    if(fuel && fuel.error){
      setMsg("#calcMsg", `Fuel note: ${fuel.error}`);
    } else {
      setMsg("#calcMsg", "");
    }

  }catch(e){
    setMsg("#calcMsg", `Calc failed: ${e.message}`);
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
  $("#btnRaw") && ($("#btnRaw").textContent = "Show raw JSON");

  // status pill based on stored token
  const hasToken = !!getToken();
  $("#statusPill") && ($("#statusPill").textContent = hasToken ? "Logged in" : "Not logged in");
}

document.addEventListener("DOMContentLoaded", init);
