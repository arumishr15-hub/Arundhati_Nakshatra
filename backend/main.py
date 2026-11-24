"""Arundhati Nakshatra — FastAPI server.  Run:  python backend/main.py"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

# tiny .env loader (no extra dependency)
env = ROOT / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import hashlib  # noqa: E402
import hmac  # noqa: E402
import time  # noqa: E402

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import agents  # noqa: E402
import llm  # noqa: E402
import quota  # noqa: E402
import geo  # noqa: E402
import storage  # noqa: E402

storage.init()
# AI settings saved from the app (survive restarts on cloud hosts, where .env is not kept)
for _k, _v in storage.get_settings().items():
    os.environ[_k] = str(_v)

app = FastAPI(title="Arundhati Nakshatra")

# ---------------------------------------------------------------- password login (cloud)
# Set APP_PASSWORD to protect the app when it is online. Locally (no APP_PASSWORD) there is no login.
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
_SECRET = (os.environ.get("SESSION_SECRET") or hashlib.sha256(("an-" + APP_PASSWORD).encode()).hexdigest()).encode()
COOKIE = "an_session"
OPEN_PATHS = ("/login", "/static/", "/manifest.webmanifest", "/sw.js", "/favicon.ico", "/apple-touch-icon", "/healthz")


def _token(ts: int) -> str:
    return f"{ts}.{hmac.new(_SECRET, str(ts).encode(), hashlib.sha256).hexdigest()}"


def _valid(tok: str | None) -> bool:
    try:
        ts, sig = tok.split(".", 1)
        return hmac.compare_digest(_token(int(ts)), tok) and time.time() - int(ts) < 90 * 86400
    except Exception:
        return False


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if not APP_PASSWORD or path.startswith(OPEN_PATHS) or _valid(request.cookies.get(COOKIE)):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Please log in"}, status_code=401)
    return RedirectResponse("/login")


# ---------------------------------------------------------------- private client id
# Each phone/browser gets a private random id (cookie). Kundalis created on it belong to it;
# clients only see their own kundalis, the unlocked Admin sees all.
CLIENT_COOKIE = "an_client"


@app.middleware("http")
async def client_id(request: Request, call_next):
    import secrets
    cid = request.cookies.get(CLIENT_COOKIE)
    new = not (cid and len(cid) == 32 and cid.isalnum())
    if new:
        cid = secrets.token_hex(16)
    request.state.client = cid
    resp = await call_next(request)
    if new:
        resp.set_cookie(CLIENT_COOKIE, cid, max_age=5 * 365 * 86400, httponly=True, samesite="lax",
                        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https")
    return resp


LOGIN_HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Arundhati Nakshatra — Login</title><meta name="theme-color" content="#f7a8c4"><link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png"><meta name="apple-mobile-web-app-capable" content="yes">
<link rel="stylesheet" href="/static/styles.css"></head><body class="login-page"><div class="stars"></div>
<form class="card login-card" method="post" action="/login">
<img src="/static/icons/icon-192.png" alt="" width="84" height="84"><h1>Arundhati <em>Nakshatra</em></h1>
<p class="muted">Enter the app password</p>{err}<input type="password" name="password" autofocus required placeholder="Password">
<button class="btn primary big">✿ Enter</button></form></body></html>"""


@app.get("/login")
def login_page():
    return HTMLResponse(LOGIN_HTML.format(err=""))


@app.post("/login")
async def login(request: Request):
    form = (await request.body()).decode()
    from urllib.parse import parse_qs
    pw = parse_qs(form).get("password", [""])[0]
    if APP_PASSWORD and hmac.compare_digest(pw, APP_PASSWORD):
        r = RedirectResponse("/", status_code=303)
        r.set_cookie(COOKIE, _token(int(time.time())), max_age=90 * 86400, httponly=True, samesite="lax",
                     secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https")
        return r
    import asyncio
    await asyncio.sleep(1)
    return HTMLResponse(LOGIN_HTML.format(err='<p class="err">Wrong password — try again.</p>'), status_code=401)


@app.get("/logout")
def logout():
    r = RedirectResponse("/login" if APP_PASSWORD else "/")
    r.delete_cookie(COOKIE)
    return r
kundali_agent, analyst, booking_agent, note_taker = (
    agents.KundaliAgent(), agents.AnalystAgent(), agents.BookingAgent(), agents.NoteTakerAgent())


class Birth(BaseModel):
    name: str
    gender: str = ""
    date: str          # YYYY-MM-DD
    time: str          # HH:MM[:SS]
    place: str
    lat: float
    lon: float
    tz: str


class Question(BaseModel):
    question: str


class ChatIn(BaseModel):
    messages: list[dict]
    profile_id: str | None = None


class BookIn(BaseModel):
    name: str
    phone: str
    date: str
    time: str
    service: str
    email: str = ""
    notes: str = ""
    mode: str = "Video call"
    profile_id: str = ""


def _text_stream(gen):
    def wrap():
        try:
            yield from gen
        except Exception as e:  # surface API errors to the UI
            yield f"\n\n**Error:** {e}"
    return StreamingResponse(wrap(), media_type="text/plain; charset=utf-8")


@app.get("/api/status")
def status():
    st = llm.status()
    return {"ai": st["ai"], "provider_label": st["provider_label"], "login": bool(APP_PASSWORD),
            "free_questions": quota.free_limit()}


# ---------------------------------------------------------------- admin area
# The Admin page (AI key, free questions, question codes, your profile, appointments) has its own password:
# ADMIN_PASSWORD in the environment, or one you create the first time you open the Admin page.
ADMIN_COOKIE = "an_admin"


def _admin_hash() -> str:
    if os.environ.get("ADMIN_PASSWORD"):
        return hashlib.sha256(os.environ["ADMIN_PASSWORD"].encode()).hexdigest()
    return storage.get_settings().get("ADMIN_PASSWORD_SHA256", "")


def _admin_token(ts: int) -> str:
    return f"{ts}.{hmac.new(_SECRET, f'admin-{ts}-{_admin_hash()}'.encode(), hashlib.sha256).hexdigest()}"


def is_admin(request: Request) -> bool:
    tok = request.cookies.get(ADMIN_COOKIE) or ""
    try:
        ts = int(tok.split(".", 1)[0])
        return bool(_admin_hash()) and hmac.compare_digest(_admin_token(ts), tok) and time.time() - ts < 30 * 86400
    except Exception:
        return False


def need_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(403, "Admin login required")


def need_owner(request: Request, pid: str):
    """Only the device that created a kundali (or the admin) may open it."""
    if is_admin(request):
        return
    if storage.get_owner(pid) != getattr(request.state, "client", None):
        raise HTTPException(404, "Kundali not found")


def _admin_cookie(resp, request: Request):
    resp.set_cookie(ADMIN_COOKIE, _admin_token(int(time.time())), max_age=30 * 86400, httponly=True, samesite="lax",
                    secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https")
    return resp


@app.get("/api/admin/session")
def admin_session(request: Request):
    return {"admin": is_admin(request), "has_password": bool(_admin_hash())}


@app.post("/api/admin/login")
async def admin_login(request: Request, body: dict):
    pw = (body.get("password") or "").strip()
    h = _admin_hash()
    if not h:   # first time: create the admin password
        if len(pw) < 4:
            raise HTTPException(400, "Choose a password with at least 4 characters")
        storage.save_settings({"ADMIN_PASSWORD_SHA256": hashlib.sha256(pw.encode()).hexdigest()})
    elif not hmac.compare_digest(hashlib.sha256(pw.encode()).hexdigest(), h):
        import asyncio
        await asyncio.sleep(1)
        raise HTTPException(401, "Wrong admin password")
    return _admin_cookie(JSONResponse({"admin": True}), request)


@app.post("/api/admin/logout")
def admin_logout():
    r = JSONResponse({"admin": False})
    r.delete_cookie(ADMIN_COOKIE)
    return r


@app.get("/api/admin/ai")
def admin_ai(request: Request):
    need_admin(request)
    return {**llm.status(), "free_questions": quota.free_limit()}


@app.put("/api/admin/ai")
def put_settings(request: Request, body: dict):
    """body: {provider: gemini|groq|anthropic, api_key?: str, model?: str, free_questions?: int}"""
    need_admin(request)
    prov = (body.get("provider") or "").strip().lower()
    key = (body.get("api_key") or "").strip()
    model = (body.get("model") or "").strip()
    lines = env.read_text().splitlines() if env.exists() else []
    saved = {}

    def setv(name, val):
        nonlocal lines
        lines = [l for l in lines if not l.strip().startswith(name + "=")] + [f"{name}={val}"]
        os.environ[name] = val
        saved[name] = val
    if prov in llm.PROVIDERS:
        setv("LLM_PROVIDER", prov)
        if key:
            setv(llm.PROVIDERS[prov]["key"], key)
        llm._model_cache.pop(prov, None)
    if "model" in body:
        setv("LLM_MODEL", model)
        if not model:
            os.environ.pop("LLM_MODEL", None)
    if str(body.get("free_questions", "")).strip().isdigit():
        setv("FREE_QUESTIONS", str(min(int(body["free_questions"]), 1000)))
    try:
        env.write_text("\n".join(lines) + "\n")   # local runs
    except OSError:
        pass
    storage.save_settings(saved)                    # cloud runs (survives restarts)
    st = {**llm.status(), "free_questions": quota.free_limit()}
    if st["ai"] and (key or prov):
        try:
            st["test_reply"] = llm.complete("Reply with exactly: Namaste", [{"role": "user", "content": "Say hello"}], 20)[:80]
            st["model"] = llm.model_name()
        except llm.LLMError as e:
            st["error"] = str(e)
    return st


@app.get("/api/admin/codes")
def admin_codes(request: Request):
    need_admin(request)
    return list(reversed(quota.list_codes()))


@app.post("/api/admin/codes")
def admin_make_codes(request: Request, body: dict):
    need_admin(request)
    return quota.create_codes(body.get("count", 1), body.get("questions", 10), body.get("note", ""))


@app.delete("/api/admin/codes/{code}")
def admin_delete_code(request: Request, code: str):
    need_admin(request)
    return {"deleted": quota.delete_code(code)}


@app.get("/api/profiles/{pid}/quota")
def profile_quota(request: Request, pid: str):
    need_owner(request, pid)
    q = quota.state(pid)
    return {"ai": llm.available(), **{k: q[k] for k in ("free", "bonus", "used", "total", "remaining")}}


@app.post("/api/profiles/{pid}/redeem")
def profile_redeem(request: Request, pid: str, body: dict):
    need_owner(request, pid)
    ok, msg, q = quota.redeem(pid, body.get("code", ""))
    if not ok:
        raise HTTPException(400, msg)
    return {"message": msg, **{k: q[k] for k in ("free", "bonus", "used", "total", "remaining")}}


@app.get("/api/chat/suggestions")
def chat_suggestions():
    import chat
    return chat.SUGGESTIONS


@app.get("/api/geocode")
def geocode(q: str):
    return geo.search(q)


@app.get("/api/geocode/health")
def geocode_health():
    """Shows which free place-search APIs are reachable from this computer."""
    geo.search("Varanasi")
    return {"provider_errors": geo.last_errors or "all providers OK"}


# ---- Agent 1
@app.post("/api/kundali")
def create_kundali(request: Request, b: Birth):
    if len(b.time) == 5:
        b.time += ":00"
    try:
        pid, k = kundali_agent.run(b.model_dump())
        storage.set_owner(pid, request.state.client)
    except Exception as e:
        raise HTTPException(400, f"Could not compute chart: {e}")
    return {"id": pid, "kundali": k}


@app.get("/api/profiles")
def profiles(request: Request):
    return storage.list_profiles(None if is_admin(request) else request.state.client)


@app.get("/api/profiles/{pid}")
def profile(request: Request, pid: str):
    need_owner(request, pid)
    p = storage.get_profile(pid)
    if not p:
        raise HTTPException(404, "Profile not found")
    return p


# ---- Agent 2
@app.post("/api/profiles/{pid}/analyse/{chart}")
def analyse(request: Request, pid: str, chart: str):
    need_owner(request, pid)
    if chart not in ("D1", "D9"):
        raise HTTPException(400, "chart must be D1 or D9")
    return _text_stream(analyst.analyse(pid, chart))


@app.post("/api/profiles/{pid}/ask")
def ask(request: Request, pid: str, q: Question):
    need_owner(request, pid)
    return _text_stream(analyst.ask(pid, q.question))


# ---- Agent 3
@app.get("/api/astrologer")
def astrologer():
    return storage.get_astrologer()


@app.put("/api/astrologer")
def save_astrologer(request: Request, p: dict):
    need_admin(request)
    return storage.save_astrologer(p)


@app.get("/api/slots")
def slots(date: str):
    return {"date": date, "slots": agents.available_slots(date)}


@app.post("/api/book")
def book(request: Request, b: BookIn):
    if b.profile_id:
        need_owner(request, b.profile_id)
    r = agents.book(**b.model_dump())
    if not r["ok"]:
        raise HTTPException(409, r["error"])
    return r["appointment"]


@app.get("/api/appointments")
def appointments(request: Request):
    need_admin(request)
    return sorted(storage.list_appointments(), key=lambda a: (a["date"], a["time"]))


@app.post("/api/appointments/{aid}/cancel")
def cancel(request: Request, aid: str):
    need_admin(request)
    return storage.update_appointment(aid, status="cancelled") or {}


@app.post("/api/booking-chat")
def booking_chat(request: Request, c: ChatIn):
    if c.profile_id:
        need_owner(request, c.profile_id)
    try:
        return booking_agent.chat(c.messages, c.profile_id)
    except Exception as e:
        return {"reply": f"Error: {e}", "booked": None}


# ---- Agent 4
@app.post("/api/profiles/{pid}/notes")
def notes(request: Request, pid: str):
    need_owner(request, pid)
    return _text_stream(note_taker.summarise(pid))


# ---- frontend
FRONT = ROOT / "frontend"
app.mount("/static", StaticFiles(directory=FRONT), name="static")


@app.get("/")
def index():
    return FileResponse(FRONT / "index.html")


# iPhone / PWA files at the site root
@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(FRONT / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(FRONT / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico")
def favicon():
    return FileResponse(FRONT / "icons" / "icon-192.png", media_type="image/png")


@app.get("/apple-touch-icon.png")
@app.get("/apple-touch-icon-precomposed.png")
def apple_icon():
    return FileResponse(FRONT / "icons" / "apple-touch-icon.png", media_type="image/png")


@app.get("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    where = storage.DATA if storage.backend_name() == "folder" else "online database (DATABASE_URL)"
    print(f"\n  Arundhati Nakshatra running →  http://localhost:{port}\n  Data: {where}\n")
    uvicorn.run(app, host=host, port=port, proxy_headers=True, forwarded_allow_ips="*")
