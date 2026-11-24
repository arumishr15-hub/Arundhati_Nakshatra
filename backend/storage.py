"""Storage for Arundhati Nakshatra.

Two interchangeable back ends behind one tiny key-value interface:

  * Folder (default, on your Mac):   everything lives in <project>/data
  * Postgres (cloud):                 set DATABASE_URL (e.g. a free Neon database) and the same
                                      keys are stored in one table, so data survives restarts on free hosts.

Keys look like file paths:
  astrologer_profile.json         your profile (name, services, hours) used by the booking agent
  appointments.json               all booked appointments
  settings.json                   AI provider + keys saved from the app (cloud mode)
  profiles/<id>/birth_details.json, kundali.json, report_d1.md, report_d9.md, notes.md, chat.json
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROFILES = DATA / "profiles"
_lock = threading.Lock()

DEFAULT_ASTROLOGER = {
    "name": "Your Name",
    "title": "Vedic Astrologer — Arundhati Nakshatra",
    "bio": "Edit this profile from the 'My Profile' tab. Describe your experience, lineage and approach.",
    "languages": ["Hindi", "English"],
    "phone": "",
    "email": "",
    "location": "Online (Video call) / In person",
    "timezone": "Asia/Kolkata",
    "working_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    "start_time": "10:00",
    "end_time": "18:00",
    "slot_minutes": 45,
    "services": [
        {"name": "Complete Kundali Analysis", "minutes": 60},
        {"name": "Career & Finance", "minutes": 45},
        {"name": "Marriage & Relationships / Kundali Milan", "minutes": 45},
        {"name": "Quick Question (Prashna)", "minutes": 20},
    ],
}


# ====================================================================== back ends
class FolderKV:
    name = "folder"

    def _p(self, key: str) -> Path:
        if ".." in key or key.startswith("/"):
            raise ValueError("bad key")
        return DATA / key

    def get(self, key):
        p = self._p(key)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def put(self, key, value):
        p = self._p(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(value, encoding="utf-8")
        tmp.replace(p)

    def exists(self, key):
        return self._p(key).exists()

    def list(self, prefix, suffix=""):
        """[(key, mtime)] for keys under prefix ending with suffix."""
        base = DATA / prefix
        if not base.exists():
            return []
        return [(str(p.relative_to(DATA)), p.stat().st_mtime) for p in base.rglob("*" + suffix) if p.is_file()]


class PostgresKV:
    name = "postgres"

    def __init__(self, url: str):
        import psycopg
        self.psycopg, self.url, self.conn = psycopg, url, None
        self._q("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
                "updated DOUBLE PRECISION NOT NULL)")

    def _q(self, sql, args=(), fetch=False):
        for attempt in (1, 2):
            try:
                if self.conn is None or self.conn.closed:
                    self.conn = self.psycopg.connect(self.url, autocommit=True, connect_timeout=15)
                with self.conn.cursor() as cur:
                    cur.execute(sql, args)
                    return cur.fetchall() if fetch else None
            except self.psycopg.OperationalError:
                self.conn = None  # serverless DBs drop idle connections — reconnect once
                if attempt == 2:
                    raise

    def get(self, key):
        r = self._q("SELECT value FROM kv WHERE key=%s", (key,), fetch=True)
        return r[0][0] if r else None

    def put(self, key, value):
        self._q("INSERT INTO kv (key, value, updated) VALUES (%s, %s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated=EXCLUDED.updated", (key, value, time.time()))

    def exists(self, key):
        return bool(self._q("SELECT 1 FROM kv WHERE key=%s", (key,), fetch=True))

    def list(self, prefix, suffix=""):
        return [(k, u) for k, u in self._q("SELECT key, updated FROM kv WHERE key LIKE %s", (prefix + "%" + suffix,), fetch=True)]


_kv = None


def kv():
    global _kv
    if _kv is None:
        url = os.environ.get("DATABASE_URL", "").strip()
        _kv = PostgresKV(url) if url else FolderKV()
    return _kv


def backend_name() -> str:
    return kv().name


def _read(key: str, default):
    raw = kv().get(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _write(key: str, obj) -> None:
    kv().put(key, json.dumps(obj, indent=2, ensure_ascii=False))


def init() -> None:
    if not kv().exists("astrologer_profile.json"):
        _write("astrologer_profile.json", DEFAULT_ASTROLOGER)
    if not kv().exists("appointments.json"):
        _write("appointments.json", [])


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return (s[:30] or "person") + "-" + uuid.uuid4().hex[:6]


def _pkey(pid: str, name: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", pid):
        raise ValueError("bad profile id")
    return f"profiles/{pid}/{name}"


# ====================================================================== profiles
def create_profile(birth: dict, kundali: dict) -> str:
    pid = _slug(birth.get("name", "person"))
    _write(_pkey(pid, "birth_details.json"), birth)
    _write(_pkey(pid, "kundali.json"), kundali)
    return pid


def set_owner(pid: str, owner: str) -> None:
    _write(_pkey(pid, "owner.json"), {"owner": owner})


def get_owner(pid: str) -> str | None:
    return (_read(_pkey(pid, "owner.json"), {}) or {}).get("owner")


def list_profiles(owner: str | None = None) -> list[dict]:
    """All kundalis (admin) or only those created on one device (owner = that device's private id)."""
    keys = dict(kv().list("profiles/"))
    pids = sorted({k.split("/")[1] for k in keys if k.count("/") == 2},
                  key=lambda p: max(u for k, u in keys.items() if k.startswith(f"profiles/{p}/")), reverse=True)
    out = []
    for pid in pids:
        if owner is not None and get_owner(pid) != owner:
            continue
        b = _read(_pkey(pid, "birth_details.json"), None)
        if b:
            has = lambda n: f"profiles/{pid}/{n}" in keys
            out.append({"id": pid, **{k: b.get(k) for k in ("name", "date", "time", "place")},
                        "has_d1": has("report_d1.md"), "has_d9": has("report_d9.md"), "has_notes": has("notes.md")})
    return out


def get_profile(pid: str) -> dict | None:
    k = _read(_pkey(pid, "kundali.json"), None)
    if not k:
        return None
    return {"id": pid, "birth": _read(_pkey(pid, "birth_details.json"), {}), "kundali": k,
            "reports": {"d1": read_text(pid, "report_d1.md"), "d9": read_text(pid, "report_d9.md"),
                        "notes": read_text(pid, "notes.md")},
            "chat": _read(_pkey(pid, "chat.json"), [])}


def save_text(pid: str, name: str, text: str) -> None:
    kv().put(_pkey(pid, name), text)


def read_text(pid: str, name: str) -> str | None:
    return kv().get(_pkey(pid, name))


def save_chat(pid: str, chat: list) -> None:
    _write(_pkey(pid, "chat.json"), chat)


# ====================================================================== astrologer + appointments
def _no_prices(p: dict) -> dict:
    """The app does not show or store fees, amounts or payment details."""
    p = {k: v for k, v in p.items() if k not in ("currency", "fee", "fees", "price", "payment")}
    p["services"] = [{k: v for k, v in s.items() if k in ("name", "minutes")} for s in p.get("services", [])]
    return p


def get_astrologer() -> dict:
    return _no_prices({**DEFAULT_ASTROLOGER, **_read("astrologer_profile.json", {})})


def save_astrologer(p: dict) -> dict:
    merged = _no_prices({**get_astrologer(), **p})
    _write("astrologer_profile.json", merged)
    return merged


def list_appointments() -> list[dict]:
    return _read("appointments.json", [])


def add_appointment(appt: dict) -> dict:
    with _lock:
        appts = list_appointments()
        appt = {"id": "APT-" + uuid.uuid4().hex[:6].upper(), "status": "confirmed", **appt}
        appts.append(appt)
        _write("appointments.json", appts)
    return appt


def update_appointment(aid: str, **fields) -> dict | None:
    with _lock:
        appts = list_appointments()
        for a in appts:
            if a["id"] == aid:
                a.update(fields)
                _write("appointments.json", appts)
                return a
    return None


# ====================================================================== settings (AI provider/keys)
def get_settings() -> dict:
    return _read("settings.json", {})


def save_settings(values: dict) -> None:
    s = get_settings()
    s.update({k: v for k, v in values.items()})
    _write("settings.json", {k: v for k, v in s.items() if v != ""})
