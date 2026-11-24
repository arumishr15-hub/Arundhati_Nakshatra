"""
Free AI questions and question codes.

* Every kundali gets FREE_QUESTIONS free AI chat answers (set in the Admin page; default 3).
* The astrologer creates question codes (e.g. LOTUS-7F3K worth 10 questions) and gives them to clients.
  A client enters the code in the chat; the questions are added to that kundali. Each code works once.
* Answers from the built-in guide (when no AI key is set) are always free and are not counted.
"""
from __future__ import annotations

import datetime as dt
import os
import random
import threading

import storage

_lock = threading.Lock()
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O/1/I/L — easy to read aloud


def free_limit() -> int:
    try:
        return max(0, int(os.environ.get("FREE_QUESTIONS", "3")))
    except ValueError:
        return 3


def _qkey(pid: str) -> str:
    return storage._pkey(pid, "quota.json")


def state(pid: str) -> dict:
    q = storage._read(_qkey(pid), {"used": 0, "bonus": 0, "codes": []})
    free = free_limit()
    total = free + q.get("bonus", 0)
    return {"free": free, "bonus": q.get("bonus", 0), "used": q.get("used", 0), "total": total,
            "remaining": max(0, total - q.get("used", 0)), "codes": q.get("codes", [])}


def can_ask(pid: str) -> bool:
    return state(pid)["remaining"] > 0


def use_one(pid: str) -> dict:
    with _lock:
        q = storage._read(_qkey(pid), {"used": 0, "bonus": 0, "codes": []})
        q["used"] = q.get("used", 0) + 1
        storage._write(_qkey(pid), q)
    return state(pid)


# ---------------------------------------------------------------- codes
def list_codes() -> list[dict]:
    return storage._read("codes.json", [])


def create_codes(count: int, questions: int, note: str = "") -> list[dict]:
    count, questions = max(1, min(int(count), 50)), max(1, min(int(questions), 500))
    with _lock:
        codes = list_codes()
        existing = {c["code"] for c in codes}
        new = []
        while len(new) < count:
            code = "LOTUS-" + "".join(random.SystemRandom().choice(ALPHABET) for _ in range(4))
            if code in existing:
                continue
            existing.add(code)
            new.append({"code": code, "questions": questions, "note": note.strip()[:60],
                        "created": dt.date.today().isoformat(), "used_by": None, "used_by_name": None, "used_on": None})
        storage._write("codes.json", codes + new)
    return new


def delete_code(code: str) -> bool:
    with _lock:
        codes = list_codes()
        keep = [c for c in codes if c["code"] != code or c.get("used_by")]
        storage._write("codes.json", keep)
    return len(keep) < len(codes)


def redeem(pid: str, raw: str) -> tuple[bool, str, dict]:
    code = raw.strip().upper().replace(" ", "")
    if code and not code.startswith("LOTUS-"):
        code = "LOTUS-" + code.replace("LOTUS", "").lstrip("-")
    with _lock:
        codes = list_codes()
        c = next((x for x in codes if x["code"] == code), None)
        if not c:
            return False, "That code was not found. Please check it and try again.", state(pid)
        if c.get("used_by"):
            return False, "This code has already been used.", state(pid)
        prof = storage.get_profile(pid) or {}
        c.update(used_by=pid, used_by_name=(prof.get("birth") or {}).get("name"), used_on=dt.date.today().isoformat())
        storage._write("codes.json", codes)
        q = storage._read(_qkey(pid), {"used": 0, "bonus": 0, "codes": []})
        q["bonus"] = q.get("bonus", 0) + c["questions"]
        q.setdefault("codes", []).append(code)
        storage._write(_qkey(pid), q)
    return True, f"🌸 Code accepted — {c['questions']} questions added.", state(pid)
