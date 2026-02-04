/* Chequmate Universal Login / Register / Forgot Password
   - Traditional login layout
   - Does NOT touch broker_ui.py / driver_ui.py / dispatcher_ui.py
*/

(function(){
  const API = {
    login: "/login",
    register: "/register",
    verify: "/verify-token",
    pwReq: "/password-reset/request"
  };

  // Put your logo file here (served from /webapp/assets or /static).
  // If you already have a logo in webapp/assets, keep that filename.
  // This will gracefully fall back to text if missing.
  const LOGO_URL = "/webapp/assets/chequmate-logo.png";

  const STORE = {
    tokenKey: "token",
    userKey: "username",
    roleKey: "role"
  };

  function $(id){ return document.getElementById(id); }
  function esc(s){
    if(s === null || s === undefined) return "";
    return String(s)
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;");
  }

  function setToken(t){ localStorage.setItem(STORE.tokenKey, t || ""); }
  function getToken(){ return localStorage.getItem(STORE.tokenKey) || ""; }
  function setUser(u){ localStorage.setItem(STORE.userKey, u || ""); }
  function setRole(r){ localStorage.setItem(STORE.roleKey, r || ""); }

  function toast(msg, kind){
    const box = $("alertBox");
    if(!box) return;
    box.className = "alert" + (kind ? (" " + kind) : "");
    box.innerHTML = esc(msg);
    box.style.display = "block";
  }

  async function apiPOST(path, body){
    const res = await fetch(path, {
      method:"POST",
      headers: { "Content-Type":"application/json" },
      body: JSON.stringify(body || {})
    });
    const j = await res.json().catch(()=>null);
    if(!res.ok){
      const msg = (j && j.detail) ? j.detail : ("HTTP " + res.status);
      throw new Error(msg);
    }
    return j;
  }

  async function apiGET(path){
    const t = getToken();
    const res = await fetch(path, {
      headers: t ? { "Authorization": "Bearer " + t } : {}
    });
    const j = await res.json().catch(()=>null);
    if(!res.ok){
      const msg = (j && j.detail) ? j.detail : ("HTTP " + res.status);
      throw new Error(msg);
    }
    return j;
  }

  function routeByRole(role){
    const r = String(role||"").toLowerCase();
    if(r === "broker") return "/broker-ui";
    if(r === "dispatcher") return "/dispatcher-ui";
    return "/driver-ui";
  }

  function setTab(tab){
    // tab: login | register | forgot
    const tabs = ["login","register","forgot"];
    for(const t of tabs){
      const btn = $("tab_" + t);
      const pane = $("pane_" + t);
      if(btn) btn.classList.toggle("active", t === tab);
      if(pane) pane.style.display = (t === tab) ? "block" : "none";
    }
    toast("", "");
    $("alertBox").style.display = "none";
  }

  function render(){
    const root = document.getElementById("app");
    root.innerHTML = `
      <div class="wrap">
        <div class="shell">

          <div class="card left">
            <div class="brand">
              <img src="${esc(LOGO_URL)}" alt="Chequmate" onerror="this.style.display='none'; document.getElementById('logoFallback').style.display='block';" />
              <div>
                <div class="name">Chequmate</div>
                <div class="tag">Freight · Broker · Dispatcher · Driver</div>
              </div>
              <div id="logoFallback" style="display:none; font-weight:950; letter-spacing:.3px;">CHEQMATE</div>
            </div>

            <div class="tabs">
              <div id="tab_login" class="tab active" onclick="window.__setTab('login')">Login</div>
              <div id="tab_register" class="tab" onclick="window.__setTab('register')">Create account</div>
              <div id="tab_forgot" class="tab" onclick="window.__setTab('forgot')">Forgot password</div>
            </div>

            <div>
              <div class="h1">Sign in</div>
              <p class="sub">Use your Chequmate account to access your role dashboard. Brokers require approval to use broker tools.</p>
            </div>

            <div id="alertBox" class="alert" style="display:none;"></div>

            <!-- LOGIN -->
            <div id="pane_login" class="form">
              <div class="field">
                <label>Username</label>
                <input id="l_user" class="input" placeholder="e.g. broker3" autocomplete="username" />
              </div>
              <div class="field">
                <label>Password</label>
                <input id="l_pass" class="input" placeholder="••••••••" type="password" autocomplete="current-password" />
              </div>
              <div class="row">
                <button id="btnLogin" class="btn" onclick="window.__doLogin()">Login</button>
                <div class="smalllinks">
                  <a href="javascript:void(0)" onclick="window.__setTab('forgot')">Forgot password?</a>
                  <a href="javascript:void(0)" onclick="window.__setTab('register')">Create account</a>
                </div>
              </div>
              <div class="alert warn" style="margin-top:8px;">
                <b>Tester notes:</b> Fuel is weekly live (not cached). National average only for now. No “fuel price date” badge in UI yet. Env hot-reload is not supported by design.
              </div>
            </div>

            <!-- REGISTER -->
            <div id="pane_register" class="form" style="display:none;">
              <div class="row" style="gap:10px;">
                <div class="field" style="flex:1; min-width:220px;">
                  <label>Username</label>
                  <input id="r_user" class="input" placeholder="Choose a username" autocomplete="username" />
                </div>
                <div class="field" style="flex:1; min-width:220px;">
                  <label>Password (min 8 chars)</label>
                  <input id="r_pass" class="input" placeholder="Create a password" type="password" autocomplete="new-password" />
                </div>
              </div>

              <div class="row" style="gap:10px;">
                <div class="field" style="flex:1; min-width:220px;">
                  <label>Role</label>
                  <select id="r_role" onchange="window.__roleChanged()">
                    <option value="driver">Driver</option>
                    <option value="dispatcher">Dispatcher</option>
                    <option value="broker">Broker (requires MC# + approval)</option>
                  </select>
                </div>
                <div class="field" id="mcWrap" style="flex:1; min-width:220px; display:none;">
                  <label>Broker MC#</label>
                  <input id="r_mc" class="input" placeholder="MC123456" />
                </div>
              </div>

              <div class="row">
                <button id="btnRegister" class="btn ok" onclick="window.__doRegister()">Create account</button>
                <div class="smalllinks">
                  <a href="javascript:void(0)" onclick="window.__setTab('login')">Back to login</a>
                </div>
              </div>

              <div class="alert" style="margin-top:8px;">
                Brokers are created as <b>pending</b>. Admin must approve before broker features work.
              </div>
            </div>

            <!-- FORGOT -->
            <div id="pane_forgot" class="form" style="display:none;">
              <div class="field">
                <label>Email (recommended) or Username</label>
                <input id="f_email" class="input" placeholder="you@email.com (or username)" />
              </div>
              <div class="row">
                <button id="btnForgot" class="btn ghost" onclick="window.__doForgot()">Send reset link</button>
                <div class="smalllinks">
                  <a href="javascript:void(0)" onclick="window.__setTab('login')">Back to login</a>
                </div>
              </div>
              <div class="alert" style="margin-top:8px;">
                This sends a reset email if your backend mail config is set. If mail isn’t configured yet, you’ll see an error — that’s expected.
              </div>
            </div>

            <div class="secure">
              <div class="lock">🔒</div>
              <div class="txt">
                <b>Secure area</b><br/>
                Your session uses token-based auth. Never share your password or token. Log out on shared devices.
              </div>
            </div>
          </div>

          <div class="card right">
            <h3 class="promoTitle">Stay connected</h3>
            <p class="promoSub">
              Run loads, negotiate, and check status from anywhere. This portal is built to be simple and fast — like a real brokerage/driver platform should be.
            </p>

            <div class="screenshot">
              App preview (replace with screenshot later)
            </div>

            <div class="badges">
              <a class="badgeLink" href="#" onclick="alert('Add your real App Store link later.'); return false;">
                 App Store <span class="mini">coming soon</span>
              </a>
              <a class="badgeLink" href="#" onclick="alert('Add your real Google Play link later.'); return false;">
                ▶ Google Play <span class="mini">coming soon</span>
              </a>
            </div>

            <div class="footerNote">
              <div><b>Tip for testers:</b> Use <span class="mono">/docs</span> to explore API endpoints.</div>
              <div style="margin-top:6px;">If you are a broker: you can log in immediately, but broker-only actions require approval.</div>
            </div>
          </div>

        </div>
      </div>
    `;
  }

  async function doLogin(){
    $("btnLogin").disabled = true;
    try{
      const username = ($("l_user").value || "").trim();
      const password = ($("l_pass").value || "").trim();
      if(!username || !password) throw new Error("Enter username and password");

      const j = await apiPOST(API.login, { username, password });
      if(!j || !j.token) throw new Error("Login did not return token");

      setToken(j.token);
      setUser(username);
      setRole(j.role || "");

      // Optional verification (gives broker status + mc)
      let role = j.role || "";
      let broker_status = j.broker_status || "";
      try{
        const v = await apiGET(API.verify);
        role = v.role || role;
        broker_status = v.broker_status || broker_status;
      }catch(_e){}

      // If broker but not approved, warn then still route to broker-ui (it will be blocked for broker-only actions)
      if(String(role).toLowerCase() === "broker" && String(broker_status) !== "approved"){
        toast("Broker login OK — status is '" + (broker_status || "pending") + "'. Broker tools require approval.", "warn");
        // still let them proceed to broker-ui if you want:
        window.location.href = routeByRole(role);
        return;
      }

      window.location.href = routeByRole(role);
    }catch(e){
      toast(e.message || "Login failed", "bad");
    }finally{
      $("btnLogin").disabled = false;
    }
  }

  async function doRegister(){
    $("btnRegister").disabled = true;
    try{
      const username = ($("r_user").value || "").trim();
      const password = ($("r_pass").value || "").trim();
      const role = ($("r_role").value || "driver").trim();
      const broker_mc = ($("r_mc").value || "").trim();

      if(!username) throw new Error("Username required");
      if(!password || password.length < 8) throw new Error("Password must be at least 8 characters");
      if(role === "broker" && !broker_mc) throw new Error("Broker MC# required");

      const payload = { username, password, role };
      if(role === "broker") payload.broker_mc = broker_mc;

      await apiPOST(API.register, payload);
      toast("Account created. Now log in.", "ok");
      setTab("login");
      $("l_user").value = username;
      $("l_pass").value = "";
    }catch(e){
      toast(e.message || "Registration failed", "bad");
    }finally{
      $("btnRegister").disabled = false;
    }
  }

  async function doForgot(){
    $("btnForgot").disabled = true;
    try{
      const v = ($("f_email").value || "").trim();
      if(!v) throw new Error("Enter your email (recommended) or username");

      // Your backend may expect {email:...}. If it expects username instead, adjust backend later.
      // This is the cleanest “traditional” UX for now.
      await apiPOST(API.pwReq, { email: v });

      toast("If the account exists, a reset email was sent.", "ok");
      setTab("login");
    }catch(e){
      toast(e.message || "Password reset request failed", "bad");
    }finally{
      $("btnForgot").disabled = false;
    }
  }

  function roleChanged(){
    const role = ($("r_role").value || "").trim();
    $("mcWrap").style.display = (role === "broker") ? "block" : "none";
  }

  // Expose handlers
  window.__setTab = setTab;
  window.__doLogin = doLogin;
  window.__doRegister = doRegister;
  window.__doForgot = doForgot;
  window.__roleChanged = roleChanged;

  // Boot
  render();
  setTab("login");
  roleChanged();

  // Enter-to-submit convenience
  document.addEventListener("keydown", (e)=>{
    if(e.key !== "Enter") return;
    const loginVisible = $("pane_login").style.display !== "none";
    const regVisible = $("pane_register").style.display !== "none";
    const forgotVisible = $("pane_forgot").style.display !== "none";
    if(loginVisible) doLogin();
    else if(regVisible) doRegister();
    else if(forgotVisible) doForgot();
  });
})();
