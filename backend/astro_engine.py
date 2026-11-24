"""
Agent 1 core — Vedic chart engine.

Computes (sidereal, Lahiri ayanamsa, Swiss Ephemeris):
  * Janam Patrika / Lagna chart (D1, whole-sign houses)
  * Navamsha (D9)
  * Chandra Kundali (Moon as Lagna)
  * Bhava Chalit (Sripati bhava cusps)
  * Vimshottari Mahadasha + Antardasha
  * Dignities, house lordships, Vedic aspects (graha drishti), conjunctions,
    a few classical yogas — the raw material for the analyst agent.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import swisseph as swe

swe.set_sid_mode(swe.SIDM_LAHIRI)
FLAGS = swe.FLG_SIDEREAL | swe.FLG_SPEED | swe.FLG_MOSEPH  # Moshier: no data files needed

SIGNS = ["Mesha (Aries)", "Vrishabha (Taurus)", "Mithuna (Gemini)", "Karka (Cancer)",
         "Simha (Leo)", "Kanya (Virgo)", "Tula (Libra)", "Vrishchika (Scorpio)",
         "Dhanu (Sagittarius)", "Makara (Capricorn)", "Kumbha (Aquarius)", "Meena (Pisces)"]
SIGN_SHORT = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"]
SIGN_LORD = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
             "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
}
ABBR = {"Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me", "Jupiter": "Ju",
        "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke", "Lagna": "As"}

NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
              "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
              "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
              "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
              "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
               "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
YEAR_DAYS = 365.25

EXALT = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11,
         "Saturn": 6, "Rahu": 1, "Ketu": 7}
DEBIL = {k: (v + 6) % 12 for k, v in EXALT.items()}
MOOLA = {"Sun": 4, "Moon": 1, "Mars": 0, "Mercury": 5, "Jupiter": 8, "Venus": 6, "Saturn": 10}
FRIENDS = {
    "Sun": {"friends": ["Moon", "Mars", "Jupiter"], "enemies": ["Venus", "Saturn"]},
    "Moon": {"friends": ["Sun", "Mercury"], "enemies": []},
    "Mars": {"friends": ["Sun", "Moon", "Jupiter"], "enemies": ["Mercury"]},
    "Mercury": {"friends": ["Sun", "Venus"], "enemies": ["Moon"]},
    "Jupiter": {"friends": ["Sun", "Moon", "Mars"], "enemies": ["Mercury", "Venus"]},
    "Venus": {"friends": ["Mercury", "Saturn"], "enemies": ["Sun", "Moon"]},
    "Saturn": {"friends": ["Mercury", "Venus"], "enemies": ["Sun", "Moon", "Mars"]},
}
# Special Vedic aspects (houses counted from planet, inclusive); all planets aspect 7th
SPECIAL_ASPECTS = {"Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10],
                   "Rahu": [5, 7, 9], "Ketu": [5, 7, 9]}
NATURAL_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
KENDRA, TRIKONA, DUSTHANA = {1, 4, 7, 10}, {1, 5, 9}, {6, 8, 12}
HOUSE_MEANING = {
    1: "Self, body, personality", 2: "Wealth, family, speech", 3: "Courage, siblings, efforts",
    4: "Mother, home, comforts, property", 5: "Children, intellect, romance, purva punya",
    6: "Enemies, debts, disease, service", 7: "Marriage, partnerships, business",
    8: "Longevity, transformation, occult, sudden events", 9: "Fortune, dharma, father, guru",
    10: "Career, status, karma", 11: "Gains, income, aspirations, elder siblings",
    12: "Losses, expenses, moksha, foreign lands",
}


def _fmt_deg(lon: float) -> str:
    d = lon % 30
    deg = int(d)
    m = int((d - deg) * 60)
    s = int(round(((d - deg) * 60 - m) * 60))
    if s == 60:
        m, s = m + 1, 0
    return f"{deg}°{m:02d}'{s:02d}\""


def nakshatra_of(lon: float) -> dict:
    span = 360 / 27
    idx = int(lon // span)
    pada = int((lon % span) // (span / 4)) + 1
    return {"name": NAKSHATRAS[idx], "pada": pada, "lord": DASHA_ORDER[idx % 9], "index": idx}


def navamsha_sign(lon: float) -> int:
    sign = int(lon // 30)
    part = int((lon % 30) // (30 / 9))
    start = {0: 0, 1: 9, 2: 6, 3: 3}[sign % 4]  # fire→Ar, earth→Cp, air→Li, water→Cn
    return (start + part) % 12


def dignity(planet: str, sign: int, lon: float | None = None) -> str:
    if planet in ("Rahu", "Ketu"):
        if sign == EXALT[planet]:
            return "Exalted"
        if sign == DEBIL[planet]:
            return "Debilitated"
        return "—"
    if sign == EXALT[planet]:
        return "Exalted"
    if sign == DEBIL[planet]:
        return "Debilitated"
    if planet in MOOLA and sign == MOOLA[planet]:
        return "Moolatrikona"
    if SIGN_LORD[sign] == planet:
        return "Own sign"
    lord = SIGN_LORD[sign]
    if lord in FRIENDS[planet]["friends"]:
        return "Friendly sign"
    if lord in FRIENDS[planet]["enemies"]:
        return "Enemy sign"
    return "Neutral sign"


def to_utc(date: str, time: str, tz: str) -> dt.datetime:
    local = dt.datetime.fromisoformat(f"{date}T{time}")
    return local.replace(tzinfo=ZoneInfo(tz)).astimezone(dt.timezone.utc)


def julday(utc: dt.datetime) -> float:
    return swe.julday(utc.year, utc.month, utc.day,
                      utc.hour + utc.minute / 60 + utc.second / 3600)


def _houses_from(lagna_sign: int, positions: dict) -> dict:
    """Whole-sign house map {1..12: [planets]} for a given lagna sign."""
    houses = {h: [] for h in range(1, 13)}
    for p, sign in positions.items():
        houses[(sign - lagna_sign) % 12 + 1].append(p)
    return houses


def _chart_payload(lagna_sign: int, sign_of: dict, degrees: dict | None = None) -> dict:
    houses = _houses_from(lagna_sign, sign_of)
    return {
        "lagna_sign": lagna_sign,
        "houses": [
            {"house": h, "sign": (lagna_sign + h - 1) % 12,
             "sign_name": SIGNS[(lagna_sign + h - 1) % 12],
             "planets": [{"name": p, "abbr": ABBR[p],
                          "deg": _fmt_deg(degrees[p]) if degrees and p in degrees else None}
                         for p in houses[h]]}
            for h in range(1, 13)
        ],
    }


def vedic_aspects(house_of: dict) -> list[dict]:
    out = []
    for p, h in house_of.items():
        if p == "Lagna":
            continue
        for n in SPECIAL_ASPECTS.get(p, [7]):
            target = (h + n - 2) % 12 + 1
            occupants = [q for q, hh in house_of.items() if hh == target and q not in (p, "Lagna")]
            out.append({"planet": p, "aspect": f"{n}th", "house": target, "on_planets": occupants})
    return out


def detect_yogas(house_of: dict, sign_of: dict, lagna_sign: int) -> list[str]:
    y = []
    lord = lambda h: SIGN_LORD[(lagna_sign + h - 1) % 12]
    moon_h, jup_h = house_of["Moon"], house_of["Jupiter"]
    if ((jup_h - moon_h) % 12) in (0, 3, 6, 9):
        y.append("Gaja Kesari Yoga — Jupiter in a kendra from the Moon")
    if house_of["Sun"] == house_of["Mercury"]:
        y.append("Budhaditya Yoga — Sun and Mercury conjunct")
    if house_of["Moon"] == house_of["Mars"]:
        y.append("Chandra-Mangala Yoga — Moon and Mars conjunct")
    pm = {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa", "Venus": "Malavya", "Saturn": "Shasha"}
    for p, name in pm.items():
        if house_of[p] in KENDRA and dignity(p, sign_of[p]) in ("Exalted", "Own sign", "Moolatrikona"):
            y.append(f"{name} Yoga (Pancha Mahapurusha) — {p} strong in a kendra")
    for k in KENDRA:
        for t in TRIKONA:
            if k == t == 1:
                continue
            a, b = lord(k), lord(t)
            if a != b and house_of[a] == house_of[b]:
                y.append(f"Raja Yoga — lord of {k} ({a}) conjunct lord of {t} ({b})")
    for d in DUSTHANA:
        L = lord(d)
        if house_of[L] in DUSTHANA and house_of[L] != d:
            y.append(f"Viparita Raja Yoga — {d}th lord {L} placed in {house_of[L]}th house")
    for p in ["Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun", "Moon"]:
        if dignity(p, sign_of[p]) == "Debilitated":
            disp = SIGN_LORD[sign_of[p]]
            if house_of[disp] in KENDRA or house_of[EXALT_LORD(p)] in KENDRA:
                y.append(f"Neecha Bhanga (cancellation of debility) possible for {p}")
    if house_of["Mars"] in (1, 2, 4, 7, 8, 12):
        y.append(f"Mangal Dosha indication — Mars in house {house_of['Mars']} from Lagna (check cancellations)")
    r, k = sign_of["Rahu"], sign_of["Ketu"]
    others = [sign_of[p] for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]]
    arc = lambda s: (s - r) % 12
    if all(0 < arc(s) < 6 for s in others) or all(6 < arc(s) < 12 for s in others):
        y.append("Kaal Sarp Yoga indication — all planets hemmed between Rahu and Ketu")
    return list(dict.fromkeys(y))


def EXALT_LORD(planet: str) -> str:
    return SIGN_LORD[EXALT[planet]]


def vimshottari(moon_lon: float, birth_utc: dt.datetime, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    nak = nakshatra_of(moon_lon)
    span = 360 / 27
    frac_left = 1 - (moon_lon % span) / span
    start_lord = nak["lord"]
    i0 = DASHA_ORDER.index(start_lord)
    # back-date the first mahadasha start so the balance at birth is correct
    first_start = birth_utc - dt.timedelta(days=DASHA_YEARS[start_lord] * (1 - frac_left) * YEAR_DAYS)
    periods, t = [], first_start
    for k in range(9 * 2):  # two full cycles = 240 years, plenty
        md = DASHA_ORDER[(i0 + k) % 9]
        md_len = DASHA_YEARS[md] * YEAR_DAYS
        md_end = t + dt.timedelta(days=md_len)
        antars, a_t = [], t
        j0 = DASHA_ORDER.index(md)
        for j in range(9):
            ad = DASHA_ORDER[(j0 + j) % 9]
            ad_len = md_len * DASHA_YEARS[ad] / 120
            a_end = a_t + dt.timedelta(days=ad_len)
            antars.append({"lord": ad, "start": a_t.date().isoformat(), "end": a_end.date().isoformat(),
                           "current": a_t <= now < a_end})
            a_t = a_end
        if md_end > birth_utc:
            periods.append({"lord": md, "years": DASHA_YEARS[md],
                            "start": max(t, birth_utc).date().isoformat(), "end": md_end.date().isoformat(),
                            "current": t <= now < md_end, "antardashas": antars})
        t = md_end
        if t.year > birth_utc.year + 120:
            break
    cur_md = next((p for p in periods if p["current"]), None)
    cur_ad = next((a for a in cur_md["antardashas"] if a["current"]), None) if cur_md else None
    bal_years = DASHA_YEARS[start_lord] * frac_left
    return {
        "moon_nakshatra": nak,
        "balance_at_birth": f"{start_lord} {int(bal_years)}y {int((bal_years % 1) * 12)}m "
                            f"{int(((bal_years * 12) % 1) * 30)}d",
        "current": {"mahadasha": cur_md["lord"] if cur_md else None,
                    "antardasha": cur_ad["lord"] if cur_ad else None,
                    "md_end": cur_md["end"] if cur_md else None,
                    "ad_end": cur_ad["end"] if cur_ad else None},
        "mahadashas": periods,
    }


def compute_kundali(name: str, date: str, time: str, lat: float, lon: float, tz: str,
                    place: str = "", gender: str = "") -> dict:
    swe.set_sid_mode(swe.SIDM_LAHIRI)  # swisseph state is per-thread: set it on every call
    utc = to_utc(date, time, tz)
    jd = julday(utc)
    ayan = swe.get_ayanamsa_ut(jd)

    lon_of = {}
    speed = {}
    for nm, pid in PLANETS.items():
        xx, _ = swe.calc_ut(jd, pid, FLAGS)
        lon_of[nm], speed[nm] = xx[0] % 360, xx[3]
    lon_of["Ketu"], speed["Ketu"] = (lon_of["Rahu"] + 180) % 360, speed["Rahu"]

    # Ascendant + Sripati bhava cusps (sidereal)
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b"S", swe.FLG_SIDEREAL)
    asc = ascmc[0] % 360
    lagna_sign = int(asc // 30)

    sign_of = {p: int(l // 30) for p, l in lon_of.items()}
    house_of = {p: (s - lagna_sign) % 12 + 1 for p, s in sign_of.items()}
    house_of_with_lagna = dict(house_of, Lagna=1)

    planets = []
    sun_lon = lon_of["Sun"]
    combust_orb = {"Moon": 12, "Mars": 17, "Mercury": 14, "Jupiter": 11, "Venus": 10, "Saturn": 15}
    for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        L = lon_of[p]
        nk = nakshatra_of(L)
        sep = abs((L - sun_lon + 180) % 360 - 180)
        retro = speed[p] < 0 and p not in ("Rahu", "Ketu")
        orb = combust_orb.get(p)
        if p == "Mercury" and retro:
            orb = 12
        if p == "Venus" and retro:
            orb = 8
        planets.append({
            "name": p, "abbr": ABBR[p], "longitude": round(L, 4),
            "sign": sign_of[p], "sign_name": SIGNS[sign_of[p]], "degree": _fmt_deg(L),
            "house": house_of[p], "nakshatra": nk["name"], "pada": nk["pada"], "nak_lord": nk["lord"],
            "retrograde": retro, "combust": bool(orb and sep < orb),
            "dignity": dignity(p, sign_of[p]),
            "navamsha_sign": navamsha_sign(L), "navamsha_sign_name": SIGNS[navamsha_sign(L)],
            "navamsha_dignity": dignity(p, navamsha_sign(L)),
            "vargottama": navamsha_sign(L) == sign_of[p],
            "lord_of": [h for h in range(1, 13) if SIGN_LORD[(lagna_sign + h - 1) % 12] == p],
        })

    # --- D1
    d1 = _chart_payload(lagna_sign, sign_of, lon_of)
    # --- D9
    d9_lagna = navamsha_sign(asc)
    d9_sign_of = {p: navamsha_sign(l) for p, l in lon_of.items()}
    d9 = _chart_payload(d9_lagna, d9_sign_of)
    d9_house_of = {p: (s - d9_lagna) % 12 + 1 for p, s in d9_sign_of.items()}
    # --- Chandra
    moon_sign = sign_of["Moon"]
    chandra = _chart_payload(moon_sign, sign_of, lon_of)
    # --- Bhava Chalit: planet belongs to bhava whose [cusp_i, cusp_i+1) contains it
    cusp_list = [c % 360 for c in cusps[:12]]

    def bhava_of(L):
        for i in range(12):
            a, b = cusp_list[i], cusp_list[(i + 1) % 12]
            span = (b - a) % 360
            if (L - a) % 360 < span:
                return i + 1
        return 1
    chalit_house = {p: bhava_of(l) for p, l in lon_of.items()}
    chalit = {
        "lagna_sign": lagna_sign,
        "houses": [{"house": h, "sign": int(cusp_list[h - 1] // 30),
                    "sign_name": SIGNS[int(cusp_list[h - 1] // 30)],
                    "cusp": f"{SIGN_SHORT[int(cusp_list[h - 1] // 30)]} {_fmt_deg(cusp_list[h - 1])}",
                    "planets": [{"name": p, "abbr": ABBR[p], "deg": _fmt_deg(lon_of[p])}
                                for p, hh in chalit_house.items() if hh == h]}
                   for h in range(1, 13)],
        "shifted": [{"planet": p, "rashi_house": house_of[p], "bhava": chalit_house[p]}
                    for p in lon_of if house_of[p] != chalit_house[p]],
    }

    from knrao import d10_sign, d7_sign, knrao_layer
    d10_l, d7_l = d10_sign(asc), d7_sign(asc)
    d10 = _chart_payload(d10_l, {p: d10_sign(l) for p, l in lon_of.items()})
    d7 = _chart_payload(d7_l, {p: d7_sign(l) for p, l in lon_of.items()})
    d10_house_of = {p: (d10_sign(l) - d10_l) % 12 + 1 for p, l in lon_of.items()}
    d7_house_of = {p: (d7_sign(l) - d7_l) % 12 + 1 for p, l in lon_of.items()}
    for p in planets:
        p["d10_sign_name"], p["d10_house"] = SIGNS[d10_sign(lon_of[p["name"]])], d10_house_of[p["name"]]
        p["d7_sign_name"], p["d7_house"] = SIGNS[d7_sign(lon_of[p["name"]])], d7_house_of[p["name"]]
    kn = knrao_layer({}, lon_of, utc, asc)
    for p in planets:
        p["functional"] = kn["functional"][p["name"]]["nature"]

    lagna_nak = nakshatra_of(asc)
    return {
        "method": "K.N. Rao (Parashari + Jaimini), Lahiri ayanamsa",
        "knrao": kn,
        "input": {"name": name, "date": date, "time": time, "place": place, "lat": lat, "lon": lon,
                  "tz": tz, "gender": gender, "utc": utc.isoformat()},
        "ayanamsa": {"name": "Lahiri (Chitrapaksha)", "value": _fmt_deg(ayan) if ayan < 30 else f"{ayan:.4f}°",
                     "decimal": round(ayan, 6)},
        "lagna": {"sign": lagna_sign, "sign_name": SIGNS[lagna_sign], "degree": _fmt_deg(asc),
                  "longitude": round(asc, 4), "nakshatra": lagna_nak["name"], "pada": lagna_nak["pada"],
                  "lord": SIGN_LORD[lagna_sign], "navamsha_sign_name": SIGNS[d9_lagna]},
        "moon_sign": SIGNS[moon_sign],
        "sun_sign": SIGNS[sign_of["Sun"]],
        "planets": planets,
        "charts": {"D1": d1, "D9": d9, "Chandra": chandra, "Chalit": chalit, "D10": d10, "D7": d7},
        "varga_lagnas": {"D10": SIGNS[d10_l], "D7": SIGNS[d7_l]},
        "aspects": {"D1": vedic_aspects(house_of_with_lagna), "D9": vedic_aspects(dict(d9_house_of, Lagna=1))},
        "conjunctions": {
            "D1": [{"house": h, "planets": ps} for h, ps in _houses_from(lagna_sign, sign_of).items() if len(ps) > 1],
            "D9": [{"house": h, "planets": ps} for h, ps in _houses_from(d9_lagna, d9_sign_of).items() if len(ps) > 1],
        },
        "house_lords": [{"house": h, "sign": SIGNS[(lagna_sign + h - 1) % 12],
                         "lord": SIGN_LORD[(lagna_sign + h - 1) % 12],
                         "lord_in_house": house_of[SIGN_LORD[(lagna_sign + h - 1) % 12]],
                         "meaning": HOUSE_MEANING[h]} for h in range(1, 13)],
        "d9_house_lords": [{"house": h, "sign": SIGNS[(d9_lagna + h - 1) % 12],
                            "lord": SIGN_LORD[(d9_lagna + h - 1) % 12],
                            "lord_in_house": d9_house_of[SIGN_LORD[(d9_lagna + h - 1) % 12]]}
                           for h in range(1, 13)],
        "yogas": detect_yogas(house_of, sign_of, lagna_sign),
        "d9_yogas": detect_yogas(d9_house_of, d9_sign_of, d9_lagna),
        "dasha": vimshottari(lon_of["Moon"], utc),
    }


if __name__ == "__main__":
    import json
    k = compute_kundali("Test", "1990-01-15", "10:30:00", 28.6139, 77.2090, "Asia/Kolkata", "New Delhi")
    print(json.dumps({x: k[x] for x in ("lagna", "moon_sign", "ayanamsa", "yogas")}, indent=1))
    for p in k["planets"]:
        print(p["name"], p["sign_name"], p["degree"], "H", p["house"], p["nakshatra"], p["pada"],
              "R" if p["retrograde"] else "", "C" if p["combust"] else "", p["dignity"], "D9:", p["navamsha_sign_name"])
    print(k["dasha"]["balance_at_birth"], k["dasha"]["current"])
    print("Chalit shifts:", k["charts"]["Chalit"]["shifted"])
