const API_BASE = ""; // same-origin

function $(sel){ return document.querySelector(sel); }
function setMsg(el, txt){ if(el) el.textContent = txt || ""; }

function getToken(){ return localStorage.getItem("token") || ""; }
function setToken(t){ localStorage.setItem("token", t); }
function clearToken(){ localStorage.removeItem("token"); }

async function tryPost(paths, body){
  let lastErr = null;
  for (const path of paths){
    try{
      const res = await fetch(API_BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch { data = { raw: text }; }

      if(!res.ok){
        const msg = data.detail || data.error || data.message || ("HTTP " + res.status);
        throw new Error(msg);
      }
      return data;
    }catch(e){
      lastErr = e;
    }
  }
  throw lastErr || new Error("Request failed");
}

async function tryGet(path){
  const token = getToken();
  const res = await fetch(API_BASE + path, {
    headers: token ? { "Authorization": "Bearer " + token } : {}
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if(!res.ok){
    const msg = data.detail || data.error || data.message || ("HTTP " + res.status);
    throw new Error(msg);
  }
  return data;
}

function updateSessionPill(){
  const pill = $("#sessionPill");
  const t = getToken();
  if(!pill) return;
  pill.textContent = t ? "Logged in" : "Not logged in";
}

async function onRegister(){
  const msg = $("#regMsg");
  setMsg(msg, "Registering...");
  const username = ($("#reg_username")?.value || "").trim();
  const password = ($("#reg_password")?.value || "").trim();
  const role = ($("#reg_role")?.value || "driver").trim();

  if(!username || !password){
    setMsg(msg, "Username + password required.");
    return;
  }

  try{
    // Common API patterns; we try both without asking you questions
    const data = await tryPost(
      ["/auth/register", "/register"],
      { username, password, role }
    );
    setMsg(msg, "Account created. Now login.");
    return data;
  }catch(e){
    setMsg(msg, "Register failed: " + (e?.message || e));
  }
}

async function onLogin(){
  const msg = $("#loginMsg");
  setMsg(msg, "Logging in...");
  const username = ($("#login_username")?.value || "").trim();
  const password = ($("#login_password")?.value || "").trim();

  if(!username || !password){
    setMsg(msg, "Username + password required.");
    return;
  }

  try{
    const data = await tryPost(
      ["/auth/login", "/login"],
      { username, password }
    );

    // Accept token under common keys
    const token = data.token || data.access_token || data.jwt || "";
    if(token) setToken(token);

    updateSessionPill();
    setMsg(msg, token ? "Logged in." : "Logged in (no token returned).");
  }catch(e){
    setMsg(msg, "Login failed: " + (e?.message || e));
  }
}

async function onCalculate(){
  const out = $("#output");
  out.textContent = "Calculating...";

  const miles = ($("#miles")?.value || "0").trim();
  const linehaul_rate = ($("#linehaul_rate")?.value || "0").trim();
  const deadhead_miles = ($("#deadhead_miles")?.value || "0").trim();
  const deadhead_rate = ($("#deadhead_rate")?.value || "0").trim();
  const detention = ($("#detention")?.value || "0").trim();
  const lumper_fee = ($("#lumper_fee")?.value || "0").trim();
  const extra_stop_fee = ($("#extra_stop_fee")?.value || "0").trim();

  const qs = new URLSearchParams({
    miles, linehaul_rate, deadhead_miles, deadhead_rate, detention, lumper_fee, extra_stop_fee
  });

  try{
    const data = await tryGet("/calculate-rate?" + qs.toString());
    out.textContent = JSON.stringify(data, null, 2);
  }catch(e){
    out.textContent = "Error: " + (e?.message || e);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  updateSessionPill();
  $("#registerBtn")?.addEventListener("click", onRegister);
  $("#loginBtn")?.addEventListener("click", onLogin);
  $("#calcBtn")?.addEventListener("click", onCalculate);
});
