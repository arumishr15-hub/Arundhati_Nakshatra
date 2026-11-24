"""
One streaming interface for two AI providers:

  gemini     — Google Gemini API (free key: https://aistudio.google.com/apikey)
  groq       — Groq (free key: https://console.groq.com/keys)

Settings come from .env:  LLM_PROVIDER, GEMINI_API_KEY, GROQ_API_KEY, LLM_MODEL (optional).
Model names change often, so for Gemini and Groq the best available model is discovered from the API.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Iterator

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _SSL = ssl.create_default_context()

PROVIDERS = {
    "gemini": {"label": "Google Gemini (free)", "key": "GEMINI_API_KEY", "get_key": "https://aistudio.google.com/apikey"},
    "groq": {"label": "Groq (free)", "key": "GROQ_API_KEY", "get_key": "https://console.groq.com/keys"},
}
_model_cache: dict[str, str] = {}


class LLMError(Exception):
    pass


def provider() -> str:
    p = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if p in PROVIDERS and os.environ.get(PROVIDERS[p]["key"]):
        return p
    for name, spec in PROVIDERS.items():  # first provider that has a key
        if os.environ.get(spec["key"]):
            return name
    return p if p in PROVIDERS else "gemini"


def key_for(p: str) -> str:
    return os.environ.get(PROVIDERS[p]["key"], "").strip()


def available() -> bool:
    return bool(key_for(provider()))


def is_compact() -> bool:
    """Groq's free tier allows ~6,000 tokens/minute — keep prompts small."""
    return provider() == "groq"


def _http(url: str, body: dict | None = None, headers: dict | None = None, timeout: int = 120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})},
                                 method="POST" if data else "GET")
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_SSL)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:400]
        if e.code in (401, 403):
            raise LLMError(f"The {PROVIDERS[provider()]['label']} key was rejected — check it in My Profile. ({detail})")
        if e.code == 429:
            raise LLMError("The free AI limit was reached for this minute/day. Wait a little and try again.")
        raise LLMError(f"AI request failed ({e.code}): {detail}")
    except urllib.error.URLError as e:
        raise LLMError(f"Could not reach the AI service: {e.reason}")


# ---------------------------------------------------------------- model discovery
def model_name() -> str:
    p = provider()
    if os.environ.get("LLM_MODEL"):
        return os.environ["LLM_MODEL"]
    if p in _model_cache:
        return _model_cache[p]
    try:
        if p == "gemini":
            with _http(f"https://generativelanguage.googleapis.com/v1beta/models?pageSize=200&key={key_for(p)}", timeout=15) as r:
                models = json.loads(r.read())["models"]
            names = [m["name"].split("/")[-1] for m in models
                     if "generateContent" in m.get("supportedGenerationMethods", [])]
            good = [n for n in names if "flash" in n and not any(x in n for x in
                    ("lite", "image", "tts", "live", "audio", "exp", "thinking", "8b", "preview", "transcribe", "translate"))]
            def ver(n):
                import re
                m = re.search(r"(\d+(?:\.\d+)?)", n)
                return float(m.group(1)) if m else 0
            good.sort(key=ver, reverse=True)
            _model_cache[p] = good[0] if good else ("gemini-flash-latest" if "gemini-flash-latest" in names else names[0])
        elif p == "groq":
            with _http("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key_for(p)}"}, timeout=15) as r:
                ids = [m["id"] for m in json.loads(r.read())["data"] if m.get("active", True)]
            prefs = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "llama-4-maverick", "llama-4-scout", "qwen3-32b", "qwen/qwen3-32b",
                     "openai/gpt-oss-20b", "llama-3.1-8b-instant"]
            pick = next((i for pref in prefs for i in ids if pref in i), None)
            pick = pick or next((i for i in ids if not any(x in i for x in ("whisper", "tts", "guard", "embed", "orpheus"))), ids[0])
            _model_cache[p] = pick
    except LLMError:
        raise
    except Exception:
        _model_cache[p] = {"gemini": "gemini-flash-latest", "groq": "llama-3.3-70b-versatile"}[p]
    return _model_cache[p]


# ---------------------------------------------------------------- streaming
def _sse(resp) -> Iterator[dict]:
    for raw in resp:
        line = raw.decode("utf-8", errors="ignore").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            return
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            continue


def stream(system: str, messages: list[dict], max_tokens: int = 4000) -> Iterator[str]:
    """messages: [{"role": "user"|"assistant", "content": str}]"""
    p = provider()
    key = key_for(p)
    if not key:
        raise LLMError("No AI key set. Add a free Gemini or Groq key in My Profile.")
    model = model_name()
    if p == "gemini":
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]} for m in messages],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.6}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={key}"
        with _http(url, body) as r:
            for ev in _sse(r):
                for c in ev.get("candidates", []):
                    for part in c.get("content", {}).get("parts", []):
                        if part.get("text") and not part.get("thought"):
                            yield part["text"]
        return
    if p == "groq":
        body = {"model": model, "stream": True, "max_tokens": min(max_tokens, 4096), "temperature": 0.6,
                "messages": [{"role": "system", "content": system}] + messages}
        with _http("https://api.groq.com/openai/v1/chat/completions", body, {"Authorization": f"Bearer {key}"}) as r:
            for ev in _sse(r):
                for ch in ev.get("choices", []):
                    t = ch.get("delta", {}).get("content")
                    if t:
                        yield t
        return
    raise LLMError(f"Unknown provider {p}")


def complete(system: str, messages: list[dict], max_tokens: int = 1500) -> str:
    return "".join(stream(system, messages, max_tokens))


def status() -> dict:
    p = provider()
    k = key_for(p)
    return {"provider": p, "provider_label": PROVIDERS[p]["label"], "ai": bool(k),
            "key_hint": (k[:6] + "…" + k[-4:]) if len(k) > 12 else "",
            "keys_set": {name: bool(key_for(name)) for name in PROVIDERS},
            "providers": {n: {"label": s["label"], "get_key": s["get_key"]} for n, s in PROVIDERS.items()},
            "model": os.environ.get("LLM_MODEL") or _model_cache.get(p) or "auto"}
