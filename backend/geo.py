"""Place of birth -> suggestions with latitude, longitude, timezone.

Search order (all merged, best first):
  1. Online, queried in parallel: Open-Meteo geocoding, Photon (OpenStreetMap), Nominatim (OpenStreetMap).
     Uses certifi certificates so it works with python.org Python on macOS.
  2. Offline: ~34,000 world cities (incl. ~3,800 Indian towns) from geonamescache — always available.
You can also type coordinates directly, e.g. "25.32, 82.97".
"""
from __future__ import annotations

import json
import re
import ssl
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _SSL = ssl.create_default_context()

try:
    from timezonefinder import TimezoneFinder
    _tf = TimezoneFinder()
except Exception:  # pragma: no cover
    _tf = None

UA = {"User-Agent": "ArundhatiNakshatra/1.0 (vedic astrology app)"}
_pool = ThreadPoolExecutor(max_workers=6)
last_errors: dict[str, str] = {}


def timezone_for(lat: float, lon: float) -> str:
    if _tf:
        try:
            tz = _tf.timezone_at(lat=lat, lng=lon)
            if tz:
                return tz
        except Exception:
            pass
    return "Asia/Kolkata"


def _get(url: str, timeout: float = 5):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return json.loads(r.read().decode())


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


# ---------------------------------------------------------------- online providers
def _open_meteo(q: str, n: int) -> list[dict]:
    d = _get("https://geocoding-api.open-meteo.com/v1/search?" +
             urllib.parse.urlencode({"name": q, "count": n, "language": "en", "format": "json"}))
    out = []
    for it in d.get("results", []) or []:
        parts = [it.get("name"), it.get("admin2"), it.get("admin1"), it.get("country")]
        parts = [p for i, p in enumerate(parts) if p and p not in parts[:i]]
        out.append({"name": ", ".join(parts), "lat": it["latitude"], "lon": it["longitude"],
                    "tz": it.get("timezone") or timezone_for(it["latitude"], it["longitude"]),
                    "pop": it.get("population") or 0, "source": "Open-Meteo"})
    return out


def _photon(q: str, n: int) -> list[dict]:
    d = _get("https://photon.komoot.io/api/?" + urllib.parse.urlencode({"q": q, "limit": n, "lang": "en"}))
    out = []
    for f in d.get("features", []):
        p = f["properties"]
        if p.get("osm_key") not in ("place", "boundary") and p.get("type") not in ("city", "town", "village", "district", "county", "state", "locality"):
            continue
        lon, lat = f["geometry"]["coordinates"]
        parts = [p.get("name"), p.get("county") or p.get("district"), p.get("state"), p.get("country")]
        parts = [x for i, x in enumerate(parts) if x and x not in parts[:i]]
        out.append({"name": ", ".join(parts), "lat": lat, "lon": lon, "tz": timezone_for(lat, lon),
                    "pop": 0, "source": "OpenStreetMap"})
    return out


def _nominatim(q: str, n: int) -> list[dict]:
    d = _get("https://nominatim.openstreetmap.org/search?" +
             urllib.parse.urlencode({"q": q, "format": "json", "limit": n, "accept-language": "en"}))
    return [{"name": it["display_name"], "lat": float(it["lat"]), "lon": float(it["lon"]),
             "tz": timezone_for(float(it["lat"]), float(it["lon"])), "pop": 0, "source": "OpenStreetMap"} for it in d]


PROVIDERS = {"open-meteo": _open_meteo, "photon": _photon, "nominatim": _nominatim}


# ---------------------------------------------------------------- offline index
_index: list[tuple] | None = None
_countries: dict[str, str] = {}

EXTRA_ALIASES = {  # common old/alternate Indian names
    "bombay": "mumbai", "calcutta": "kolkata", "madras": "chennai", "bangalore": "bengaluru",
    "poona": "pune", "benares": "varanasi", "banaras": "varanasi", "kashi": "varanasi",
    "allahabad": "prayagraj", "gurgaon": "gurugram", "mysore": "mysuru", "trivandrum": "thiruvananthapuram",
    "cochin": "kochi", "baroda": "vadodara", "simla": "shimla", "pondicherry": "puducherry",
}


def _build_index():
    global _index, _countries
    if _index is not None:
        return _index
    _index = []
    try:
        import geonamescache
        gc = geonamescache.GeonamesCache()
        _countries = {c: v["name"] for c, v in gc.get_countries().items()}
        for c in gc.get_cities().values():
            names = {_fold(c["name"])}
            for a in c.get("alternatenames") or []:
                if a and re.fullmatch(r"[A-Za-z .'\-]+", a):
                    names.add(_fold(a))
            _index.append((tuple(n for n in names if n), c["name"], c["latitude"], c["longitude"],
                           c["countrycode"], c.get("population") or 0, c.get("timezone")))
    except Exception as e:  # pragma: no cover
        last_errors["offline"] = str(e)
    return _index


def offline_search(q: str, n: int = 8) -> list[dict]:
    idx = _build_index()
    parts = [p.strip() for p in _fold(q).split(",") if p.strip()]
    if not parts:
        return []
    key, rest = parts[0], " ".join(parts[1:])
    key = EXTRA_ALIASES.get(key, key)
    scored = []
    for names, name, lat, lon, cc, pop, tz in idx:
        best = 0
        for nm in names:
            if nm == key:
                best = 3; break
            if nm.startswith(key):
                best = max(best, 2)
            elif len(key) >= 3 and key in nm:
                best = max(best, 1)
        if not best:
            continue
        country = _countries.get(cc, cc)
        if rest and rest not in _fold(country) and rest not in cc.lower():
            best -= 0.5
        boost = 0.3 if cc == "IN" else 0  # Indian app: prefer Indian matches on ties
        scored.append((best + boost, pop, {"name": f"{name}, {country}", "lat": lat, "lon": lon,
                                           "tz": tz or timezone_for(lat, lon), "pop": pop, "source": "offline"}))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [s[2] for s in scored[:n]]


# ---------------------------------------------------------------- public
_COORD = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$")


def search(query: str, limit: int = 8) -> list[dict]:
    q = query.strip()
    if len(q) < 2:
        return []
    m = _COORD.match(q)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return [{"name": f"Coordinates {lat:.4f}, {lon:.4f}", "lat": lat, "lon": lon,
                     "tz": timezone_for(lat, lon), "pop": 0, "source": "coordinates"}]

    city_only = q.split(",")[0].strip()  # Open-Meteo matches on the place name only
    futures = {name: _pool.submit(fn, city_only if name == "open-meteo" else q, limit) for name, fn in PROVIDERS.items()}
    off = _pool.submit(offline_search, q, limit)
    wait(list(futures.values()), timeout=6)

    results = []
    for name, f in futures.items():
        if f.done() and not f.exception():
            results += f.result()
            last_errors.pop(name, None)
        else:
            last_errors[name] = str(f.exception()) if f.done() else "timeout"
    results += off.result()

    # dedupe (~5 km) keeping first (online) entry
    out, seen = [], []
    for r in results:
        if any(abs(r["lat"] - a) < 0.05 and abs(r["lon"] - b) < 0.05 for a, b in seen):
            continue
        seen.append((r["lat"], r["lon"]))
        out.append(r)
    return out[:limit]


# warm the offline index in the background at import
_pool.submit(_build_index)
