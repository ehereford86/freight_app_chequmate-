from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

ADMIN_HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Chequmate Admin</title>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; margin:24px; max-width:1100px;}
    h1{margin:0 0 8px 0;}
    .muted{color:#666;}
    .row{display:flex; gap:14px; flex-wrap:wrap; align-items:flex-end;}
    .card{border:1px solid #ddd; border-radius:10px; padding:14px; margin-top:14px;}
    input, button, select{padding:10px; border-radius:8px; border:1px solid #ccc;}
    button{cursor:pointer;}
    button.primary{border-color:#111; background:#111; color:#fff;}
    button.danger{border-color:#b00; background:#b00; color:#fff;}
    table{width:100%; border-collapse:collapse; margin-top:10px;}
    th, td{padding:8px; border-bottom:1px solid #eee; text-align:left; font-size:14px;}
    .pill{display:inline-block; padding:2px 8px; border:1px solid #ddd; border-radius:999px; font-size:12px;}
    .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;}
    .toast{margin-top:10px; padding:10px; border-radius:10px; background:#f5f5f5; border:1px solid #eee;}
  </style>
</head>
<body>
  <h1>Admin</h1>
  <div class="muted">Login as an <span class="pill">admin</span> user to manage broker approvals.</div>

  <div class="card">
    <div class="row">
      <div style="min-width:260px;">
        <div class="muted">Username</div>
        <input id="u" placeholder="admin username" />
      </div>
      <div style="min-width:260px;">
        <div class="muted">Password</div>
        <input id="p" type="password" placeholder="password" />
      </div>
      <button class="primary" onclick="login()">Login</button>
      <button onclick="logout()">Logout</button>
    </div>
    <div id="me" class="toast" style="display:none;"></div>
  </div>

  <div class="card">
    <div class="row" style="justify-content:space-between;">
      <h2 style="margin:0;">Pending brokers</h2>
      <button class="primary" onclick="loadPending()">Refresh</button>
    </div>
    <div id="pending"></div>
  </div>

  <div class="card">
    <div class="row" style="justify-content:space-between;">
      <h2 style="margin:0;">Loads</h2>
      <button class="primary" onclick="loadLoads()">Refresh</button>
    </div>
    <div id="loads"></div>
  </div>

<script>
  const LS_TOKEN = "cheq_admin_token";

  function getToken(){ return localStorage.getItem(LS_TOKEN) || ""; }
  function setToken(t){ localStorage.setItem(LS_TOKEN, t || ""); }

  function showMe(txt){
    const el = document.getElementById("me");
    el.style.display = "block";
    el.textContent = txt;
  }

  async function apiGET(path){
    const r = await fetch(path, { headers: { "Authorization": "Bearer " + getToken() } });
    const j = await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(j.detail || ("HTTP " + r.status));
    return j;
  }

  async function apiPOST(path, body){
    const r = await fetch(path, {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + getToken(),
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body || {})
    });
    const j = await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(j.detail || ("HTTP " + r.status));
    return j;
  }

  function escapeHtml(s){
    return (s||"")
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;")
      .replaceAll("'","&#039;");
  }

  async function login(){
    const username = document.getElementById("u").value.trim();
    const password = document.getElementById("p").value.trim();
    if(!username || !password){ alert("Enter username + password"); return; }

    const r = await fetch("/login", {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ username, password })
    });

    const j = await r.json().catch(()=>({}));
    if(!r.ok){ alert(j.detail || "Login failed"); return; }

    setToken(j.token);

    // Verify role is actually admin
    try{
      const me = await apiGET("/verify-token");
      if(me.role !== "admin"){
        setToken("");
        alert("This user is not admin (role: " + me.role + ")");
        return;
      }
      showMe("Logged in as: " + me.username + " (role: " + me.role + ")");
      await loadPending();
      await loadLoads();
    }catch(e){
      setToken("");
      alert(e.message);
    }
  }

  function logout(){
    setToken("");
    showMe("Logged out.");
    document.getElementById("pending").innerHTML = "";
    document.getElementById("loads").innerHTML = "";
  }

  async function loadPending(){
    const wrap = document.getElementById("pending");
    wrap.innerHTML = "<div class='muted'>Loading...</div>";
    try{
      const j = await apiGET("/admin/pending-brokers?limit=200");
      const rows = (j.pending || j.brokers || j.rows || []);
      if(!rows.length){
        wrap.innerHTML = "<div class='muted'>No pending brokers.</div>";
        return;
      }
      let html = "<table><thead><tr><th>Username</th><th>MC#</th><th>Status</th><th>Actions</th></tr></thead><tbody>";
      for(const r of rows){
        const user = r.username || r.user || "";
        const mc = r.broker_mc || r.mc_number || r.mc || "";
        const st = r.broker_status || r.status || "";
        html += "<tr>";
        html += "<td class='mono'>" + escapeHtml(user) + "</td>";
        html += "<td class='mono'>" + escapeHtml(mc) + "</td>";
        html += "<td>" + escapeHtml(st) + "</td>";
        html += "<td style='display:flex; gap:8px; flex-wrap:wrap;'>";
        html += "<button class='primary' onclick=\"approveBroker('" + encodeURIComponent(user) + "')\">Approve</button>";
        html += "<button class='danger' onclick=\"rejectBroker('" + encodeURIComponent(user) + "')\">Reject</button>";
        html += "</td>";
        html += "</tr>";
      }
      html += "</tbody></table>";
      wrap.innerHTML = html;
    }catch(e){
      wrap.innerHTML = "<div class='toast'>Error: " + escapeHtml(e.message) + "</div>";
    }
  }

  async function approveBroker(userEnc){
    const username = decodeURIComponent(userEnc);
    if(!confirm("Approve broker: " + username + " ?")) return;
    try{
      await apiPOST("/admin/approve-broker-user", { username });
      await loadPending();
      showMe("Approved: " + username);
    }catch(e){
      alert(e.message);
    }
  }

  async function rejectBroker(userEnc){
    const username = decodeURIComponent(userEnc);
    if(!confirm("Reject broker: " + username + " ?")) return;
    try{
      await apiPOST("/admin/reject-broker-user", { username });
      await loadPending();
      showMe("Rejected: " + username);
    }catch(e){
      alert(e.message);
    }
  }

  async function loadLoads(){
    const wrap = document.getElementById("loads");
    wrap.innerHTML = "<div class='muted'>Loading...</div>";
    try{
      const j = await apiGET("/admin/loads?limit=200");
      const rows = (j.loads || j.rows || []);
      if(!rows.length){
        wrap.innerHTML = "<div class='muted'>No loads.</div>";
        return;
      }
      let html = "<table><thead><tr><th>ID</th><th>Broker MC</th><th>Visibility</th><th>Status</th><th>Driver</th><th>Actions</th></tr></thead><tbody>";
      for(const r of rows){
        const id = r.id;
        const mc = r.broker_mc || "";
        const vis = r.visibility || "";
        const st = r.status || "";
        const drv = r.driver_username || "";
        html += "<tr>";
        html += "<td class='mono'>" + escapeHtml(String(id)) + "</td>";
        html += "<td class='mono'>" + escapeHtml(String(mc)) + "</td>";
        html += "<td>" + escapeHtml(String(vis)) + "</td>";
        html += "<td>" + escapeHtml(String(st)) + "</td>";
        html += "<td class='mono'>" + escapeHtml(String(drv)) + "</td>";
        html += "<td style='display:flex; gap:8px; flex-wrap:wrap;'>";
        html += "<button class='primary' onclick='adminPublish(" + id + ")'>Publish</button>";
        html += "<button class='danger' onclick='adminPull(" + id + ")'>Pull</button>";
        html += "</td>";
        html += "</tr>";
      }
      html += "</tbody></table>";
      wrap.innerHTML = html;
    }catch(e){
      wrap.innerHTML = "<div class='toast'>Error: " + escapeHtml(e.message) + "</div>";
    }
  }

  async function adminPublish(id){
    if(!confirm("Admin publish load " + id + " ?")) return;
    try{
      await apiPOST("/admin/loads/" + id + "/publish", {});
      await loadLoads();
      showMe("Published load: " + id);
    }catch(e){
      alert(e.message);
    }
  }

  async function adminPull(id){
    if(!confirm("Admin pull load " + id + " ?")) return;
    try{
      await apiPOST("/admin/loads/" + id + "/pull", {});
      await loadLoads();
      showMe("Pulled load: " + id);
    }catch(e){
      alert(e.message);
    }
  }

  // Optional auto-refresh if token already exists
  (async function(){
    if(getToken()){
      try{
        const me = await apiGET("/verify-token");
        if(me.role === "admin"){
          showMe("Logged in as: " + me.username + " (role: " + me.role + ")");
          await loadPending();
          await loadLoads();
        }else{
          setToken("");
        }
      }catch(e){
        setToken("");
      }
    }
  })();
</script>

</body>
</html>
"""

@router.get("/admin-ui", response_class=HTMLResponse)
def admin_ui_page():
    # Public page. Real protection is enforced by /verify-token + /admin/* endpoints requiring admin token.
    return HTMLResponse(ADMIN_HTML)
