"""
K.N. Rao methodology layer.

  * Functional nature of planets for the lagna (Laghu Parashari)
  * Jaimini 7 chara karakas, Karakamsha, Arudha Lagna (AL), Upapada (UL), rashi drishti
  * Jaimini Chara Dasha as taught by K.N. Rao
      - starts from the Lagna sign
      - direction from the 9th sign from Lagna: Ar/Ta/Ge/Li/Sc/Sg -> zodiacal, Cn/Le/Vi/Cp/Aq/Pi -> reverse
      - years = count from sign to its lord (in that sign's own direction) minus 1; lord in own sign = 12
      - NO +1/-1 for exalted/debilitated lords (K.N. Rao's convention)
      - Sc/Aq: stronger of the two co-lords
      - 12 antardashas of equal length, starting from the sign after the MD sign; the MD sign is last
      - second cycle = 12 - first-cycle years
  * Divisional charts D10 (Dashamsha - career) and D7 (Saptamsha - children)
  * Double transit of Jupiter and Saturn (K.N. Rao, "Ups and Downs in Career")
"""
from __future__ import annotations

import datetime as dt

import swisseph as swe

from astro_engine import (DEBIL, EXALT, FLAGS, SIGN_LORD, SIGNS, julday)

SAVYA = {0, 1, 2, 6, 7, 8}          # Ar Ta Ge Li Sc Sg  -> direct
MOVABLE, FIXED, DUAL = {0, 3, 6, 9}, {1, 4, 7, 10}, {2, 5, 8, 11}
NAT_BENEFIC = {"Jupiter", "Venus", "Mercury", "Moon"}
SEVEN = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
KARAKA_NAMES = [("AK", "Atmakaraka", "self, soul's desire"), ("AmK", "Amatyakaraka", "career, advisor"),
                ("BK", "Bhratrikaraka", "siblings, guru"), ("MK", "Matrikaraka", "mother, education"),
                ("PK", "Putrakaraka", "children, intelligence"), ("GK", "Gnatikaraka", "rivals, disease"),
                ("DK", "Darakaraka", "spouse")]


# ---------------- functional nature (Laghu Parashari)
def functional_nature(lagna_sign: int) -> dict:
    lords = {p: [h for h in range(1, 13) if SIGN_LORD[(lagna_sign + h - 1) % 12] == p] for p in SEVEN}
    out = {}
    for p, hs in lords.items():
        s = set(hs)
        kendra = s & {4, 7, 10}
        trikona = s & {5, 9}
        if kendra and trikona:
            nat, why = "Yogakaraka", f"owns kendra {sorted(kendra)} and trikona {sorted(trikona)}"
        elif 1 in s:
            nat, why = "Benefic", "lagna lord is always auspicious" + (" (8th lordship not harmful for lagna lord)" if 8 in s else "")
        elif trikona:
            nat, why = "Benefic", f"trikona lord {sorted(trikona)}" + (" though also owns a dusthana" if s & {6, 8, 12} else "")
        elif s & {3, 6, 11}:
            nat, why = "Malefic", f"owns trishadaya house(s) {sorted(s & {3, 6, 11})}" + (f" (also owns {sorted(s - {3, 6, 11})})" if s - {3, 6, 11} else "")
        elif 8 in s and p not in ("Sun", "Moon"):
            nat, why = "Malefic", "8th lord"
        elif kendra:
            if p in NAT_BENEFIC:
                nat, why = "Neutral (kendradhipati dosha)", f"natural benefic owning kendra {sorted(kendra)}"
            else:
                nat, why = "Neutral / good", f"natural malefic owning kendra {sorted(kendra)} loses maleficence"
        else:
            nat, why = "Neutral", f"owns {sorted(s)} — 2nd/12th lords give results according to their association"
        out[p] = {"nature": nat, "reason": why, "houses": hs}
    out["Rahu"] = {"nature": "By dispositor", "reason": "gives results of its sign lord, house and conjunctions", "houses": []}
    out["Ketu"] = dict(out["Rahu"])
    return out


# ---------------- varga charts
def d10_sign(lon: float) -> int:
    s, part = int(lon // 30), int((lon % 30) // 3)
    start = s if s % 2 == 0 else (s + 8) % 12
    return (start + part) % 12


def d7_sign(lon: float) -> int:
    s, part = int(lon // 30), int((lon % 30) // (30 / 7))
    start = s if s % 2 == 0 else (s + 6) % 12
    return (start + part) % 12


# ---------------- Jaimini
def chara_karakas(lon_of: dict) -> list[dict]:
    ranked = sorted(SEVEN, key=lambda p: lon_of[p] % 30, reverse=True)
    return [{"code": c, "name": n, "signifies": sig, "planet": p, "deg_in_sign": round(lon_of[p] % 30, 2)}
            for (c, n, sig), p in zip(KARAKA_NAMES, ranked)]


def rashi_drishti(sign: int) -> list[int]:
    if sign in MOVABLE:
        return [s for s in FIXED if s != (sign + 1) % 12]
    if sign in FIXED:
        return [s for s in MOVABLE if s != (sign - 1) % 12]
    return [s for s in DUAL if s != sign]


def _lord_sign_for(sign: int, sign_of: dict, lon_of: dict) -> int:
    """Sign of the (stronger) lord of `sign` — handles Sc (Mars/Ketu) and Aq (Saturn/Rahu)."""
    if sign not in (7, 10):
        return sign_of[SIGN_LORD[sign]]
    a, b = ("Mars", "Ketu") if sign == 7 else ("Saturn", "Rahu")
    sa, sb = sign_of[a], sign_of[b]
    if sa == sign and sb == sign:
        return sign
    if sa == sign:
        return sb
    if sb == sign:
        return sa
    count = lambda s: sum(1 for x in sign_of.values() if x == s)
    if count(sa) != count(sb):
        return sa if count(sa) > count(sb) else sb
    ex = lambda p, s: 1 if EXALT.get(p) == s else (-1 if DEBIL.get(p) == s else 0)
    if ex(a, sa) != ex(b, sb):
        return sa if ex(a, sa) > ex(b, sb) else sb
    return sa if lon_of[a] % 30 >= lon_of[b] % 30 else sb


def arudha(house_sign: int, sign_of: dict, lon_of: dict) -> int:
    lord_s = _lord_sign_for(house_sign, sign_of, lon_of)
    n = (lord_s - house_sign) % 12
    a = (lord_s + n) % 12
    if a == house_sign or a == (house_sign + 6) % 12:
        a = (a + 9) % 12
    return a


def chara_dasha_years(sign: int, sign_of: dict, lon_of: dict) -> int:
    lord_s = _lord_sign_for(sign, sign_of, lon_of)
    if lord_s == sign:
        return 12
    n = (lord_s - sign) % 12 + 1 if sign in SAVYA else (sign - lord_s) % 12 + 1
    return n - 1


def chara_dasha(lagna_sign: int, sign_of: dict, lon_of: dict, birth: dt.datetime, now: dt.datetime) -> dict:
    ninth = (lagna_sign + 8) % 12
    direct = ninth in SAVYA
    step = 1 if direct else -1
    seq = [(lagna_sign + step * i) % 12 for i in range(12)]
    first = {s: chara_dasha_years(s, sign_of, lon_of) for s in seq}
    periods, t = [], birth
    for cycle in (1, 2):
        for s in seq:
            yrs = first[s] if cycle == 1 else 12 - first[s]
            if yrs <= 0:
                continue
            end = t + dt.timedelta(days=yrs * 365.25)
            sub_step = 1 if s in SAVYA else -1
            subs, st = [], t
            for j in range(1, 13):
                ss = (s + sub_step * j) % 12
                se = st + dt.timedelta(days=yrs * 365.25 / 12)
                subs.append({"sign": ss, "sign_name": SIGNS[ss], "start": st.date().isoformat(),
                             "end": se.date().isoformat(), "current": st <= now < se})
                st = se
            periods.append({"sign": s, "sign_name": SIGNS[s], "years": yrs, "cycle": cycle,
                            "start": t.date().isoformat(), "end": end.date().isoformat(),
                            "current": t <= now < end, "antardashas": subs})
            t = end
            if t.year > birth.year + 110:
                break
    cur = next((p for p in periods if p["current"]), None)
    cur_ad = next((a for a in cur["antardashas"] if a["current"]), None) if cur else None
    return {"direction": "Direct (zodiacal)" if direct else "Reverse (anti-zodiacal)",
            "ninth_from_lagna": SIGNS[ninth],
            "current": {"mahadasha": cur["sign_name"] if cur else None, "md_end": cur["end"] if cur else None,
                        "antardasha": cur_ad["sign_name"] if cur_ad else None, "ad_end": cur_ad["end"] if cur_ad else None},
            "periods": periods}


# ---------------- double transit
def _influenced(sign: int, planet: str) -> set[int]:
    asp = {"Jupiter": [5, 7, 9], "Saturn": [3, 7, 10]}[planet]
    return {sign} | {(sign + n - 1) % 12 for n in asp}


def double_transit(lagna_sign: int, moon_sign: int, months: int = 36, start: dt.date | None = None) -> list[dict]:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    start = start or dt.date.today().replace(day=1)
    rows = []
    for m in range(months):
        y, mo = start.year + (start.month - 1 + m) // 12, (start.month - 1 + m) % 12 + 1
        jd = julday(dt.datetime(y, mo, 15, 12, tzinfo=dt.timezone.utc))
        ju = int((swe.calc_ut(jd, swe.JUPITER, FLAGS)[0][0] % 360) // 30)
        sa_xx = swe.calc_ut(jd, swe.SATURN, FLAGS)[0]
        sa = int((sa_xx[0] % 360) // 30)
        both = _influenced(ju, "Jupiter") & _influenced(sa, "Saturn")
        rows.append({"month": f"{y}-{mo:02d}", "jupiter": SIGNS[ju], "saturn": SIGNS[sa],
                     "houses_from_lagna": sorted((s - lagna_sign) % 12 + 1 for s in both),
                     "houses_from_moon": sorted((s - moon_sign) % 12 + 1 for s in both)})
    # compress consecutive identical months
    out = []
    for r in rows:
        key = (r["jupiter"], r["saturn"], tuple(r["houses_from_lagna"]))
        if out and out[-1]["_k"] == key:
            out[-1]["to"] = r["month"]
        else:
            out.append({**r, "from": r["month"], "to": r["month"], "_k": key})
    for o in out:
        o.pop("_k"); o.pop("month")
    return out


def knrao_layer(k: dict, lon_of: dict, birth_utc: dt.datetime, asc: float) -> dict:
    sign_of = {p: int(l // 30) for p, l in lon_of.items()}
    lagna_sign = int(asc // 30)
    now = dt.datetime.now(dt.timezone.utc)
    karakas = chara_karakas(lon_of)
    ak = karakas[0]["planet"]
    from astro_engine import navamsha_sign
    karakamsha = navamsha_sign(lon_of[ak])
    al = arudha(lagna_sign, sign_of, lon_of)
    ul = arudha((lagna_sign + 11) % 12, sign_of, lon_of)
    drishti = []
    for s in range(12):
        tgt = rashi_drishti(s)
        occ = [p for p, ps in sign_of.items() if ps == s]
        if occ:
            drishti.append({"from_sign": SIGNS[s], "planets": occ,
                            "aspects_signs": [SIGNS[t] for t in tgt],
                            "aspects_planets": [p for p, ps in sign_of.items() if ps in tgt]})
    return {
        "functional": functional_nature(lagna_sign),
        "karakas": karakas,
        "karakamsha": {"atmakaraka": ak, "sign": karakamsha, "sign_name": SIGNS[karakamsha]},
        "arudha_lagna": {"sign": al, "sign_name": SIGNS[al], "house": (al - lagna_sign) % 12 + 1},
        "upapada": {"sign": ul, "sign_name": SIGNS[ul], "house": (ul - lagna_sign) % 12 + 1},
        "rashi_drishti": drishti,
        "chara_dasha": chara_dasha(lagna_sign, sign_of, lon_of, birth_utc, now),
        "double_transit": double_transit(lagna_sign, sign_of["Moon"]),
    }
