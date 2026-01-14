from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from auth import authenticate_user, create_user, create_token, get_current_user
from fmcsa import lookup_mc

app = FastAPI(title="Chequmate Freight System")

# -------------------------------------------------
# STATIC FILES
# -------------------------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")

# -------------------------------------------------
# ROUTES
# -------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home():
    return open("static/login.html").read()

@app.get("/register")
def register(username: str, password: str):
    return create_user(username, password)

@app.get("/login")
def login(username: str, password: str):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token, "role": user["role"]}

# -------------------------------------------------
# PROTECTED: DISPATCHER PANEL
# -------------------------------------------------
from fastapi.responses import FileResponse

@app.get("/dispatcher-panel")
def dispatcher_panel():
    return FileResponse("static/dispatcher.html")

# -------------------------------------------------
# BROKER LOOKUP (LOGGED IN USERS ONLY)
# -------------------------------------------------
@app.get("/verify-broker")
def verify_broker(mc_number: str, user=Depends(get_current_user)):
    result = lookup_mc(mc_number)
    return result

# -------------------------------------------------
# VERIFY TOKEN
# -------------------------------------------------
@app.get("/verify-token")
def verify_token(user=Depends(get_current_user)):
    return {"username": user["username"], "role": user["role"]}

