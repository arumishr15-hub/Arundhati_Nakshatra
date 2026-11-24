"""
K.N. Rao-style interpretation engine (deterministic, no API needed).

Produces an in-depth, chart-specific Markdown reading:
  * Lagna & lagna lord; functional benefics/malefics (Laghu Parashari)
  * Planet-by-planet: dignity, D9 confirmation, functional role, lordship, bhavat-bhavam,
    nakshatra-lord, conjunctions, aspects received from functional benefics/malefics, strength score
  * House-by-house three-fold judgement: Bhava + Bhavesh + Karaka, Moon-chart cross-check
  * Yogas formed by real connections (conjunction / mutual aspect / exchange) + whether their dashas come
  * Jaimini: AK, Karakamsha, AmK, DK, Arudha Lagna, Upapada
  * Life areas with varga confirmation: career (D10), marriage (D9), children (D7), wealth, health
  * Dasha-by-dasha reading of antardashas (position of AD lord from MD lord)
  * Timing by K.N. Rao's triple check: Vimshottari + Chara Dasha + Jupiter–Saturn double transit
"""
from __future__ import annotations

import datetime as dt

import swisseph as swe

from astro_engine import (DEBIL, EXALT, FLAGS, SIGN_LORD, SIGNS, julday)

PL7 = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
ALL9 = PL7 + ["Rahu", "Ketu"]
NAT_BEN = {"Jupiter", "Venus", "Mercury", "Moon"}
KENDRA, TRIKONA, DUSTHANA, UPACHAYA = {1, 4, 7, 10}, {1, 5, 9}, {6, 8, 12}, {3, 6, 10, 11}
SPECIAL = {"Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10], "Rahu": [5, 7, 9], "Ketu": [5, 7, 9]}
ORD = lambda n: f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
short = lambda s: s.split(" (")[0]

HOUSE = {
    1: ("Tanu", "body, health, temperament, self-image, overall vitality and direction of life"),
    2: ("Dhana", "accumulated wealth, family, speech, food habits, early education, right eye"),
    3: ("Sahaja", "courage, initiative, younger siblings, communication, short travels, skills of the hands"),
    4: ("Sukha", "mother, home, inner peace, property, vehicles, formal education, emotional security"),
    5: ("Putra", "children, intelligence, discrimination, mantra, romance, speculation, past-life merit"),
    6: ("Ari", "enemies, litigation, debts, disease, service, competition, maternal uncle"),
    7: ("Kalatra", "spouse, marriage, partnerships, business dealings, public dealings, foreign stay"),
    8: ("Ayu", "longevity, sudden events, obstacles, inheritance, in-laws' wealth, research, occult, chronic illness"),
    9: ("Dharma", "fortune, father, guru, higher learning, religion, long journeys, grace"),
    10: ("Karma", "career, status, authority, actions in the world, government, reputation"),
    11: ("Labha", "gains, income, fulfilment of desires, elder siblings, friends and networks"),
    12: ("Vyaya", "expenses, losses, sleep, foreign lands, hospitals, isolation, moksha, bed pleasures"),
}
KARAKA = {1: ["Sun"], 2: ["Jupiter"], 3: ["Mars"], 4: ["Moon"], 5: ["Jupiter"], 6: ["Mars", "Saturn"],
          7: ["Venus"], 8: ["Saturn"], 9: ["Jupiter", "Sun"], 10: ["Sun", "Saturn"], 11: ["Jupiter"], 12: ["Saturn"]}
PLANET_SIG = {
    "Sun": "soul, father, authority, government, vitality, self-confidence",
    "Moon": "mind, mother, emotions, public, comforts, fluids",
    "Mars": "energy, courage, brothers, land, surgery, police/army, engineering",
    "Mercury": "intellect, speech, trade, writing, accounts, communication, youth",
    "Jupiter": "wisdom, guru, children, dharma, wealth, law, teaching, husband (for women)",
    "Venus": "spouse/relationships, arts, luxury, vehicles, beauty, comforts",
    "Saturn": "discipline, delay, labour, longevity, service, masses, endurance",
    "Rahu": "obsession, foreign, unconventional, technology, sudden rise, illusion",
    "Ketu": "detachment, spirituality, research, losses that liberate, past-life skills",
}
PROFESSION = {
    "Sun": "government, administration, politics, medicine, leadership roles",
    "Moon": "public-facing work, hospitality, nursing, food, liquids, psychology",
    "Mars": "engineering, defence/police, surgery, real estate, sports, technical work",
    "Mercury": "commerce, accounts, writing, media, IT, teaching languages, consulting",
    "Jupiter": "teaching, law, finance/banking, advisory, priesthood, counselling",
    "Venus": "arts, design, fashion, beauty, entertainment, luxury goods, hospitality",
    "Saturn": "service sector, labour/industry, administration, mining, judiciary, long-term institutions",
    "Rahu": "technology, foreign companies, aviation, research, unconventional fields, politics",
    "Ketu": "research, occult/astrology, spirituality, coding, investigative work",
}
SIGN_TRAIT = {
    0: "pioneering, quick, courageous, impatient", 1: "steady, sensual, practical, possessive",
    2: "communicative, curious, versatile, restless", 3: "emotional, nurturing, protective, moody",
    4: "regal, generous, proud, authoritative", 5: "analytical, service-minded, critical, precise",
    6: "balanced, diplomatic, aesthetic, partnership-oriented", 7: "intense, secretive, determined, transformative",
    8: "philosophical, principled, optimistic, outspoken", 9: "ambitious, disciplined, practical, reserved",
    10: "humanitarian, independent, unconventional, detached", 11: "compassionate, intuitive, spiritual, dreamy",
}
BODY = {0: "head", 1: "face/throat", 2: "shoulders/arms/lungs", 3: "chest/stomach", 4: "heart/upper back",
        5: "intestines/digestion", 6: "kidneys/lower back", 7: "reproductive organs", 8: "hips/thighs/liver",
        9: "knees/bones/joints", 10: "calves/circulation", 11: "feet/lymphatic system"}
AK_MEANING = {
    "Sun": "the soul seeks recognition and must learn humility and to drop ego",
    "Moon": "the soul's lessons come through emotions, care and attachment; must learn equanimity",
    "Mars": "the soul must learn to channel aggression into disciplined courage",
    "Mercury": "the soul's lessons come through speech and intellect; must use words truthfully",
    "Jupiter": "the soul must honour gurus, dharma and children; lessons through wisdom",
    "Venus": "the soul's lessons come through relationships and desires; must learn purity in pleasure",
    "Saturn": "the soul must learn patience and service; lessons through hardship and responsibility",
}


DK_TRAIT = {"Sun": "dignity, self-confidence and a strong, authoritative presence",
            "Moon": "sensitivity, care and an emotional, nurturing nature",
            "Mars": "energy, courage and a direct, assertive temperament",
            "Mercury": "intelligence, wit and a youthful, communicative nature",
            "Jupiter": "wisdom, principles and a learned, guiding nature",
            "Venus": "charm, artistic taste and a refined, affectionate nature",
            "Saturn": "maturity, seriousness and a disciplined, responsible nature (often older or reserved)"}


class Chart:
    def __init__(self, k: dict):
        self.k = k
        self.lagna = k["lagna"]["sign"]
        self.P = {p["name"]: p for p in k["planets"]}
        self.house = {p: v["house"] for p, v in self.P.items()}
        self.sign = {p: v["sign"] for p, v in self.P.items()}
        self.fn = {p: v["nature"] for p, v in k["knrao"]["functional"].items()}
        self.lord = {h: SIGN_LORD[(self.lagna + h - 1) % 12] for h in range(1, 13)}
        self.owns = {p: [h for h in range(1, 13) if self.lord[h] == p] for p in PL7}
        self.owns["Rahu"] = self.owns["Ketu"] = []
        self.gender = (k["input"].get("gender") or "").lower()
        # aspects on houses
        self.asp_on = {h: [] for h in range(1, 13)}
        for p in ALL9:
            for n in SPECIAL.get(p, [7]):
                self.asp_on[(self.house[p] + n - 2) % 12 + 1].append(p)
        self.occ = {h: [p for p in ALL9 if self.house[p] == h] for h in range(1, 13)}
        self.birth = dt.date.fromisoformat(k["input"]["date"])

    # ---------------- helpers
    def eff_fn(self, p):  # Rahu/Ketu act as their dispositor
        if p in ("Rahu", "Ketu"):
            d = SIGN_LORD[self.sign[p]]
            return self.fn.get(d, "Neutral")
        return self.fn[p]

    def is_fb(self, p):
        """Functional benefic as an *influence* (nodes never count as benefic influences)."""
        return p not in ("Rahu", "Ketu") and self.eff_fn(p) in ("Benefic", "Yogakaraka")

    def is_fm(self, p):
        """Functional malefic influence; Rahu/Ketu conjunctions and aspects afflict."""
        return p in ("Rahu", "Ketu") or self.eff_fn(p) == "Malefic"

    def role(self, p):
        if p in ("Rahu", "Ketu"):
            d = SIGN_LORD[self.sign[p]]
            return f"a node acting for {d} ({self.fn[d].lower()})"
        return self.fn[p]

    def aspects(self, a, b):
        return self.house[b] in [(self.house[a] + n - 2) % 12 + 1 for n in SPECIAL.get(a, [7])]

    def connected(self, a, b):
        if a == b:
            return None
        if self.house[a] == self.house[b]:
            return "conjunction"
        if a in PL7 and b in PL7 and SIGN_LORD[self.sign[a]] == b and SIGN_LORD[self.sign[b]] == a:
            return "exchange (parivartana)"
        if self.aspects(a, b) and self.aspects(b, a):
            return "mutual aspect"
        return None

    def neecha_bhanga(self, p):
        if p not in PL7 or self.P[p]["dignity"] != "Debilitated":
            return []
        r = []
        disp = SIGN_LORD[self.sign[p]]
        ex_lord = SIGN_LORD[EXALT[p]]
        moon_h = self.house["Moon"]
        for who, role in ((disp, "its dispositor"), (ex_lord, "lord of its exaltation sign")):
            if self.house[who] in KENDRA:
                r.append(f"{role} {who} is in a kendra from Lagna")
            if ((self.house[who] - moon_h) % 12) in (0, 3, 6, 9):
                r.append(f"{role} {who} is in a kendra from the Moon")
        if self.aspects(disp, p) or self.house[disp] == self.house[p]:
            r.append(f"its dispositor {disp} aspects/joins it")
        if self.P[p]["navamsha_dignity"] in ("Exalted", "Own sign"):
            r.append(f"it is {self.P[p]['navamsha_dignity'].lower()} in Navamsha")
        return list(dict.fromkeys(r))

    def strength(self, p) -> tuple[float, list[str]]:
        v = self.P[p]
        s, why = 0.0, []
        dig = {"Exalted": 3, "Moolatrikona": 2.5, "Own sign": 2, "Friendly sign": 1, "Neutral sign": 0,
               "Enemy sign": -1, "Debilitated": -3, "—": 0}[v["dignity"]]
        if dig:
            s += dig; why.append(f"{v['dignity'].lower()} in D1 ({'+' if dig > 0 else ''}{dig})")
        nb = self.neecha_bhanga(p)
        if nb:
            s += 2.5; why.append("neecha bhanga — debility cancelled (+2.5)")
        d9 = {"Exalted": 1.5, "Moolatrikona": 1, "Own sign": 1, "Debilitated": -1.5}.get(v["navamsha_dignity"], 0)
        if d9:
            s += d9; why.append(f"{v['navamsha_dignity'].lower()} in D9 ({'+' if d9 > 0 else ''}{d9})")
        if v["vargottama"]:
            s += 1; why.append("vargottama (+1)")
        if v["combust"]:
            s -= 1.5; why.append("combust (−1.5)")
        if v["retrograde"]:
            s += 0.5; why.append("retrograde — cheshta bala (+0.5)")
        h = v["house"]
        if h in KENDRA | TRIKONA:
            s += 1; why.append(f"in {'kendra' if h in KENDRA else 'trikona'} ({ORD(h)}) (+1)")
        elif h in DUSTHANA:
            s -= 1; why.append(f"in dusthana {ORD(h)} (−1)")
        for q in ALL9:
            if q == p:
                continue
            if self.house[q] == h or self.aspects(q, p):
                how = "joined" if self.house[q] == h else "aspected"
                if self.is_fb(q):
                    s += 0.5; why.append(f"{how} by functional benefic {q} (+0.5)")
                elif self.is_fm(q):
                    s -= 0.5; why.append(f"{how} by {'node' if q in ('Rahu', 'Ketu') else 'functional malefic'} {q} (−0.5)")
        return round(s, 1), why

    @staticmethod
    def verdict(s):
        return "very strong" if s >= 4 else "strong" if s >= 2 else "moderate" if s >= 0 else "weak" if s >= -2 else "very weak"


# ======================================================================
def bhavat(c: Chart, own: int, placed: int) -> str:
    n = (placed - own) % 12 + 1
    if n == 1:
        return "in its own house — protects and strengthens that house"
    if n in (6, 8, 12):
        return f"in the {ORD(n)} from its own house (bhavat-bhavam) — significations of house {own} suffer obstacles, delays or losses"
    if n in (5, 9):
        return f"in the {ORD(n)} from its own house — trinal, supportive of house {own}"
    if n in (4, 7, 10):
        return f"in the {ORD(n)} from its own house — angular, keeps house {own} active"
    return f"in the {ORD(n)} from its own house"


def lord_in_house(lh: int, ph: int) -> str:
    a, b = HOUSE[lh][1].split(",")[0], HOUSE[ph][1].split(",")[0]
    if lh == ph:
        return (f"the lord sits in its own {ORD(lh)} house — it protects it" +
                ("; a dusthana lord in its own house keeps enemies, debts and disease under control" if lh in DUSTHANA else "; matters of this house are self-sustaining and strong"))
    if ph in DUSTHANA and lh in DUSTHANA:
        return f"dusthana lord in a dusthana — Viparita Raja Yoga tendency: troubles of the {ORD(lh)} are destroyed; rise after adversity"
    if ph in DUSTHANA:
        return f"matters of the {ORD(lh)} ({a}) are linked with the {ORD(ph)} — struggle, debt, illness, delay or loss around them unless the lord is strong"
    if ph in KENDRA | TRIKONA:
        return f"matters of the {ORD(lh)} ({a}) are supported and flourish through the {ORD(ph)} ({b})"
    if ph in (3, 11):
        return f"matters of the {ORD(lh)} ({a}) grow with effort and time (upachaya {ORD(ph)})"
    return f"matters of the {ORD(lh)} ({a}) are channelled into the {ORD(ph)} ({b})"


# ======================================================================
def section_lagna(c: Chart) -> list[str]:
    k, L = c.k, []
    lg = k["lagna"]
    ll = lg["lord"]
    s, why = c.strength(ll)
    L += ["## 1. Lagna, Lagna Lord and Functional Nature",
          f"**{lg['sign_name']} Lagna** rising at {lg['degree']} in **{lg['nakshatra']}** pada {lg['pada']}. "
          f"{short(lg['sign_name'])} gives a {SIGN_TRAIT[lg['sign']]} temperament. "
          f"The Moon is in {k['moon_sign']} and the Sun in {k['sun_sign']}."]
    occ = c.occ[1]
    if occ:
        L.append(f"Planets in the Lagna: **{', '.join(occ)}** — they colour the personality directly: " +
                 "; ".join(f"{p} adds {PLANET_SIG[p].split(',')[0]}" for p in occ) + ".")
    if c.asp_on[1]:
        L.append("Aspects on the Lagna: " + ", ".join(
            f"{p} ({'functional benefic' if c.is_fb(p) else 'functional malefic' if c.is_fm(p) else 'neutral'})" for p in c.asp_on[1]) + ".")
    L.append(f"**Lagna lord {ll}** is in the {ORD(c.house[ll])} house in {c.P[ll]['sign_name']} ({c.P[ll]['dignity'].lower()}); "
             f"strength **{c.verdict(s)}** (score {s}: {', '.join(why) or 'no special factors'}). "
             f"{lord_in_house(1, c.house[ll]).capitalize()}.")
    L.append("\n**Functional benefics and malefics for this Lagna** (K.N. Rao always starts here):")
    for p, v in k["knrao"]["functional"].items():
        L.append(f"- **{p}** — {v['nature']}: {v['reason']}.")
    yk = [p for p, v in c.fn.items() if v == "Yogakaraka"]
    if yk:
        L.append(f"\n**{', '.join(yk)}** is the yogakaraka — its dasha and its strength decide the rise in life.")
    return L


def section_planets(c: Chart) -> list[str]:
    L = ["## 2. Planet-by-Planet Analysis"]
    for p in ALL9:
        v = c.P[p]
        s, why = c.strength(p)
        lines = [f"### {p} — {short(v['sign_name'])}, {ORD(v['house'])} house · {c.role(p)} · {c.verdict(s)}"]
        lines.append(f"Placed at {v['degree']} in {v['nakshatra']} pada {v['pada']} (nakshatra lord **{v['nak_lord']}**, "
                     f"in the {ORD(c.house[v['nak_lord']])} house) — {p} will also give results of {v['nak_lord']}'s house.")
        if p in PL7 and c.owns[p]:
            for h in c.owns[p]:
                lines.append(f"- As **lord of the {ORD(h)}** ({HOUSE[h][1]}): {lord_in_house(h, v['house'])}; it is {bhavat(c, h, v['house'])}.")
        else:
            d = SIGN_LORD[v["sign"]]
            lines.append(f"- As a node, {p} acts like its dispositor **{d}** (lord of {', '.join(ORD(h) for h in c.owns[d])}, in the {ORD(c.house[d])}) "
                         f"and like the planets it joins. It amplifies {HOUSE[v['house']][1].split(',')[0]} matters with {PLANET_SIG[p].split(',')[0]} and {PLANET_SIG[p].split(',')[1].strip()}.")
        nb = c.neecha_bhanga(p)
        if v["dignity"] == "Debilitated" and p in PL7:
            lines.append(f"- **Debilitated**" + (f", but **neecha bhanga** operates: {'; '.join(nb)}. Results start weak and improve markedly, often after struggle." if nb else
                                                  " with no cancellation — its significations need conscious support."))
        if v["combust"]:
            lines.append(f"- **Combust** — {p}'s significations ({PLANET_SIG[p].split(',')[0]}) are overshadowed by the Sun's ego/authority themes.")
        if v["retrograde"]:
            lines.append(f"- **Retrograde** — results are revisited, delayed or internalised; strong effort brings them back.")
        if v["vargottama"]:
            lines.append(f"- **Vargottama** — same sign in D1 and D9: promises are reliable and stable.")
        d9 = v["navamsha_dignity"]
        if d9 != v["dignity"]:
            change = ("gains inner strength" if d9 in ("Exalted", "Own sign", "Moolatrikona") else
                      "loses inner strength" if d9 == "Debilitated" else "is of ordinary inner strength")
            lines.append(f"- In Navamsha it is in {short(v['navamsha_sign_name'])} ({d9.lower()}) — {change}; D9 decides how fully D1 promises fructify.")
        conj = [q for q in ALL9 if q != p and c.house[q] == v["house"]]
        if conj:
            lines.append(f"- **Conjunct** {', '.join(conj)}: " + "; ".join(
                f"{q} ({'functional benefic' if c.is_fb(q) else 'malefic influence' if c.is_fm(q) else 'neutral'})" for q in conj) + ".")
        asp_by = [q for q in ALL9 if q != p and c.aspects(q, p)]
        if asp_by:
            lines.append(f"- **Aspected by** {', '.join(asp_by)}.")
        gives = [(c.house[p] + n - 2) % 12 + 1 for n in SPECIAL.get(p, [7])]
        lines.append(f"- **Aspects** houses {', '.join(ORD(h) for h in gives)}" +
                     (f" (and planets {', '.join(q for q in ALL9 if c.house[q] in gives and q != p)})" if any(c.house[q] in gives and q != p for q in ALL9) else "") + ".")
        lines.append(f"- Strength assessment: {'; '.join(why) or 'no strong modifiers'} → **{c.verdict(s)}**.")
        L += lines
    return L


def section_houses(c: Chart) -> list[str]:
    L = ["## 3. House-by-House Analysis (Bhava + Bhavesh + Karaka)"]
    moon = c.sign["Moon"]
    for h in range(1, 13):
        name, sig = HOUSE[h]
        sign = (c.lagna + h - 1) % 12
        lord = c.lord[h]
        ls, _ = c.strength(lord)
        score = 0.0
        pts = []
        for p in c.occ[h]:
            if c.is_fb(p):
                score += 1; pts.append(f"functional benefic {p} occupies it (+)")
            elif c.is_fm(p):
                score -= 1; pts.append(f"{'node' if p in ('Rahu', 'Ketu') else 'functional malefic'} {p} occupies it (−)")
            else:
                pts.append(f"{p} occupies it")
        for p in c.asp_on[h]:
            if p in c.occ[h]:
                continue
            if c.is_fb(p):
                score += 0.5; pts.append(f"aspected by functional benefic {p} (+)")
            elif c.is_fm(p):
                score -= 0.5; pts.append(f"aspected by {'node' if p in ('Rahu', 'Ketu') else 'functional malefic'} {p} (−)")
        lh = c.house[lord]
        score += 1 if ls >= 2 else -1 if ls < 0 else 0
        pts.append(f"its lord {lord} is in the {ORD(lh)} ({c.verdict(ls)}) — {bhavat(c, h, lh)}")
        if lh in DUSTHANA and h not in DUSTHANA:
            score -= 1
        elif lh in KENDRA | TRIKONA:
            score += 0.5
        kar = KARAKA[h]
        if h == 7 and "female" in c.gender:
            kar = ["Jupiter", "Venus"]
        ks = [(x, c.strength(x)[0]) for x in kar]
        pts.append("karaka " + ", ".join(f"{x} is {c.verdict(s)}" for x, s in ks))
        score += sum(0.5 if s >= 2 else -0.5 if s < 0 else 0 for _, s in ks)
        from_moon = (sign - moon) % 12 + 1
        verdict = "strong and well-supported" if score >= 2 else "good" if score >= 0.5 else "mixed" if score > -1 else "afflicted — needs care"
        L.append(f"### {ORD(h)} house — {name} ({short(SIGNS[sign])}) · **{verdict}**")
        L.append(f"_Signifies {sig}._")
        L.append(f"- " + "\n- ".join(pts))
        L.append(f"- From the Moon this sign is the {ORD(from_moon)} house — read together for the mind's experience of it.")
        if h == 7:
            L.append(f"- Navamsha check: D9 7th lord is {c.k['d9_house_lords'][6]['lord']} in D9 {ORD(c.k['d9_house_lords'][6]['lord_in_house'])}.")
        if h == 10:
            d10 = c.P[lord]["d10_house"]
            L.append(f"- Dashamsha check: the D1 10th lord {lord} falls in the {ORD(d10)} of D10 — "
                     + ("confirms career strength." if d10 in KENDRA | TRIKONA | {11} else "career results need extra effort." if d10 in DUSTHANA else "moderate confirmation."))
        if h == 5:
            d7 = c.P[lord]["d7_house"]
            L.append(f"- Saptamsha check: the D1 5th lord {lord} falls in the {ORD(d7)} of D7 — "
                     + ("supports progeny." if d7 in KENDRA | TRIKONA | {11} else "progeny may come with delay or effort." if d7 in DUSTHANA else "moderate support."))
    return L


def find_yogas(c: Chart) -> list[dict]:
    Y = []
    ken = [h for h in (1, 4, 7, 10)]
    tri = [h for h in (1, 5, 9)]
    seen = set()
    for kh in ken:
        for th in tri:
            a, b = c.lord[kh], c.lord[th]
            if a == b:
                if kh != 1 and th != 1:
                    Y.append({"name": "Raja Yoga (single planet)", "planets": [a], "detail": f"{a} owns both kendra {kh} and trikona {th} — yogakaraka"})
                continue
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            how = c.connected(a, b)
            if how:
                seen.add(key)
                Y.append({"name": "Raja Yoga", "planets": [a, b], "detail": f"lord of {kh} ({a}) and lord of {th} ({b}) by {how}"})
    for wh in (2, 11):
        for th in (1, 5, 9):
            a, b = c.lord[wh], c.lord[th]
            if a != b and (how := c.connected(a, b)):
                Y.append({"name": "Dhana Yoga", "planets": [a, b], "detail": f"wealth lord of {wh} ({a}) with lord of {th} ({b}) by {how}"})
    for d in (6, 8, 12):
        L = c.lord[d]
        if c.house[L] in DUSTHANA and c.house[L] != d:
            Y.append({"name": "Viparita Raja Yoga", "planets": [L], "detail": f"{ORD(d)} lord {L} in the {ORD(c.house[L])}"})
    for p in PL7:
        if c.neecha_bhanga(p):
            Y.append({"name": "Neecha Bhanga Raja Yoga", "planets": [p], "detail": f"{p}: " + "; ".join(c.neecha_bhanga(p))})
    pm = {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa", "Venus": "Malavya", "Saturn": "Shasha"}
    for p, n in pm.items():
        if c.house[p] in KENDRA and c.P[p]["dignity"] in ("Exalted", "Own sign", "Moolatrikona"):
            Y.append({"name": f"{n} Mahapurusha Yoga", "planets": [p], "detail": f"{p} {c.P[p]['dignity'].lower()} in the {ORD(c.house[p])}"})
    mh, jh = c.house["Moon"], c.house["Jupiter"]
    if (jh - mh) % 12 in (0, 3, 6, 9):
        Y.append({"name": "Gaja Kesari Yoga", "planets": ["Jupiter", "Moon"], "detail": f"Jupiter in a kendra from the Moon"})
    if c.house["Sun"] == c.house["Mercury"]:
        Y.append({"name": "Budha-Aditya Yoga", "planets": ["Sun", "Mercury"], "detail": "Sun and Mercury together"})
    around = [p for p in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")]
    s2 = [p for p in around if c.house[p] == mh % 12 + 1]
    s12 = [p for p in around if c.house[p] == (mh - 2) % 12 + 1]
    if s2 and s12:
        Y.append({"name": "Durudhara Yoga", "planets": s2 + s12, "detail": "planets on both sides of the Moon"})
    elif s2:
        Y.append({"name": "Sunapha Yoga", "planets": s2, "detail": "planets in 2nd from Moon"})
    elif s12:
        Y.append({"name": "Anapha Yoga", "planets": s12, "detail": "planets in 12th from Moon"})
    elif not any(c.house[p] == mh for p in around):
        Y.append({"name": "Kemadruma tendency", "planets": ["Moon"], "detail": "no planets around the Moon (check cancellations: kendras from lagna/Moon)"})
    for p in PL7:
        q = SIGN_LORD[c.sign[p]]
        if q != p and q in PL7 and SIGN_LORD[c.sign[q]] == p and p < q:
            Y.append({"name": "Parivartana (exchange)", "planets": [p, q], "detail": f"{p} in {q}'s sign and {q} in {p}'s sign — houses {c.house[p]} and {c.house[q]} are fused"})
    if c.house["Mars"] in (1, 2, 4, 7, 8, 12):
        canc = []
        if c.P["Mars"]["dignity"] in ("Own sign", "Exalted"):
            canc.append("Mars in own/exalted sign")
        if c.sign["Mars"] in (3, 4) and c.house["Mars"] in (2, 4, 7, 8, 12):
            canc.append("Mars in Cancer/Leo")
        if c.aspects("Jupiter", "Mars") or c.house["Jupiter"] == c.house["Mars"]:
            canc.append("Jupiter's influence on Mars")
        Y.append({"name": "Mangal Dosha", "planets": ["Mars"], "detail": f"Mars in the {ORD(c.house['Mars'])}" + (f"; cancelled/reduced by {', '.join(canc)}" if canc else "; match with a similar chart")})
    return Y


def vim_md_ages(c: Chart) -> dict:
    out = {}
    for m in c.k["dasha"]["mahadashas"]:
        a = dt.date.fromisoformat(m["start"]).year - c.birth.year
        b = dt.date.fromisoformat(m["end"]).year - c.birth.year
        out.setdefault(m["lord"], (a, b, m["start"], m["end"]))
    return out


def section_yogas(c: Chart) -> list[str]:
    L = ["## 4. Yogas and Doshas — and whether their dashas come",
         "K.N. Rao's rule: a yoga gives results only in the dasha/antardasha of the planets forming it. Ages below are Vimshottari mahadasha spans in this life."]
    ages = vim_md_ages(c)
    ys = find_yogas(c)
    if not ys:
        L.append("No major classical yogas by strict connection; results come mainly from house lords and dashas.")
    for y in ys:
        when = [f"{p} MD age {ages[p][0]}–{ages[p][1]} ({ages[p][2][:4]}–{ages[p][3][:4]})" for p in y["planets"] if p in ages and ages[p][1] > 0 and ages[p][0] < 95]
        L.append(f"- **{y['name']}** — {y['detail']}. " + (f"Activates in: {'; '.join(when)}." if when else "Its mahadashas do not fall in a normal lifespan — mainly works through antardashas."))
    return L


def section_jaimini(c: Chart) -> list[str]:
    kn = c.k["knrao"]
    kar = {x["code"]: x["planet"] for x in kn["karakas"]}
    ak = kar["AK"]
    L = ["## 5. Jaimini Indications"]
    L.append(f"- **Atmakaraka {ak}** — {AK_MEANING.get(ak, '')}. It sits in the {ORD(c.house[ak])} house.")
    km = kn["karakamsha"]["sign"]
    in_km = [p for p in ALL9 if c.P[p]["navamsha_sign"] == km]
    L.append(f"- **Karakamsha** {short(kn['karakamsha']['sign_name'])}" + (f" holds (in D9) {', '.join(in_km)} — " + "; ".join(f"{p}: {PLANET_SIG[p].split(',')[0]}" for p in in_km) if in_km else "") + ".")
    amk = kar["AmK"]
    L.append(f"- **Amatyakaraka {amk}** (career) is in the {ORD(c.house[amk])} and in the {ORD(c.P[amk]['d10_house'])} of D10 — suggests {PROFESSION[amk]}.")
    dk = kar["DK"]
    L.append(f"- **Darakaraka {dk}** (spouse) — spouse shows {PLANET_SIG[dk].split(',')[0]} qualities; DK is {c.verdict(c.strength(dk)[0])} and in {short(c.P[dk]['navamsha_sign_name'])} in D9.")
    al, ul = kn["arudha_lagna"], kn["upapada"]
    al_occ = [p for p in ALL9 if c.sign[p] == al["sign"]]
    L.append(f"- **Arudha Lagna** in {short(al['sign_name'])} ({ORD(al['house'])} house) — the world's image of the native" + (f"; {', '.join(al_occ)} here shape that image" if al_occ else "") + ".")
    ul2 = (ul["sign"] + 1) % 12
    ul2_occ = [p for p in ALL9 if c.sign[p] == ul2]
    L.append(f"- **Upapada** in {short(ul['sign_name'])} ({ORD(ul['house'])} house); 2nd from UL ({short(SIGNS[ul2])}) " +
             (f"has {', '.join(ul2_occ)} — " + ("malefic influence can strain continuity of marriage." if any(p in ("Saturn", "Mars", "Rahu", "Ketu", "Sun") for p in ul2_occ) else "benefic influence sustains marriage.") if ul2_occ else "is empty — judged by its lord.") )
    return L


def section_life(c: Chart) -> list[str]:
    k = c.k
    L = ["## 6. Life Areas (D1 promise → varga confirmation)"]
    # career
    l10 = c.lord[10]
    infl10 = sorted(set(c.occ[10] + c.asp_on[10] + [l10]))
    d10 = c.P[l10]["d10_house"]
    L.append(f"### Career\nThe 10th ({short(SIGNS[(c.lagna + 9) % 12])}) is influenced by {', '.join(infl10)}; its lord {l10} is in the {ORD(c.house[l10])} "
             f"({c.verdict(c.strength(l10)[0])}). In Dashamsha (lagna {short(k['varga_lagnas']['D10'])}) the 10th lord falls in the {ORD(d10)}. "
             f"Indicated fields: " + "; ".join(f"**{p}** → {PROFESSION[p]}" for p in infl10[:4]) + ". "
             f"Saturn (karma) is {c.verdict(c.strength('Saturn')[0])}, Sun (authority) {c.verdict(c.strength('Sun')[0])}.")
    # marriage
    l7 = c.lord[7]
    kar7 = "Jupiter" if "female" in c.gender else "Venus"
    d9_7 = k["d9_house_lords"][6]
    L.append(f"### Marriage\nThe 7th ({short(SIGNS[(c.lagna + 6) % 12])}) has {', '.join(c.occ[7]) or 'no planets'} and receives aspects from {', '.join(c.asp_on[7]) or 'none'}. "
             f"7th lord {l7} is in the {ORD(c.house[l7])} ({c.verdict(c.strength(l7)[0])}); {bhavat(c, 7, c.house[l7])}. "
             f"Karaka {kar7} is {c.verdict(c.strength(kar7)[0])}; Venus is {c.verdict(c.strength('Venus')[0])}. "
             f"Navamsha 7th lord {d9_7['lord']} is in D9 {ORD(d9_7['lord_in_house'])} — "
             + ("confirms a supportive marriage." if d9_7['lord_in_house'] in KENDRA | TRIKONA | {11} else "marriage needs maturity and adjustment." if d9_7['lord_in_house'] in DUSTHANA else "moderate confirmation."))
    # children
    l5 = c.lord[5]
    L.append(f"### Children\n5th lord {l5} in the {ORD(c.house[l5])} ({c.verdict(c.strength(l5)[0])}); Jupiter (putrakaraka) is {c.verdict(c.strength('Jupiter')[0])}; "
             f"in Saptamsha (lagna {short(k['varga_lagnas']['D7'])}) the 5th lord falls in the {ORD(c.P[l5]['d7_house'])}. "
             f"Occupants of the 5th: {', '.join(c.occ[5]) or 'none'}.")
    # wealth
    l2, l11 = c.lord[2], c.lord[11]
    L.append(f"### Wealth\n2nd lord {l2} in the {ORD(c.house[l2])} ({c.verdict(c.strength(l2)[0])}) and 11th lord {l11} in the {ORD(c.house[l11])} ({c.verdict(c.strength(l11)[0])}). "
             f"{lord_in_house(2, c.house[l2]).capitalize()}. {lord_in_house(11, c.house[l11]).capitalize()}.")
    # health
    l6, l8 = c.lord[6], c.lord[8]
    weak_signs = sorted({c.sign[p] for p in ALL9 if c.is_fm(p) and c.house[p] in DUSTHANA | {1}})
    L.append(f"### Health tendencies\nLagna lord {c.lord[1]} is {c.verdict(c.strength(c.lord[1])[0])}; 6th lord {l6} in the {ORD(c.house[l6])}, 8th lord {l8} in the {ORD(c.house[l8])}. "
             + (f"Areas to watch (signs holding functional malefics in sensitive houses): {', '.join(BODY[s] for s in weak_signs)}. " if weak_signs else "")
             + "These are tendencies only — consult a doctor for any health concern.")
    return L


def section_dashas(c: Chart) -> list[str]:
    k = c.k
    L = ["## 7. Dasha-by-Dasha Reading (Vimshottari)",
         "Each antardasha is read from (a) the AD lord's functional nature and houses, and (b) its position from the mahadasha lord — "
         "6/8/12 from the MD lord brings friction, kendra/trikona brings support (K.N. Rao's practice)."]
    today = dt.date.today().isoformat()
    shown = 0
    for m in k["dasha"]["mahadashas"]:
        if m["end"] < today or shown >= 2:
            continue
        shown += 1
        md = m["lord"]
        L.append(f"### {md} Mahadasha ({m['start']} → {m['end']})")
        L.append(f"{md} is {c.role(md).lower()} for this lagna, owns {', '.join(ORD(h) for h in c.owns[md]) or 'no house (node)'}, sits in the {ORD(c.house[md])} "
                 f"and is {c.verdict(c.strength(md)[0])}. Main themes: {HOUSE[c.house[md]][1]}" +
                 (f"; and {'; '.join(HOUSE[h][1].split(',')[0] for h in c.owns[md])}" if c.owns[md] else "") + ".")
        for a in m["antardashas"]:
            if a["end"] < today:
                continue
            ad = a["lord"]
            rel = (c.house[ad] - c.house[md]) % 12 + 1
            tone = "friction/obstacles" if rel in (6, 8, 12) else "support/progress" if rel in (1, 4, 5, 7, 9, 10) else "effort brings gains" if rel in (3, 11) else "mixed"
            houses = sorted(set(c.owns[ad] + [c.house[ad]]))
            L.append(f"- **{md}–{ad}** ({a['start']} → {a['end']}){' ← running now' if a['current'] else ''}: {ad} is {c.role(ad).lower()}, "
                     f"{ORD(rel)} from {md} → {tone}. Activates houses {', '.join(map(str, houses))}: "
                     + "; ".join(HOUSE[h][1].split(',')[0] for h in houses) + ".")
    return L


# ---------------- timing: triple check
EVENTS = {
    "Career rise / new job": {"houses": [10], "karakas": ["Sun", "Saturn"], "jaimini": "AmK", "min_age": 18},
    "Marriage": {"houses": [7], "karakas": ["Venus"], "jaimini": "DK", "min_age": 20},
    "Children": {"houses": [5], "karakas": ["Jupiter"], "jaimini": "PK", "min_age": 22},
    "Property / vehicle / home": {"houses": [4], "karakas": ["Mars", "Moon"], "jaimini": "MK", "min_age": 20},
    "Financial gains": {"houses": [11, 2], "karakas": ["Jupiter"], "jaimini": "AmK", "min_age": 18},
    "Foreign travel / relocation": {"houses": [12, 9], "karakas": ["Rahu"], "jaimini": "AK", "min_age": 16},
    "Higher education": {"houses": [4, 5, 9], "karakas": ["Jupiter", "Mercury"], "jaimini": "MK", "min_age": 15, "max_age": 32},
}


def _ju_sa(date: dt.date):
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    jd = julday(dt.datetime(date.year, date.month, 15, 12, tzinfo=dt.timezone.utc))
    return int((swe.calc_ut(jd, swe.JUPITER, FLAGS)[0][0] % 360) // 30), int((swe.calc_ut(jd, swe.SATURN, FLAGS)[0][0] % 360) // 30)


def _infl(sign, planet):
    return {sign} | {(sign + n - 1) % 12 for n in ({"Jupiter": [5, 7, 9], "Saturn": [3, 7, 10]}[planet])}


def timing_windows(c: Chart, years: int = 15) -> dict:
    from knrao import rashi_drishti
    k = c.k
    kar = {x["code"]: x["planet"] for x in k["knrao"]["karakas"]}
    vim = [(a["lord"], m["lord"], a["start"], a["end"]) for m in k["dasha"]["mahadashas"] for a in m["antardashas"]]
    chara = [(a["sign"], m["sign"], a["start"], a["end"]) for m in k["knrao"]["chara_dasha"]["periods"] for a in m["antardashas"]]
    start = dt.date.today().replace(day=1)
    months = [dt.date(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, 15) for i in range(years * 12)]
    transit = {d: _ju_sa(d) for d in months}
    out = {}
    for ev, spec in EVENTS.items():
        hs = spec["houses"]
        hsigns = [(c.lagna + h - 1) % 12 for h in hs]
        lords = [c.lord[h] for h in hs]
        kars = list(spec["karakas"]) + [kar[spec["jaimini"]]]
        if ev == "Marriage" and "female" in c.gender:
            kars.append("Jupiter")
        conn = set(lords) | set(kars)
        for h in hs:
            conn |= set(c.occ[h])            # occupants
        for L_ in lords:                      # planets conjunct the house lord
            conn |= {q for q in ALL9 if c.house[q] == c.house[L_]}
        for q in ("Rahu", "Ketu"):            # nodes act for their dispositor
            if SIGN_LORD[c.sign[q]] in lords:
                conn.add(q)
        key_signs = set(hsigns) | {c.sign[L_] for L_ in lords} | {c.sign[x] for x in kars if x in c.sign}
        rows = []
        for d in months:
            age = d.year - c.birth.year
            if age < spec["min_age"] or age > spec.get("max_age", 120):
                rows.append((0, 0, 0, 0, 0)); continue
            ds = d.isoformat()
            v = next(((ad, md) for ad, md, s, e in vim if s <= ds < e), None)
            ch = next(((ad, md) for ad, md, s, e in chara if s <= ds < e), None)
            v_ok = bool(v) and (v[0] in conn and (v[1] in conn or v[1] in lords))
            v_half = bool(v) and (v[0] in conn or v[1] in conn)
            ch_ok = False
            if ch:
                for sg in ch:
                    if sg in key_signs or any(t in key_signs for t in rashi_drishti(sg)):
                        ch_ok = True
            ju, sa = transit[d]
            both = _infl(ju, "Jupiter") & _infl(sa, "Saturn")
            dt_ok = bool(both & key_signs)
            score = (2 if v_ok else 1 if v_half else 0) + (1 if ch_ok else 0) + (1 if dt_ok else 0)
            rows.append((score, v_ok, v_half, ch_ok, dt_ok) if (v_half and dt_ok) else (0, 0, 0, 0, 0))
        wins, cur, prev = [], None, None
        for d, (sc, vo, vh, co, do) in zip(months, rows):
            ym = d.strftime("%Y-%m")
            if sc >= 3:
                if cur and prev and _next(prev) == ym:
                    cur["to"] = ym; cur["score"] = max(cur["score"], sc)
                    cur["chara_ok"] |= bool(co); cur["vim_full"] |= bool(vo)
                else:
                    cur = {"from": ym, "to": ym, "score": sc, "chara_ok": bool(co), "vim_full": bool(vo)}
                    wins.append(cur)
                prev = ym
            else:
                prev = None
        for w in wins:
            ds = w["from"] + "-15"
            v = next(((ad, md) for ad, md, s_, e in vim if s_ <= ds < e), ("?", "?"))
            ch = next(((ad, md) for ad, md, s_, e in chara if s_ <= ds < e), None)
            w["vim"] = f"{v[1]}–{v[0]}"
            w["chara"] = f"{short(SIGNS[ch[1]])}–{short(SIGNS[ch[0]])}" if ch else "?"
            w["checks"] = (f"Vimshottari {'✓✓' if w['vim_full'] else '✓'} · Chara {'✓' if w['chara_ok'] else '✗'} · Double transit ✓")
            w["strength"] = "strong" if w["score"] >= 4 else "moderate"
        wins.sort(key=lambda w: (-w["score"], w["from"]))
        wins = sorted(wins[:6], key=lambda w: w["from"])
        out[ev] = wins[:6]
    return out


def _next(ym: str) -> str:
    y, m = map(int, ym.split("-"))
    return f"{y + (m // 12)}-{m % 12 + 1:02d}"


def section_timing(c: Chart) -> list[str]:
    L = ["## 8. Timing by Triple Check (Vimshottari + Chara Dasha + Double Transit)",
         "Windows are listed only where the Vimshottari period is connected to the house/karakas **and** Jupiter and Saturn both influence the "
         "relevant house, its lord or karaka by transit; the Chara Dasha check adds confirmation. Next 15 years:"]
    L.append("✓✓ = both Mahadasha and Antardasha lords connected; ✓ = one of them. Events already fulfilled (e.g. marriage if married) "
             "will instead show as renewals or related developments.")
    tw = timing_windows(c)
    for ev, wins in tw.items():
        L.append(f"### {ev}")
        if not wins:
            L.append("No window in the next 15 years passes the strict triple check.")
            continue
        for w in wins:
            L.append(f"- **{w['from']}{' → ' + w['to'] if w['to'] != w['from'] else ''}** — {w['strength']} · {w['checks']} · "
                     f"Vimshottari {w['vim']}, Chara {w['chara']}")
    return L


# ======================================================================
def section_d9(c: Chart) -> list[str]:
    k = c.k
    d9 = k["charts"]["D9"]
    d9l = d9["lagna_sign"]
    d9lord = SIGN_LORD[d9l]
    h9 = {p["name"]: x["house"] for x in d9["houses"] for p in x["planets"]}
    L = ["## Navamsha (D9) — inner strength, marriage and dharma",
         f"**Navamsha Lagna {short(SIGNS[d9l])}** ({SIGN_TRAIT[d9l]}); its lord **{d9lord}** sits in D9 {ORD(h9[d9lord])} "
         f"in {short(c.P[d9lord]['navamsha_sign_name'])} ({c.P[d9lord]['navamsha_dignity'].lower()})."]
    L.append("### Strength shift D1 → D9")
    for p in ALL9:
        v = c.P[p]
        d1, d9d = v["dignity"], v["navamsha_dignity"]
        arrow = ("↑ gains" if d9d in ("Exalted", "Own sign", "Moolatrikona") and d1 not in ("Exalted", "Own sign", "Moolatrikona") else
                 "↓ loses" if d9d == "Debilitated" or (d1 in ("Exalted", "Own sign", "Moolatrikona") and d9d in ("Enemy sign", "Debilitated")) else "≈ steady")
        L.append(f"- **{p}**: D1 {short(v['sign_name'])} ({d1.lower()}) → D9 {short(v['navamsha_sign_name'])} ({d9d.lower()}), D9 house {h9[p]} — {arrow}"
                 + (" · **vargottama**" if v["vargottama"] else "") + f" · functional role in D1: {c.role(p).lower()}.")
    L.append("### Planets by D9 house — where each graha's inner strength goes")
    for p in ALL9:
        h = h9[p]
        q = ("kendra — the planet can deliver its D1 promise firmly" if h in KENDRA else
             "trikona — blessed, its results carry grace" if h in TRIKONA else
             "dusthana — its results come with struggle or are partly withheld" if h in DUSTHANA else
             "upachaya — results grow with time and effort")
        L.append(f"- **{p}** in D9 {ORD(h)} ({HOUSE[h][1].split(',')[0]}): {q}. In D1 it rules "
                 f"{', '.join(ORD(x) for x in c.owns[p]) or 'no house'} — so those matters are {('well sustained' if h in KENDRA | TRIKONA else 'strained' if h in DUSTHANA else 'moderately supported')} in the long run.")
    L.append("### D9 house lords")
    for hl in k["d9_house_lords"]:
        occ = [p for p, x in h9.items() if x == hl["house"]]
        L.append(f"- D9 {ORD(hl['house'])} ({short(hl['sign'])}): lord {hl['lord']} in D9 {ORD(hl['lord_in_house'])}" + (f"; occupied by {', '.join(occ)}" if occ else "") + ".")
    asp9 = [a for a in k["aspects"]["D9"] if a["house"] == 7]
    l7 = k["d9_house_lords"][6]
    occ7 = [p for p, h in h9.items() if h == 7]
    sign7 = (d9l + 6) % 12
    dk_ = next(x["planet"] for x in k["knrao"]["karakas"] if x["code"] == "DK")
    L.append("### Nature of the spouse")
    L.append(f"The D9 7th sign {short(SIGNS[sign7])} suggests a partner who is {SIGN_TRAIT[sign7]}; the D1 7th sign {short(SIGNS[(c.lagna + 6) % 12])} adds "
             f"{SIGN_TRAIT[(c.lagna + 6) % 12]} traits. As Darakaraka, {dk_} shows a spouse with {DK_TRAIT[dk_]}. "
             + (f"Planets in the D9 7th ({', '.join(occ7)}) add {'; '.join(PLANET_SIG[p].split(',')[0] for p in occ7)}. " if occ7 else "")
             + (f"Aspects on the D9 7th from {', '.join(a['planet'] for a in asp9)}." if asp9 else ""))
    L.append("### Marriage in D9")
    L.append(f"D9 7th sign {short(l7['sign'])}; lord **{l7['lord']}** in D9 {ORD(l7['lord_in_house'])}; occupants: {', '.join(occ7) or 'none'}. "
             f"Venus in D9 {ORD(h9['Venus'])} ({c.P['Venus']['navamsha_dignity'].lower()}), Jupiter in D9 {ORD(h9['Jupiter'])} ({c.P['Jupiter']['navamsha_dignity'].lower()}). "
             f"D1 7th lord {c.lord[7]} goes to D9 {ORD(h9[c.lord[7]])}.")
    dk = next(x["planet"] for x in k["knrao"]["karakas"] if x["code"] == "DK")
    L.append(f"Darakaraka {dk} in D9 {ORD(h9[dk])}. Upapada in {short(k['knrao']['upapada']['sign_name'])}.")
    L.append("### Dharma and spiritual path")
    for h in (5, 9, 12):
        hl = k["d9_house_lords"][h - 1]
        occ = [p for p, x in h9.items() if x == h]
        L.append(f"- D9 {ORD(h)} ({short(hl['sign'])}): lord {hl['lord']} in D9 {ORD(hl['lord_in_house'])}" + (f"; holds {', '.join(occ)}" if occ else "") + ".")
    km = k["knrao"]["karakamsha"]
    L.append(f"- Karakamsha {short(km['sign_name'])} (AK {km['atmakaraka']}) — the soul's direction.")
    if k.get("d9_yogas"):
        L.append("### Yogas in D9\n" + "\n".join(f"- {y}" for y in k["d9_yogas"]))
    return L


def md_join(lines: list[str]) -> str:
    out = []
    for ln in lines:
        for sub in ln.split("\n"):
            import re as _re
            is_item = lambda x: x.startswith("- ") or bool(_re.match(r"^\d+\. ", x))
            if out and is_item(sub) and is_item(out[-1]):
                out.append(sub)
            elif sub.strip():
                out += ["", sub]
    return "\n".join(out).strip() + "\n"


SECTIONS_D1 = [("Lagna, functional nature and planets", lambda c: section_lagna(c) + section_planets(c)),
               ("Houses", section_houses),
               ("Yogas, Jaimini and life areas", lambda c: section_yogas(c) + section_jaimini(c) + section_life(c)),
               ("Dashas and timing", lambda c: section_dashas(c) + section_timing(c))]


def d1_sections(k: dict) -> list[tuple[str, str]]:
    c = Chart(k)
    return [(t, md_join(fn(c))) for t, fn in SECTIONS_D1]


def marriage_timing(c: Chart) -> list[str]:
    tw = timing_windows(c)["Marriage"]
    L = ["## Marriage Timing — triple check"]
    L += [f"- **{w['from']}{' → ' + w['to'] if w['to'] != w['from'] else ''}** — {w['strength']} · {w['checks']} · Vimshottari {w['vim']}, Chara {w['chara']}" for w in tw] or ["No window in the next 15 years passes the strict triple check."]
    return L


def full_d1(k: dict) -> str:
    return "\n".join(body for _, body in d1_sections(k))


def full_d9(k: dict) -> str:
    c = Chart(k)
    return md_join(section_d9(c) + marriage_timing(c))


if __name__ == "__main__":
    import json, sys
    k = json.load(open(sys.argv[1]))
    print(full_d1(k))
    print("\n\n=========== D9 ===========\n")
    print(full_d9(k))
