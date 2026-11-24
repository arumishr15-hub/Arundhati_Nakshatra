"""
"Your Life Guide" — a narrative, explained K.N. Rao-style reading built from the
calculations in interpret.py and the interpretation library (texts_*.py).

Every topic follows the same pattern:
  What it means  →  What your chart shows  →  How it plays out  →  Guidance  →  Technical basis
"""
from __future__ import annotations

import datetime as dt

from astro_engine import SIGN_LORD, SIGNS
from interpret import (ALL9, DUSTHANA, KENDRA, ORD, PL7, PROFESSION, TRIKONA, Chart, find_yogas,
                       short, timing_windows, vim_md_ages, md_join)
from texts_core import (HOUSE_EXPLAIN, HOUSE_GUIDE, HOUSE_NAME, LAGNA, MOON_SIGN, NAKSHATRA,
                        PLANET_GUIDE, PLANET_ROLE, YOGA_EXPLAIN)
from texts_lord_house import LORD_IN
from texts_planet_house import PLANET_IN_HOUSE

TECH = lambda s: f"🔎 Technical basis: {s}"

DIGNITY_PLAIN = {
    "Exalted": "exalted — at its very best, like a person in their ideal job",
    "Moolatrikona": "in its moolatrikona sign — confident and effective, like working in its own office",
    "Own sign": "in its own sign — comfortable and in control, like being at home",
    "Friendly sign": "in a friend's sign — supported and reasonably comfortable",
    "Neutral sign": "in a neutral sign — neither helped nor hindered",
    "Enemy sign": "in an enemy's sign — uncomfortable, it has to work harder to deliver",
    "Debilitated": "debilitated — at its weakest, like a person out of their element",
    "—": "a shadow planet, acting through the sign it occupies",
}
VERDICT_PLAIN = {
    "very strong": "very strong — it can deliver its promises fully",
    "strong": "strong — it gives good results",
    "moderate": "of moderate strength — results come with some effort",
    "weak": "weak — its results need support and patience",
    "very weak": "very weak — its areas need conscious care and remedies",
}


def house_score(c: Chart, h: int) -> tuple[float, list[str]]:
    score, pts = 0.0, []
    for p in c.occ[h]:
        if c.is_fb(p):
            score += 1; pts.append(f"{p} (helpful planet) sits here")
        elif c.is_fm(p):
            score -= 1; pts.append(f"{p} ({'shadow planet' if p in ('Rahu', 'Ketu') else 'testing planet'}) sits here")
        else:
            pts.append(f"{p} sits here")
    for p in c.asp_on[h]:
        if p in c.occ[h]:
            continue
        if c.is_fb(p):
            score += 0.5; pts.append(f"helpful {p} looks at it")
        elif c.is_fm(p):
            score -= 0.5; pts.append(f"{p} casts a testing aspect on it")
    lord = c.lord[h]
    ls = c.strength(lord)[0]
    lh = c.house[lord]
    score += 1 if ls >= 2 else -1 if ls < 0 else 0
    if lh == h:
        score += 1
    elif (lh - h) % 12 + 1 in (6, 8, 12):
        score -= 0.5
    if lh in DUSTHANA and h not in DUSTHANA and lh != h:
        score -= 1
    elif lh in KENDRA | TRIKONA:
        score += 0.5
    pts.append(f"its ruler {lord} is in your {ORD(lh)} house and is {c.verdict(ls)}")
    return score, pts


def plain_verdict(score: float) -> tuple[str, str]:
    if score >= 2:
        return "🌸 Strong", "good"
    if score >= 0.5:
        return "🌼 Good", "good"
    if score > -1:
        return "🌿 Mixed", "weak"
    return "🍂 Needs care", "weak"


# ======================================================================
def part_who(c: Chart) -> list[str]:
    k = c.k
    lg = k["lagna"]
    L = LAGNA[lg["sign"]]
    nak = lg["nakshatra"]
    moon = c.P["Moon"]
    sun = c.P["Sun"]
    ll = lg["lord"]
    lls, llw = c.strength(ll)
    out = [f"# Your Life Guide — {k['input']['name']}",
           f"_Born {k['input']['date']} at {k['input']['time'][:5]} in {k['input']['place']}. Read by the K.N. Rao method (Parashari + Jaimini, Lahiri ayanamsa)._",
           "> **How to read this guide.** Each topic first explains what it means in Vedic astrology, then what *your* chart shows, "
           "how it is likely to play out in your life, and practical guidance. The small 🔎 notes give the technical reasons for "
           "anyone who wants to verify them. Astrology shows tendencies and timing — your choices shape how they unfold.",
           "## Part 1 · Who You Are",
           f"### Your Rising Sign: {L['name']}",
           "**What it means:** the Lagna (ascendant) is the sign rising on the eastern horizon at your birth. It is the single most "
           "important point in the chart — your body, personality and the lens through which you meet life.",
           f"**Your personality:** {L['who']}",
           f"- **Natural strengths:** {L['strengths']}.",
           f"- **Growth areas:** {L['challenges']}.",
           f"- **Body and health:** {L['body']}.",
           f"**Your rising nakshatra — {nak}:** {NAKSHATRA.get(nak, '')}. This adds its colour to your whole personality.",
           ]
    if c.occ[1]:
        out.append("**Planets in your Lagna** shape your personality directly:")
        for p in c.occ[1]:
            out.append(f"- **{p}:** {PLANET_IN_HOUSE[p][1]}")
    out.append(f"**Your chart ruler — {ll}:** the lord of the Lagna shows where your life energy flows. Your {ll} sits in your "
               f"**{ORD(c.house[ll])} house ({HOUSE_NAME[c.house[ll]].lower()})** and is {VERDICT_PLAIN[c.verdict(lls)]}. "
               f"{LORD_IN[1][c.house[ll]]}")
    out.append(f"**Guidance:** {L['advice']}")
    out.append(TECH(f"Lagna {lg['degree']} {short(lg['sign_name'])}, {nak} pada {lg['pada']}; lagna lord {ll} in {short(c.P[ll]['sign_name'])}, H{c.house[ll]}, score {lls} ({'; '.join(llw)})."))

    out += [f"### Your Mind: Moon in {moon['sign_name']}",
            "**What it means:** the Moon shows your mind, emotions and how you feel safe. In Vedic astrology it is almost as important as the Lagna — "
            "the Chandra Kundali (Moon chart) is read alongside the birth chart.",
            f"**Your emotional nature:** {MOON_SIGN[moon['sign']]}",
            f"**Your birth star — {moon['nakshatra']} (pada {moon['pada']}):** {NAKSHATRA.get(moon['nakshatra'], '')}. Your birth star also sets your Vimshottari dasha sequence.",
            (f"**Where your Moon sits:** {PLANET_IN_HOUSE['Moon'][moon['house']]}" if moon["house"] != 1 else
             "**Where your Moon sits:** in your Lagna — your feelings show openly and shape your personality (see above)."),
            TECH(f"Moon {moon['degree']} {short(moon['sign_name'])}, H{moon['house']}, {moon['dignity'].lower()}" + (", vargottama" if moon['vargottama'] else "") + ".")]
    out += [f"### Your Soul: Sun in {sun['sign_name']}",
            f"**What it means:** the Sun shows your soul, confidence, father and relationship with authority.",
            f"**In your chart:** {PLANET_IN_HOUSE['Sun'][sun['house']]}",
            TECH(f"Sun {sun['degree']} {short(sun['sign_name'])}, H{sun['house']}, D1 {sun['dignity'].lower()}, D9 {sun['navamsha_dignity'].lower()}.")]

    fb = [p for p in PL7 if c.fn[p] in ("Benefic", "Yogakaraka")]
    fm = [p for p in PL7 if c.fn[p] == "Malefic"]
    nt = [p for p in PL7 if p not in fb + fm]
    yk = [p for p in PL7 if c.fn[p] == "Yogakaraka"]
    out += ["### Planets That Help You and Planets That Test You",
            "**What it means:** K.N. Rao always begins here. A planet's effect depends less on whether it is 'good' or 'bad' in general and "
            "more on which houses it rules *for your rising sign*. Rulers of fortune houses help you; rulers of difficult houses test you.",
            f"- 🌸 **Your helpers (functional benefics):** {', '.join(fb) or 'none'} — their periods and strength bring support." ,
            f"- ⭐ **Your yogakaraka:** {', '.join(yk)} — the single most important planet for your rise; its period is a turning point." if yk else "",
            f"- 🍂 **Your teachers (functional malefics):** {', '.join(fm) or 'none'} — they bring lessons, effort and obstacles to overcome. Never strengthen them with gemstones.",
            f"- 🌿 **Neutral:** {', '.join(nt) or 'none'} — they give results according to their placement and company.",
            "- 🌑 **Rahu and Ketu** act on behalf of the planet ruling the sign they sit in, and amplify the house they occupy.",
            TECH("; ".join(f"{p}: {v['nature']} — {v['reason']}" for p, v in c.k["knrao"]["functional"].items()))]
    return [x for x in out if x]


def part_planets(c: Chart) -> list[str]:
    out = ["## Part 2 · Your Nine Planets",
           "Each planet is a 'minister' in the cabinet of your life. Here is what each one does for you."]
    for p in ALL9:
        v = c.P[p]
        s, why = c.strength(p)
        vd = c.verdict(s)
        icon = {"very strong": "🌸", "strong": "🌸", "moderate": "🌼", "weak": "🍂", "very weak": "🍂"}[vd]
        out.append(f"### {icon} {p} in your {ORD(v['house'])} house ({short(v['sign_name'])})")
        out.append(f"**What {p} represents:** {PLANET_ROLE[p]}.")
        out.append(f"**In your chart:** {PLANET_IN_HOUSE[p][v['house']]}")
        out.append(f"**Its condition:** {p} is {DIGNITY_PLAIN[v['dignity']]}"
                   + (f", and in your Navamsha it is {v['navamsha_dignity'].lower()}" if v["navamsha_dignity"] not in ("—",) else "")
                   + f". Overall it is **{VERDICT_PLAIN[vd]}**.")
        if p in PL7 and c.owns[p]:
            for h in c.owns[p]:
                out.append(f"- **As ruler of your {ORD(h)} house ({HOUSE_NAME[h].lower()}):** {LORD_IN[h][v['house']]}")
        elif p not in PL7:
            d = SIGN_LORD[v["sign"]]
            out.append(f"- **Acting for {d}:** as a shadow planet, {p} delivers the results of {d} (ruler of your "
                       f"{', '.join(ORD(h) for h in c.owns[d])} house) mixed with its own nature.")
        notes = []
        nb = c.neecha_bhanga(p)
        if v["dignity"] == "Debilitated" and p in PL7:
            notes.append("**Debilitation cancelled (Neecha Bhanga):** its weakness is repaired — " + "; ".join(nb) + ". Expect struggle at first, then a marked rise. This often produces remarkable people."
                         if nb else "**Debilitated without cancellation:** its matters need conscious support, patience and remedies.")
        if v["retrograde"]:
            notes.append("**Retrograde:** its results turn inward — you revisit, rethink and redo its matters; results often come later but deeper.")
        if v["combust"]:
            notes.append(f"**Combust (too close to the Sun):** its significations are overshadowed — {p}'s qualities need extra attention to be expressed.")
        if v["vargottama"]:
            notes.append("**Vargottama (same sign in D1 and D9):** " + ("its condition is confirmed in both charts — here that means the debility is real, so the neecha bhanga matters all the more."
                         if v["dignity"] == "Debilitated" else "this planet is reliable — what it promises, it delivers."))
        if v["nak_lord"] != p:
            notes.append(f"**Its star lord is {v['nak_lord']}** (in your {ORD(c.house[v['nak_lord']])} house) — so {p} also brings up {HOUSE_NAME[c.house[v['nak_lord']]].lower()} matters.")
        conj = [q for q in ALL9 if q != p and c.house[q] == v["house"]]
        if conj:
            notes.append(f"**Together with {', '.join(conj)}:** their energies blend — " + "; ".join(f"{q} adds {PLANET_ROLE[q].split(',')[0]}" for q in conj) + ".")
        out += [f"- {n}" for n in notes]
        gk = "strong" if s >= 1 else "weak"
        g = PLANET_GUIDE[p][gk]
        if p in PL7 and c.fn[p] == "Malefic" and gk == "strong":
            g += " (It is a 'teacher' planet for your lagna — use its strength wisely and do not wear its gemstone.)"
        out.append(f"**Your guidance:** {g}")
        out.append(TECH(f"{v['degree']} {short(v['sign_name'])}, {v['nakshatra']} pada {v['pada']}, H{v['house']}, role {c.role(p)}, score {s}: {'; '.join(why) or '—'}."))
    return out


def part_houses(c: Chart) -> list[str]:
    out = ["## Part 3 · The Twelve Areas of Your Life",
           "K.N. Rao judges every house three ways: the **house itself** (who sits there, who looks at it), its **ruler** (where it went and how strong it is), "
           "and its **karaka** (natural significator). When all three agree, results are certain."]
    for h in range(1, 13):
        sc, pts = house_score(c, h)
        label, gk = plain_verdict(sc)
        lord = c.lord[h]
        lh = c.house[lord]
        out.append(f"### {ORD(h)} House — {HOUSE_NAME[h]} · {label}")
        out.append(f"**What it governs:** {HOUSE_EXPLAIN[h]}")
        body = []
        if c.occ[h]:
            for p in c.occ[h]:
                body.append(f"- **{p} here:** {PLANET_IN_HOUSE[p][h]}")
        else:
            body.append("- No planet sits here, so the house is judged mainly by its ruler and the planets looking at it.")
        body.append(f"- **Its ruler {lord} sits in your {ORD(lh)} house:** {LORD_IN[h][lh]}")
        if c.asp_on[h]:
            body.append(f"- **Planets looking at it:** {', '.join(c.asp_on[h])} — "
                        + ", ".join(f"{p} {'supports' if c.is_fb(p) else 'tests' if c.is_fm(p) else 'influences'}" for p in c.asp_on[h]) + " this area.")
        if h == 5:
            d7 = c.P[lord]["d7_house"]
            body.append(f"- **Children chart (D7) check:** the 5th ruler falls in the {ORD(d7)} of D7 — " +
                        ("this confirms the blessing of children." if d7 in KENDRA | TRIKONA | {11} else "children may come with some delay or effort." if d7 in DUSTHANA else "moderate confirmation."))
        if h == 7:
            l9 = c.k["d9_house_lords"][6]
            body.append(f"- **Marriage chart (D9) check:** the Navamsha 7th ruler {l9['lord']} is in the D9 {ORD(l9['lord_in_house'])} — " +
                        ("this supports a stable marriage." if l9['lord_in_house'] in KENDRA | TRIKONA | {11} else "marriage asks for maturity and adjustment." if l9['lord_in_house'] in DUSTHANA else "moderate support."))
        if h == 10:
            d10 = c.P[lord]["d10_house"]
            body.append(f"- **Career chart (D10) check:** the 10th ruler falls in the {ORD(d10)} of D10 — " +
                        ("this confirms career strength." if d10 in KENDRA | TRIKONA | {11} else "career needs extra effort and patience." if d10 in DUSTHANA else "moderate confirmation."))
        out += body
        out.append(f"**Guidance:** {HOUSE_GUIDE[h][gk]}")
        out.append(TECH("; ".join(pts) + f"; score {sc:+.1f}."))
    return out


def part_yogas(c: Chart) -> list[str]:
    ys = find_yogas(c)
    ages = vim_md_ages(c)
    out = ["## Part 4 · Special Combinations in Your Chart (Yogas)",
           "A yoga is a special combination of planets that produces a specific result. K.N. Rao stresses that **a yoga works only "
           "when the planets forming it get their dasha** — so for each yoga you will see when it switches on in your life."]
    if not ys:
        out.append("Your chart does not have the major classical yogas by strict rules; results come mainly through house rulers and dashas.")
    for y in ys:
        when = [f"{p} period, age {ages[p][0]}–{ages[p][1]} ({ages[p][2][:4]}–{ages[p][3][:4]})" for p in y["planets"] if p in ages and ages[p][1] > 0 and ages[p][0] < 95]
        out.append(f"### ✨ {y['name']}")
        out.append(f"**What it is:** {YOGA_EXPLAIN.get(y['name'], '')}")
        out.append(f"**In your chart:** {y['detail']}.")
        out.append(f"**When it gives results:** {'; '.join(when)}." if when else "**When it gives results:** mainly through sub-periods (antardashas) of these planets.")
    return out


def part_soul(c: Chart) -> list[str]:
    kn = c.k["knrao"]
    kar = {x["code"]: x["planet"] for x in kn["karakas"]}
    ak, amk, dk = kar["AK"], kar["AmK"], kar["DK"]
    al, ul = kn["arudha_lagna"], kn["upapada"]
    from interpret import AK_MEANING, DK_TRAIT
    return ["## Part 5 · Your Soul's Purpose (Jaimini Astrology)",
            "K.N. Rao combines Parashari astrology with Jaimini's system, which ranks the planets by degree to find the 'king' of your chart.",
            f"- **Your Atmakaraka (soul planet) is {ak}:** {AK_MEANING.get(ak, '')}. Your life's deepest lessons come through {PLANET_ROLE[ak].split(',')[0]}.",
            f"- **Your Karakamsha is {short(kn['karakamsha']['sign_name'])}:** the sign of your soul's desire — " + ({
                0: "independence and courage", 1: "stability and beauty", 2: "knowledge and communication", 3: "care, home and devotion",
                4: "leadership and dignity", 5: "service and healing", 6: "harmony and justice", 7: "depth, research and transformation",
                8: "wisdom, teaching and dharma", 9: "duty and achievement", 10: "service to society", 11: "compassion and spirituality"}[kn['karakamsha']['sign']]) + ".",
            f"- **Your Amatyakaraka (career guide) is {amk}:** work suited to you — {PROFESSION[amk]}.",
            f"- **Your Darakaraka (spouse indicator) is {dk}:** your partner is likely to show {DK_TRAIT.get(dk, 'distinctive qualities')}.",
            f"- **Your Arudha Lagna (public image) is in {short(al['sign_name'])}, your {ORD(al['house'])} house:** the world sees you through {HOUSE_NAME[al['house']].lower()} themes.",
            f"- **Your Upapada (marriage indicator) is in {short(ul['sign_name'])}, your {ORD(ul['house'])} house:** marriage connects with {HOUSE_NAME[ul['house']].lower()}."]


def part_chapters(c: Chart) -> list[str]:
    k = c.k
    today = dt.date.today().isoformat()
    out = ["## Part 6 · The Chapters of Your Life (Dashas)",
           "**What it means:** the Vimshottari dasha divides life into planetary 'chapters'. During a planet's mahadasha (main period) its houses, "
           "strength and nature colour your life; each antardasha (sub-period) adds a second planet's theme. K.N. Rao reads each sub-period "
           "by the sub-lord's own nature *and* its position from the main lord — 6th, 8th or 12th from it brings friction; 1st, 4th, 5th, 7th, "
           "9th or 10th brings support."]
    past = [m for m in k["dasha"]["mahadashas"] if m["end"] < today]
    if past:
        out.append("**Chapters already lived:** " + "; ".join(f"{m['lord']} ({m['start'][:4]}–{m['end'][:4]})" for m in past) + ". Look back — you will recognise their themes.")
    shown = 0
    for m in k["dasha"]["mahadashas"]:
        if m["end"] < today or shown >= 2:
            continue
        shown += 1
        md = m["lord"]
        s = c.strength(md)[0]
        houses = sorted(set(c.owns[md] + [c.house[md]]))
        now = "your current chapter" if m["current"] else "your next chapter"
        out.append(f"### {'📖' if m['current'] else '🔮'} {md} Mahadasha · {m['start']} to {m['end']} ({now})")
        out.append(f"**The theme of this chapter:** {md} represents {PLANET_ROLE[md]}. For you it activates "
                   + ", ".join(f"your {ORD(h)} house ({HOUSE_NAME[h].lower()})" for h in houses) + ".")
        fnl = c.fn.get(SIGN_LORD[c.sign[md]]) if md in ("Rahu", "Ketu") else c.fn[md]
        helper = fnl in ("Benefic", "Yogakaraka")
        nb = c.neecha_bhanga(md) if md in PL7 else []
        if nb and helper:
            tone = ("a chapter that begins with effort and struggle and then builds to a clear rise — your " + md +
                    " is a helper whose debility is cancelled (neecha bhanga), the classic 'from weakness to strength' pattern")
        elif helper and s >= 1:
            tone = "a chapter of rise, support and opportunity"
        elif helper:
            tone = "a chapter of big promise that asks for effort — the results come, but through work and patience"
        elif s >= 0:
            tone = "a chapter of growth through effort — what you build now lasts"
        else:
            tone = "a chapter of lessons and patience — slower, but it builds inner strength"
        out.append(f"**How it is likely to feel:** {tone}. For your lagna {md} is {c.role(md)}, and on its own it is {VERDICT_PLAIN[c.verdict(s)]}. "
                   f"{PLANET_IN_HOUSE[md][c.house[md]]}")
        out.append(f"**Guidance for this chapter:** {PLANET_GUIDE[md]['strong' if s >= 1 else 'weak']}")
        out.append("**Sub-periods (antardashas):**")
        for a in m["antardashas"]:
            if a["end"] < today:
                continue
            ad = a["lord"]
            rel = (c.house[ad] - c.house[md]) % 12 + 1
            feel = ("smooth and supportive" if rel in (1, 4, 5, 7, 9, 10) else "challenging — stay patient" if rel in (6, 8, 12) else "rewarding with effort")
            adh = sorted(set(c.owns[ad] + [c.house[ad]]))
            focus = ", ".join(HOUSE_NAME[h].split(",")[0].lower() for h in adh)
            out.append(f"- **{md}–{ad}** ({a['start']} → {a['end']}){' — ▶ you are here' if a['current'] else ''}: {feel}. "
                       f"Focus areas: {focus}. {PLANET_GUIDE[ad]['strong' if c.strength(ad)[0] >= 1 else 'weak'].split(';')[0].split('.')[0]}.")
    return out


def part_dates(c: Chart) -> list[str]:
    tw = timing_windows(c)
    out = ["## Part 7 · Important Dates Ahead",
           "**How these are found:** K.N. Rao's famous 'triple check'. An event is likely only when (1) the Vimshottari dasha is connected to that "
           "area of life, (2) the Jaimini Chara Dasha points to it, and (3) Jupiter and Saturn *both* influence the relevant house in transit "
           "(the 'double transit'). Windows marked **strong** pass all checks. Use them to plan, apply, propose or invest — and use the gaps to prepare."]
    icons = {"Career rise / new job": "💼", "Marriage": "💍", "Children": "👶", "Property / vehicle / home": "🏡",
             "Financial gains": "💰", "Foreign travel / relocation": "✈️", "Higher education": "🎓"}
    for ev, ws in tw.items():
        out.append(f"### {icons.get(ev, '•')} {ev}")
        if not ws:
            out.append("No window passes the strict triple check in the next 15 years — this area unfolds gradually rather than through one big event.")
            continue
        for w in ws:
            out.append(f"- **{w['from']}{' to ' + w['to'] if w['to'] != w['from'] else ''}** — {w['strength']} "
                       f"({w['checks']}; Vimshottari {w['vim']}, Chara {w['chara']})")
    return out


def part_summary(c: Chart) -> list[str]:
    scores = {h: house_score(c, h)[0] for h in range(1, 13)}
    best = sorted(scores, key=scores.get, reverse=True)[:3]
    worst = sorted(scores, key=scores.get)[:3]
    pstr = {p: c.strength(p)[0] for p in PL7}
    strong_p = sorted(pstr, key=pstr.get, reverse=True)[:2]
    weak_p = sorted(pstr, key=pstr.get)[:2]
    lg = LAGNA[c.lagna]
    yk = [p for p in PL7 if c.fn[p] == "Yogakaraka"]
    cur = c.k["dasha"]["current"]
    tips = [lg["advice"],
            f"Lean on your strongest planets, {strong_p[0]} and {strong_p[1]}: {PLANET_GUIDE[strong_p[0]]['strong'].split('.')[0]}.",
            f"Nurture {weak_p[0]}: {PLANET_GUIDE[weak_p[0]]['weak'].split(';')[0].split('.')[0]}.",
            f"Your running {cur['mahadasha']}–{cur['antardasha']} period (till {cur['ad_end']}) is the time to focus on "
            + ", ".join(HOUSE_NAME[h].split(',')[0].lower() for h in sorted(set(c.owns[cur['antardasha']] + [c.house[cur['antardasha']]]))) + "."]
    if yk:
        tips.append(f"{yk[0]} is your yogakaraka — honour it (its weekday, colour and mantra) and make full use of its periods.")
    tips += [HOUSE_GUIDE[h]["weak"] for h in worst[:2]]
    tips.append("Mark the 'strong' date windows in your calendar and plan important steps around them.")
    return ["## Part 8 · Your Personal Guidance Summary",
            "**Your greatest blessings:** " + "; ".join(f"{HOUSE_NAME[h].lower()} ({ORD(h)} house)" for h in best) + ".",
            "**Areas to nurture with care:** " + "; ".join(f"{HOUSE_NAME[h].lower()} ({ORD(h)} house)" for h in worst) + ".",
            "**Ten-second summary:** " + f"a {short(SIGNS[c.lagna])} rising person with a {short(c.P['Moon']['sign_name'])} Moon — {lg['strengths'].split(',')[0]} and {lg['strengths'].split(',')[1].strip()} are your nature; "
            f"{', '.join(strong_p)} are your pillars, and the current {cur['mahadasha']} chapter shapes the years until {c.k['dasha']['current']['md_end'][:4]}.",
            "**Practical guidance:**"] + [f"{i}. {t}" for i, t in enumerate(tips, 1)] + [
            "> Astrology is guidance, not destiny — and not a substitute for medical, legal or financial advice. For a personal consultation, use the **Book Appointment** tab."]


def guide_d1(k: dict) -> list[tuple[str, str]]:
    c = Chart(k)
    return [("Who you are", md_join(part_who(c))),
            ("Your planets", md_join(part_planets(c))),
            ("Life areas", md_join(part_houses(c))),
            ("Yogas and soul", md_join(part_yogas(c) + part_soul(c))),
            ("Chapters and dates", md_join(part_chapters(c) + part_dates(c) + part_summary(c)))]


# ======================================================================
def guide_d9(k: dict) -> str:
    c = Chart(k)
    d9 = k["charts"]["D9"]
    d9l = d9["lagna_sign"]
    h9 = {p["name"]: x["house"] for x in d9["houses"] for p in x["planets"]}
    d9lord = SIGN_LORD[d9l]
    from interpret import DK_TRAIT, SIGN_TRAIT
    out = [f"# Navamsha Guide — Marriage, Inner Strength & Dharma",
           "> **What the Navamsha (D9) is:** each sign is divided into nine parts; the Navamsha chart built from them shows the *inner* strength "
           "of every planet, your marriage and spouse, your dharma, and the fruits of the second half of life. K.N. Rao's rule: **the birth chart "
           "shows the promise, the Navamsha shows whether it will be fulfilled.**",
           f"## Your Navamsha Lagna: {LAGNA[d9l]['name']}",
           f"Your inner self and the way you grow through marriage has a {SIGN_TRAIT[d9l]} quality. Its ruler {d9lord} sits in the "
           f"{ORD(h9[d9lord])} house of the Navamsha ({HOUSE_NAME[h9[d9lord]].lower()}), so that area becomes central to your inner growth.",
           "## How Strong Your Planets Really Are",
           "A planet strong in both charts delivers fully; strong in D1 but weak in D9 promises more than it gives; weak in D1 but strong in D9 improves with time."]
    for p in ALL9:
        v = c.P[p]
        d1g = v["dignity"] in ("Exalted", "Own sign", "Moolatrikona")
        d9g = v["navamsha_dignity"] in ("Exalted", "Own sign", "Moolatrikona")
        d9b = v["navamsha_dignity"] == "Debilitated"
        if v["vargottama"] and v["dignity"] == "Debilitated":
            msg = ("vargottama but debilitated in both charts — the weakness is real and needs conscious support; "
                   + ("the cancellation of debility (neecha bhanga) in your birth chart is the key to its rise." if c.neecha_bhanga(p) else "remedies and patience help most."))
        elif v["vargottama"]:
            msg = "vargottama — same sign in both charts. Very reliable: what it promises, it delivers."
        elif d9g and not d1g:
            msg = "gains strength in D9 — its results improve with age and maturity."
        elif d9b or (d1g and not d9g and v["navamsha_dignity"] in ("Enemy sign",)):
            msg = "loses strength in D9 — its outer promise needs effort to be fully realised."
        else:
            msg = "of steady strength — results stay much as the birth chart shows."
        out.append(f"### {p} — D1 {short(v['sign_name'])} → D9 {short(v['navamsha_sign_name'])}")
        out.append(f"**Strength:** {v['dignity'].lower()} in the birth chart, {v['navamsha_dignity'].lower()} in the Navamsha — {msg}")
        first = PLANET_IN_HOUSE[p][h9[p]].split(". ")[0].rstrip(".")
        out.append(f"**In your inner life (D9 {ORD(h9[p])} house — {HOUSE_NAME[h9[p]].lower()}):** {first}. "
                   f"In the Navamsha this shows how {p}'s themes ({PLANET_ROLE[p].split(',')[0]}, {PLANET_ROLE[p].split(',')[1].strip()}) mature over time and in marriage.")
    l7 = k["d9_house_lords"][6]
    sign7 = (d9l + 6) % 12
    occ7 = [p for p, h in h9.items() if h == 7]
    dk = next(x["planet"] for x in k["knrao"]["karakas"] if x["code"] == "DK")
    kar = "Jupiter" if "female" in c.gender else "Venus"
    out += ["## Marriage and Your Spouse",
            "**How it is read:** the 7th house of the birth chart and its ruler, the 7th house of the Navamsha and its ruler, Venus and (for a woman) Jupiter, "
            "the Darakaraka and the Upapada — K.N. Rao insists that several of these agree before judging marriage.",
            f"- **Nature of your spouse:** the Navamsha 7th sign {short(SIGNS[sign7])} suggests someone {SIGN_TRAIT[sign7]}; your Darakaraka {dk} adds "
            f"{DK_TRAIT.get(dk, '')}." + (f" Planets in the Navamsha 7th ({', '.join(occ7)}) add {', '.join(PLANET_ROLE[p].split(',')[0] for p in occ7)}." if occ7 else ""),
            f"- **Birth-chart 7th house:** {LORD_IN[7][c.house[c.lord[7]]]}" + (f" Planets there: " + "; ".join(PLANET_IN_HOUSE[p][7] for p in c.occ[7]) if c.occ[7] else ""),
            f"- **Navamsha 7th ruler {l7['lord']} in the D9 {ORD(l7['lord_in_house'])}:** " + (
                "a supportive sign for lasting marriage." if l7['lord_in_house'] in KENDRA | TRIKONA | {11} else
                "marriage asks for patience, maturity and conscious effort." if l7['lord_in_house'] in DUSTHANA else "moderate support for marriage."),
            f"- **{kar} (marriage karaka for you)** is in the D9 {ORD(h9[kar])} and is {c.P[kar]['navamsha_dignity'].lower()} there; Venus is in the D9 {ORD(h9['Venus'])} ({c.P['Venus']['navamsha_dignity'].lower()}).",
            f"- **Guidance:** {HOUSE_GUIDE[7]['good' if l7['lord_in_house'] in KENDRA | TRIKONA | {11} else 'weak']} Choose a partner whose chart supports yours (Kundali Milan), and communicate openly during testing periods."]
    tw = timing_windows(c)["Marriage"]
    out.append("### Marriage timing (triple check)")
    out += [f"- **{w['from']}{' to ' + w['to'] if w['to'] != w['from'] else ''}** — {w['strength']} ({w['checks']}; Vimshottari {w['vim']}, Chara {w['chara']})" for w in tw] or ["- No strong window in the next 15 years by strict rules."]
    out.append("_If you are already married, these windows show important developments in married life rather than a wedding._")
    km = k["knrao"]["karakamsha"]
    out += ["## Your Dharma and Spiritual Path",
            f"The Navamsha 9th house shows dharma, the 5th shows mantra and devotion, the 12th shows liberation. Your Karakamsha (soul's sign) is {short(km['sign_name'])}."]
    for h, name in ((9, "dharma and faith"), (5, "mantra, devotion and wisdom"), (12, "liberation and retreat")):
        hl = k["d9_house_lords"][h - 1]
        occ = [p for p, x in h9.items() if x == h]
        out.append(f"- **{name.capitalize()} (D9 {ORD(h)}):** ruler {hl['lord']} in the D9 {ORD(hl['lord_in_house'])}" + (f"; {', '.join(occ)} here bring{'s' if len(occ) == 1 else ''} {', '.join(PLANET_ROLE[p].split(',')[0] for p in occ)} into your spiritual life" if occ else "") + ".")
    out.append(f"**Guidance:** {PLANET_GUIDE[km['atmakaraka']]['weak' if c.strength(km['atmakaraka'])[0] < 1 else 'strong']} Your soul planet {km['atmakaraka']} is your spiritual teacher in this life.")
    return md_join(out)


if __name__ == "__main__":
    import json, sys
    k = json.load(open(sys.argv[1]))
    print("\n".join(b for _, b in guide_d1(k)))
    print("\n\n=================\n")
    print(guide_d9(k))
