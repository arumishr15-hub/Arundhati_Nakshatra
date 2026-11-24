"""
The four Arundhati Nakshatra agents.

  Agent 1  KundaliAgent      — builds Janam Patrika, Navamsha, Chandra, Chalit + Vimshottari dasha
  Agent 2  AnalystAgent      — deep, reasoned analysis of the Lagna (D1) and Navamsha (D9) charts,
                               plus follow-up questions on the chart
  Agent 3  BookingAgent      — conversational agent that books a kundali consultation with you
  Agent 4  NoteTakerAgent    — distils every report into the crux + remedies

Agents 2-4 use the AI provider set in My Profile (Gemini or Groq). Without a key they fall back to a basic
rule-based mode so the app still runs.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from typing import Iterator
from zoneinfo import ZoneInfo

import astro_engine as AE
import storage

import llm


def llm_available() -> bool:
    return llm.available()


def full_reports_available() -> bool:
    """Long multi-part reports need a provider with a generous limit (Gemini, not Groq's free tier)."""
    return llm.available() and not llm.is_compact()


def _stream(system: str, messages: list, max_tokens: int = 8000) -> Iterator[str]:
    yield from llm.stream(system, messages, max_tokens)


# ======================================================================
# Agent 1 — Kundali creator
# ======================================================================
class KundaliAgent:
    name = "Kundali Agent"

    def run(self, birth: dict) -> tuple[str, dict]:
        k = AE.compute_kundali(birth["name"], birth["date"], birth["time"], float(birth["lat"]),
                               float(birth["lon"]), birth["tz"], birth.get("place", ""),
                               birth.get("gender", ""))
        pid = storage.create_profile(birth, k)
        return pid, k


# ----------------------------------------------------------------------
def chart_fact_sheet(k: dict, chart: str = "D1") -> str:
    """Compact, complete fact sheet the analyst reasons over."""
    b = k["input"]
    L = [f"Native: {b['name']} | Gender: {b.get('gender') or 'n/a'} | Born {b['date']} {b['time']} ({b['tz']}) at {b['place']}",
         f"Ayanamsa: {k['ayanamsa']['name']} {k['ayanamsa']['decimal']}°"]
    if chart == "D1":
        lg = k["lagna"]
        L.append(f"LAGNA: {lg['sign_name']} {lg['degree']}, nakshatra {lg['nakshatra']} pada {lg['pada']}, lagna lord {lg['lord']}")
        L.append(f"Moon sign (Rashi): {k['moon_sign']} | Sun sign: {k['sun_sign']}")
        L.append("\nPLANETS (D1, whole-sign houses):")
        for p in k["planets"]:
            flags = [x for x, on in (("Retrograde", p["retrograde"]), ("Combust", p["combust"]),
                                    ("Vargottama", p["vargottama"])) if on]
            L.append(f"- {p['name']}: {p['sign_name']} {p['degree']}, House {p['house']}, {p['nakshatra']} pada {p['pada']} "
                     f"(nak lord {p['nak_lord']}), dignity: {p['dignity']}, lord of houses {p['lord_of'] or '-'}"
                     + (f", {', '.join(flags)}" if flags else ""))
        L.append("\nHOUSE LORDS:")
        for h in k["house_lords"]:
            L.append(f"- H{h['house']} {h['sign']} ({h['meaning']}): lord {h['lord']} sits in H{h['lord_in_house']}")
        L.append("\nVEDIC ASPECTS (graha drishti):")
        for a in k["aspects"]["D1"]:
            L.append(f"- {a['planet']} casts {a['aspect']} aspect on H{a['house']}" +
                     (f" (aspecting {', '.join(a['on_planets'])})" if a["on_planets"] else ""))
        L.append("\nCONJUNCTIONS: " + ("; ".join(f"H{c['house']}: {' + '.join(c['planets'])}" for c in k["conjunctions"]["D1"]) or "none"))
        L.append("\nBHAVA CHALIT shifts: " + ("; ".join(f"{s['planet']} rashi H{s['rashi_house']} → bhava {s['bhava']}"
                                                    for s in k["charts"]["Chalit"]["shifted"]) or "none"))
        L.append("\nCHANDRA KUNDALI (houses from Moon): " + "; ".join(
            f"H{h['house']}: {', '.join(p['name'] for p in h['planets'])}" for h in k["charts"]["Chandra"]["houses"] if h["planets"]))
        L.append("\nYOGAS DETECTED (rule-based, verify): " + ("; ".join(k["yogas"]) or "none of the common ones"))
        kn = k["knrao"]
        L.append("\nFUNCTIONAL NATURE FOR THIS LAGNA (Laghu Parashari): " + "; ".join(
            f"{p}: {v['nature']} ({v['reason']})" for p, v in kn["functional"].items()))
        L.append(f"\nDASHAMSHA D10 (career) lagna {k['varga_lagnas']['D10']}: " + "; ".join(
            f"{p['name']} {p['d10_sign_name']} H{p['d10_house']}" for p in k["planets"]))
        L.append(f"SAPTAMSHA D7 (children) lagna {k['varga_lagnas']['D7']}: " + "; ".join(
            f"{p['name']} {p['d7_sign_name']} H{p['d7_house']}" for p in k["planets"]))
        L.append(jaimini_sheet(k))
    else:
        d9 = k["charts"]["D9"]
        L.append(f"NAVAMSHA LAGNA: {AE.SIGNS[d9['lagna_sign']]} (D1 lagna {k['lagna']['sign_name']})")
        L.append("\nPLANETS IN D9:")
        for p in k["planets"]:
            h = next(x["house"] for x in d9["houses"] if any(q["name"] == p["name"] for q in x["planets"]))
            L.append(f"- {p['name']}: D9 {p['navamsha_sign_name']} in D9 house {h}, D9 dignity {p['navamsha_dignity']}; "
                     f"D1 dignity {p['dignity']} in {p['sign_name']}" + (" — VARGOTTAMA" if p["vargottama"] else ""))
        L.append("\nD9 HOUSE LORDS:")
        for h in k["d9_house_lords"]:
            L.append(f"- D9 H{h['house']} {h['sign']}: lord {h['lord']} in D9 H{h['lord_in_house']}")
        L.append("\nD9 ASPECTS:")
        for a in k["aspects"]["D9"]:
            L.append(f"- {a['planet']} {a['aspect']} aspect on D9 H{a['house']}" +
                     (f" ({', '.join(a['on_planets'])})" if a["on_planets"] else ""))
        L.append("\nD9 CONJUNCTIONS: " + ("; ".join(f"H{c['house']}: {' + '.join(c['planets'])}" for c in k["conjunctions"]["D9"]) or "none"))
        L.append("D9 YOGAS (rule-based): " + ("; ".join(k["d9_yogas"]) or "none"))
        kn = k["knrao"]
        dk = next(x for x in kn["karakas"] if x["code"] == "DK")
        L.append(f"Darakaraka (spouse) = {dk['planet']}; Upapada Lagna = {kn['upapada']['sign_name']} (H{kn['upapada']['house']} from D1 lagna); "
                 f"Karakamsha = {kn['karakamsha']['sign_name']} (AK {kn['karakamsha']['atmakaraka']}).")
        L.append("Functional nature (D1 lagna): " + "; ".join(f"{p}: {v['nature']}" for p, v in kn["functional"].items()))
    d = k["dasha"]
    L.append(f"\nVIMSHOTTARI: birth nakshatra {d['moon_nakshatra']['name']} pada {d['moon_nakshatra']['pada']}, "
             f"balance at birth {d['balance_at_birth']}. CURRENT: {d['current']['mahadasha']} Mahadasha (till {d['current']['md_end']}) / "
             f"{d['current']['antardasha']} Antardasha (till {d['current']['ad_end']}).")
    seq = []
    for m in d["mahadashas"]:
        if m["end"] >= dt.date.today().isoformat() and len(seq) < 3:
            seq.append(f"{m['lord']} MD {m['start']}→{m['end']}: " +
                       ", ".join(f"{a['lord']}({a['start'][:7]}→{a['end'][:7]})" for a in m["antardashas"]
                                 if a["end"] >= dt.date.today().isoformat()))
    L.append("Upcoming: " + " | ".join(seq))
    L.append(f"\nToday's date: {dt.date.today().isoformat()}")
    return "\n".join(L)


def jaimini_sheet(k: dict) -> str:
    kn = k["knrao"]
    L = ["\nJAIMINI (as used by K.N. Rao):",
         "Chara karakas (7-karaka scheme): " + ", ".join(f"{x['code']}={x['planet']} ({x['deg_in_sign']}°)" for x in kn["karakas"]),
         f"Karakamsha (AK {kn['karakamsha']['atmakaraka']} in D9): {kn['karakamsha']['sign_name']}",
         f"Arudha Lagna (AL): {kn['arudha_lagna']['sign_name']} = H{kn['arudha_lagna']['house']} | "
         f"Upapada (UL): {kn['upapada']['sign_name']} = H{kn['upapada']['house']}",
         "Rashi drishti (sign aspects): " + "; ".join(
             f"{d['from_sign'].split()[0]} [{', '.join(d['planets'])}] → {', '.join(x.split()[0] for x in d['aspects_signs'])}"
             + (f" (aspects {', '.join(d['aspects_planets'])})" if d["aspects_planets"] else "") for d in kn["rashi_drishti"])]
    cd = kn["chara_dasha"]
    today = dt.date.today().isoformat()
    L.append(f"\nCHARA DASHA (K.N. Rao method: from lagna, {cd['direction']} since 9th from lagna is {cd['ninth_from_lagna']}; "
             f"no exaltation/debilitation adjustment). CURRENT: {cd['current']['mahadasha']} MD till {cd['current']['md_end']}, "
             f"{cd['current']['antardasha']} AD till {cd['current']['ad_end']}.")
    L.append("Chara MD sequence: " + "; ".join(
        f"{p['sign_name'].split()[0]} {p['start'][:4]}–{p['end'][:4]} ({p['years']}y, H{(p['sign'] - k['lagna']['sign']) % 12 + 1})"
        for p in [x for x in cd["periods"] if x["end"] >= today][:8]))
    cur = next((p for p in cd["periods"] if p["current"]), None)
    if cur:
        L.append("Current Chara MD antardashas: " + ", ".join(
            f"{a['sign_name'].split()[0]}({a['start'][:7]}→{a['end'][:7]})" for a in cur["antardashas"] if a["end"] >= today))
    L.append("\nDOUBLE TRANSIT of Jupiter & Saturn (houses influenced by BOTH via occupation or aspect), next 3 years:")
    for r in kn["double_transit"]:
        L.append(f"- {r['from']}→{r['to']}: Ju {r['jupiter'].split()[0]}, Sa {r['saturn'].split()[0]} → "
                 f"from Lagna H{r['houses_from_lagna']}, from Moon H{r['houses_from_moon']}")
    return "\n".join(L)


# ======================================================================
# Agent 2 — Chart analyst
# ======================================================================
ANALYST_SYSTEM = """You are the Analyst Agent of "Arundhati Nakshatra". You read charts strictly in the
tradition of Shri K.N. Rao (Bharatiya Vidya Bhavan school; Journal of Astrology): classical Parashari
principles combined with Jaimini, verified by timing. You receive a precise computed fact sheet
(Lahiri ayanamsa). Never write a generic or static horoscope — reason from THIS chart and show WHY.

K.N. Rao method — follow it in order:
1. FUNCTIONAL NATURE FIRST. Judge every planet by its functional role for this lagna (Laghu Parashari:
   trikona lords benefic, 3/6/11 lords malefic, kendradhipati dosha, yogakaraka, 2/12/8 lords by
   association) — not by natural benefic/malefic status alone.
2. THREE-FOLD HOUSE JUDGEMENT. For each bhava weigh the house itself (occupants, aspects), its lord
   (placement, dignity, aspects on it) and its karaka. Use whole-sign rashi houses as primary; mention
   Bhava Chalit only as a secondary note.
3. PROMISE THEN CONFIRMATION. A result must be promised in D1 and confirmed in the relevant varga:
   D9 for marriage and inner strength of planets, D10 for career, D7 for children. If the varga does not
   confirm, say the result is weakened or delayed.
4. YOGAS with functional lordship — Raja yoga, Dhana yoga, Viparita Raja yoga, Neecha Bhanga — and only
   if the yoga-forming planets get dashas; a yoga without its dasha gives little.
5. JAIMINI: Atmakaraka and Karakamsha for the soul's direction, Amatyakaraka for career, Darakaraka and
   Upapada for marriage, Arudha Lagna for image/status, rashi drishti between signs.
6. TIMING BY TRIPLE CHECK — K.N. Rao's hallmark: an event is predicted only when (a) the Vimshottari
   Mahadasha/Antardasha lords are connected to the house, (b) the Chara Dasha sign activates the same
   house/karakas, and (c) the double transit of Jupiter and Saturn influences that house or its lord.
   Give date windows where all three agree, and say clearly when they do not.
7. Be balanced and humane: strengths before challenges, no fear-mongering, no death predictions, no
   medical or legal certainty.

Format in Markdown with clear ## headings. Write in English with Sanskrit/Hindi terms in brackets where
natural. Do not include remedies — the Note-Taker Agent handles remedies."""

D1_TASK = """Analyse this LAGNA CHART (D1 / Janam Kundali) completely, by the K.N. Rao method.

Sections:
## Lagna, Lagna Lord & Functional Benefics/Malefics — constitution, temperament, which planets help or hurt this lagna and why
## Planet-by-Planet Analysis — every graha (Sun→Ketu): functional role, placement, dignity, lordship, nakshatra, aspects given & received, conjunctions, net result
## House-by-House Analysis — all 12 bhavas using house + lord + karaka
## Aspects & Conjunctions — key interplays and what they produce
## Yogas & Doshas — confirmed or cancelled, with reasoning, and whether their dashas come in this life
## Career (D1 promise + D10 confirmation + Amatyakaraka)
## Children (D1 5th house + D7 confirmation + Putrakaraka)
## Jaimini Indications — Atmakaraka, Karakamsha, Arudha Lagna, rashi drishti
## Chandra Kundali Perspective — mind and emotional life from the Moon
## Timing: Vimshottari + Chara Dasha + Double Transit — current period and next 10–15 years, with the date windows where all three agree
## Life Areas Summary — career, wealth, marriage, health tendencies, spirituality

CHART FACT SHEET
----------------
{facts}"""

D9_TASK = """Analyse this NAVAMSHA CHART (D9) completely, by the K.N. Rao method. D9 shows marriage and
spouse, dharma, the inner strength of planets and the fruits of the second half of life. Always
cross-check with D1 (promise in D1, confirmation in D9).

Sections:
## Navamsha Lagna & Its Lord
## Planetary Strength D1 vs D9 — gains/losses of strength, vargottama planets, D9 dignities, functional role carried from D1
## Planet-by-Planet in D9 — placement, house, aspects, conjunctions
## Marriage — D1 7th house and lord, D9 7th house and lord, Venus/Jupiter, Darakaraka, Upapada Lagna; nature of spouse and harmony
## Marriage Timing — Vimshottari + Chara Dasha + Jupiter–Saturn double transit on the 7th house/lord (from Lagna and Moon)
## Dharma & Spiritual Path — D9 9th/5th/12th, Karakamsha
## Yogas in D9
## How D9 Modifies the D1 Promise

D1 CONTEXT
----------
{d1facts}

NAVAMSHA FACT SHEET
-------------------
{facts}"""


DEPTH = ("Write it as a warm, personal LIFE GUIDE addressed to the native ('you'), in the depth of K.N. Rao's case studies. "
         "For every topic use this pattern: **What it means** (explain the concept simply), **In your chart** (name the exact placements), "
         "**How it plays out** (concrete life experiences, with ages/dates where the dashas allow), **Guidance** (practical do's and don'ts). "
         "Keep a one-line '🔎 Technical basis:' note under each topic listing the placements used. No generic sentences that could fit any chart; "
         "never fatalistic; no death or medical certainty. Use the headings given.")
SECTION_TASKS = {
    "Who you are":
        "Write '# Your Life Guide — <name>' with a short note on how to read it, then '## Part 1 · Who You Are' with ### sub-sections: "
        "Your Rising Sign (personality, strengths, growth areas, body, rising nakshatra, planets in lagna, the chart ruler's placement), "
        "Your Mind (Moon sign, birth nakshatra, house), Your Soul (Sun), and Planets That Help You and Planets That Test You "
        "(functional benefics/malefics/yogakaraka explained). " + DEPTH,
    "Your planets":
        "Write '## Part 2 · Your Nine Planets' with a ### sub-section for EACH graha (Sun→Ketu): what it represents, its placement, "
        "condition in D1 and D9, every house it rules and what that means (bhavat-bhavam), star lord, conjunctions and aspects, special "
        "states (neecha bhanga, retrograde, combust, vargottama), how it shows up in life, and guidance. 150+ words per planet. " + DEPTH,
    "Life areas":
        "Write '## Part 3 · The Twelve Areas of Your Life' with a ### sub-section for EACH house 1–12 using the three-fold method "
        "(house, ruler, karaka) plus the D7/D9/D10 check for the 5th/7th/10th, a clear verdict, how it plays out, and guidance. "
        "120+ words per house. " + DEPTH,
    "Yogas and soul":
        "Write '## Part 4 · Special Combinations in Your Chart (Yogas)' — confirm or reject each yoga with reasons, explain what it does "
        "and in which dasha it activates — and '## Part 5 · Your Soul's Purpose (Jaimini Astrology)' — Atmakaraka, Karakamsha, "
        "Amatyakaraka and suitable careers, Darakaraka and spouse, Arudha Lagna, Upapada. " + DEPTH,
    "Chapters and dates":
        "Write '## Part 6 · The Chapters of Your Life (Dashas)' — a brief look back at past mahadashas, then the current mahadasha and "
        "EVERY remaining antardasha in depth (themes, how it feels, what to do), then the next mahadasha; read alongside the running "
        "Chara Dasha. Then '## Part 7 · Important Dates Ahead' — the triple-check windows for career, marriage, children, property, "
        "finance and travel, what is likely and how confident. End with '## Part 8 · Your Personal Guidance Summary' — blessings, areas "
        "to nurture, and 10 practical guidance points. " + DEPTH,
    "Navamsha":
        "Write '# Navamsha Guide — Marriage, Inner Strength & Dharma': what D9 is; ## Your Navamsha Lagna; ## How Strong Your Planets "
        "Really Are (### per planet, D1 → D9, vargottama, what it changes in life); ## Marriage and Your Spouse (D1 7th + D9 7th + Venus/"
        "Jupiter + Darakaraka + Upapada — nature of spouse, harmony, challenges, guidance); ## Marriage Timing (triple check); "
        "## Your Dharma and Spiritual Path; ## How the Navamsha Modifies Your Birth Chart. " + DEPTH,
}


class AnalystAgent:
    name = "Analyst Agent"

    def analyse(self, pid: str, chart: str) -> Iterator[str]:
        import interpret  # noqa: F401
        k = storage.get_profile(pid)["kundali"]
        fname = "report_d1.md" if chart == "D1" else "report_d9.md"
        buf: list[str] = []

        def emit(t):
            buf.append(t)
            return t
        try:
            import guide
            if not full_reports_available():
                yield emit("> 🌸 Your personal guide, prepared by the Arundhati Nakshatra K.N. Rao engine. "
                           "Have a question? Tap **✨ Ask your Kundali**.\n\n")
                yield emit("\n".join(b for _, b in guide.guide_d1(k)) if chart == "D1" else guide.guide_d9(k))
                return
            facts = chart_fact_sheet(k, "D1") + ("\n\n" + chart_fact_sheet(k, "D9") if chart == "D9" else "")
            if chart == "D1":
                plan = [(title, body, SECTION_TASKS[title]) for title, body in guide.guide_d1(k)]
            else:
                plan = [("Navamsha", guide.guide_d9(k) + "\n\n" + interpret.full_d9(k), SECTION_TASKS["Navamsha"])]
            for i, (title, evidence, task) in enumerate(plan):
                yield emit("\n\n" if i else "")
                prompt = (f"CHART FACT SHEET\n----------------\n{facts}\n\n"
                          f"COMPUTED GUIDE DRAFT for this part (from the K.N. Rao engine — keep its facts and verdicts unless you can show "
                          f"from the chart why they are wrong; go much deeper and make it personal)\n----------------\n{evidence}\n\n"
                          f"TASK\n----\n{task}")
                for t in _stream(ANALYST_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=12000):
                    yield emit(t)
        finally:
            if buf:
                storage.save_text(pid, fname, "".join(buf))

    def ask(self, pid: str, question: str) -> Iterator[str]:
        import chat
        yield from chat.ask(pid, question)


# ======================================================================
# Agent 3 — Appointment booking
# ======================================================================
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def available_slots(date: str) -> list[str]:
    a = storage.get_astrologer()
    d = dt.date.fromisoformat(date)
    tz = ZoneInfo(a.get("timezone", "Asia/Kolkata"))
    now = dt.datetime.now(tz)
    if d < now.date() or DAYS[d.weekday()] not in a["working_days"]:
        return []
    step = int(a.get("slot_minutes", 45))
    t = dt.datetime.combine(d, dt.time.fromisoformat(a["start_time"]), tz)
    end = dt.datetime.combine(d, dt.time.fromisoformat(a["end_time"]), tz)
    taken = {x["time"] for x in storage.list_appointments() if x["date"] == date and x.get("status") != "cancelled"}
    out = []
    while t + dt.timedelta(minutes=step) <= end:
        s = t.strftime("%H:%M")
        if s not in taken and t > now:
            out.append(s)
        t += dt.timedelta(minutes=step)
    return out


def book(name: str, phone: str, date: str, time: str, service: str, email: str = "",
         notes: str = "", profile_id: str = "", mode: str = "Video call") -> dict:
    if time not in available_slots(date):
        return {"ok": False, "error": f"{date} {time} is not available. Free slots: {available_slots(date)[:8]}"}
    appt = storage.add_appointment({"name": name, "phone": phone, "email": email, "date": date, "time": time,
                                    "service": service, "mode": mode, "notes": notes, "profile_id": profile_id,
                                    "created": dt.datetime.now().isoformat(timespec="seconds")})
    return {"ok": True, "appointment": appt}


BOOKING_TOOLS = [
    {"name": "get_astrologer_profile", "description": "Get the astrologer's profile: name, bio, services with durations, working days and hours.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "check_availability", "description": "List free appointment start times (HH:MM, astrologer's timezone) for a date.",
     "input_schema": {"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}}, "required": ["date"]}},
    {"name": "book_appointment", "description": "Book a confirmed slot. Only call after the client has confirmed date, time, service, name and phone.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}, "phone": {"type": "string"}, "email": {"type": "string"},
         "date": {"type": "string"}, "time": {"type": "string"}, "service": {"type": "string"},
         "mode": {"type": "string", "enum": ["Video call", "Phone call", "In person"]},
         "notes": {"type": "string", "description": "Client's questions/concerns for the session"}},
         "required": ["name", "phone", "date", "time", "service"]}},
    {"name": "find_my_appointments", "description": "Look up existing appointments by phone number.",
     "input_schema": {"type": "object", "properties": {"phone": {"type": "string"}}, "required": ["phone"]}},
    {"name": "cancel_appointment", "description": "Cancel an appointment by id after the client confirms.",
     "input_schema": {"type": "object", "properties": {"appointment_id": {"type": "string"}}, "required": ["appointment_id"]}},
]


class BookingAgent:
    name = "Booking Agent"

    def _system(self, pid: str | None) -> str:
        a = storage.get_astrologer()
        tz = ZoneInfo(a.get("timezone", "Asia/Kolkata"))
        s = (f"You are the Appointment Agent of Arundhati Nakshatra. You book Kundali analysis consultations "
             f"with the astrologer {a['name']}. Be warm, brief and efficient (2-4 sentences per reply). "
             f"Today is {dt.datetime.now(tz).strftime('%A %Y-%m-%d %H:%M')} ({a.get('timezone')}). "
             "Steps: understand what the client wants help with → suggest the right service → "
             "check availability → offer 3-5 slots → collect name and phone (email optional) and preferred mode → "
             "read the details back and get a yes → book_appointment → share the appointment ID. "
             "Never mention fees, prices, amounts or payment — if asked, say the astrologer will discuss it personally. "
             "Never invent slots; always use the tools. Interpret relative dates like 'tomorrow' or 'Saturday' yourself.")
        if pid:
            p = storage.get_profile(pid)
            if p:
                b = p["birth"]
                s += (f"\nThe client is likely {b['name']} (born {b['date']} {b['time']}, {b.get('place', '')}); "
                      f"their kundali is saved (profile id {pid}). Prefill their name and attach the profile.")
        return s

    def _tool(self, name: str, args: dict, pid: str | None):
        if name == "get_astrologer_profile":
            return storage.get_astrologer()
        if name == "check_availability":
            return {"date": args["date"], "free_slots": available_slots(args["date"])}
        if name == "book_appointment":
            return book(profile_id=pid or "", **args)
        if name == "find_my_appointments":
            digits = "".join(c for c in args["phone"] if c.isdigit())[-10:]
            return [x for x in storage.list_appointments() if "".join(c for c in x["phone"] if c.isdigit())[-10:] == digits]
        if name == "cancel_appointment":
            return storage.update_appointment(args["appointment_id"], status="cancelled") or {"error": "not found"}
        return {"error": "unknown tool"}

    def chat(self, messages: list, pid: str | None = None) -> dict:
        """messages: [{role, content(str)}]. Returns {reply, booked}."""
        if not llm_available():
            return {"reply": "Please use the booking form to choose a date and time — it only takes a moment. 🌸", "booked": None}
        msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
        return self._chat_json(msgs, pid)

    def _chat_json(self, msgs: list, pid: str | None) -> dict:
        """Tool use for providers without native tools: the model replies with an ACTION line we execute."""
        import re as _re
        tools = "\n".join(f"- {t['name']}: {t['description']} Args: {json.dumps(t['input_schema'].get('properties', {}))}" for t in BOOKING_TOOLS)
        system = (self._system(pid) + "\n\nYou can use these tools:\n" + tools +
                  "\n\nTo use a tool, reply with ONLY one line: ACTION: {\"tool\": \"<name>\", \"args\": {...}} "
                  "and nothing else. You will then receive the RESULT. When you are ready to talk to the client, reply normally "
                  "without any ACTION line.")
        booked = None
        convo = list(msgs)
        for _ in range(6):
            reply = llm.complete(system, convo, max_tokens=700).strip()
            m = _re.search(r"ACTION:\s*(\{.*\})", reply, _re.S)
            if not m:
                return {"reply": reply, "booked": booked}
            act = {}
            try:
                act = json.loads(m.group(1))
                out = self._tool(act.get("tool", ""), act.get("args", {}) or {}, pid)
            except Exception as e:
                out = {"error": f"could not run tool: {e}"}
            if act.get("tool") == "book_appointment" and isinstance(out, dict) and out.get("ok"):
                booked = out["appointment"]
            convo += [{"role": "assistant", "content": reply},
                      {"role": "user", "content": "RESULT: " + json.dumps(out, default=str)[:3000]}]
        return {"reply": "Sorry, I got stuck. Please try again or use the booking form.", "booked": booked}


# ======================================================================
# Agent 4 — Note taker + remedies
# ======================================================================
NOTES_SYSTEM = """You are the Note-Taker Agent of "Arundhati Nakshatra" (K.N. Rao school). You read the full
Lagna (D1) and Navamsha (D9) reports plus the dasha and transit data, and produce a crisp, practical
summary the native can keep.

Output Markdown with these sections:
## At a Glance — 5–7 bullet crux points (the most important truths of this chart)
## Functional Benefics & Malefics — one line: which planets support this lagna and which test it
## Strengths — key blessings / yogas that will actually fructify (their dashas come)
## Watch-outs — challenges, doshas, weak or afflicted functional benefics, strong functional malefics
## Life Areas — one line each: Career, Wealth, Marriage, Children, Health tendencies, Spirituality
## Current Period — running Vimshottari MD/AD and Chara Dasha MD/AD, and the current Jupiter–Saturn double transit, with what they mean and until when
## Key Date Windows — upcoming windows where Vimshottari, Chara Dasha and double transit agree, and for what
## Remedies (Upaya) — only for planets that need it in THIS chart, each with the reason. Prefer simple,
   sattvic, non-commercial remedies: mantra/japa of the planet or its deity (with count), prayer and
   devotion (e.g. Hanuman Chalisa, Vishnu Sahasranama, Durga Saptashati, Aditya Hridayam as fitting),
   fasting (vrat), charity (daan) of the planet's items, service (seva) and behavioural correction.
   Strengthen functional benefics; pacify functional malefics — never strengthen a functional malefic.
   Gemstones: mention only as optional for a functional benefic, after expert consultation, and never as
   the main remedy.
## Questions to Discuss in Consultation — 3-5 questions worth raising with the astrologer

Be concise and specific. End with a one-line note that astrology is guidance, not a substitute for
medical, legal or financial advice."""

REMEDIES = {
    "Sun": ("Om Hraam Hreem Hraum Sah Suryaya Namah", "Sunday", "Offer water (Arghya) to the rising Sun; donate wheat/jaggery", "Ruby (Manik), gold, ring finger"),
    "Moon": ("Om Shraam Shreem Shraum Sah Chandraya Namah", "Monday", "Worship Lord Shiva; donate rice/milk/white cloth", "Pearl (Moti), silver, little finger"),
    "Mars": ("Om Kraam Kreem Kraum Sah Bhaumaya Namah", "Tuesday", "Hanuman Chalisa; donate red lentils (masoor)", "Red Coral (Moonga), copper/gold, ring finger"),
    "Mercury": ("Om Braam Breem Braum Sah Budhaya Namah", "Wednesday", "Worship Lord Ganesha; donate green moong; feed cows", "Emerald (Panna), gold, little finger"),
    "Jupiter": ("Om Graam Greem Graum Sah Gurave Namah", "Thursday", "Respect teachers; donate chana dal/turmeric/yellow cloth", "Yellow Sapphire (Pukhraj), gold, index finger"),
    "Venus": ("Om Draam Dreem Draum Sah Shukraya Namah", "Friday", "Worship Goddess Lakshmi; donate white sweets/curd", "Diamond/White Sapphire, silver/platinum, middle finger"),
    "Saturn": ("Om Praam Preem Praum Sah Shanaischaraya Namah", "Saturday", "Serve the elderly and labourers; donate black sesame/mustard oil", "Blue Sapphire (Neelam) — only after trial and expert advice"),
    "Rahu": ("Om Bhraam Bhreem Bhraum Sah Rahave Namah", "Saturday", "Durga worship; feed stray dogs; donate blankets", "Hessonite (Gomed) — only on expert advice"),
    "Ketu": ("Om Sraam Sreem Sraum Sah Ketave Namah", "Tuesday", "Ganesha worship; donate to spiritual causes", "Cat's Eye (Lehsunia) — only on expert advice"),
}


class NoteTakerAgent:
    name = "Note-Taker Agent"

    def summarise(self, pid: str) -> Iterator[str]:
        prof = storage.get_profile(pid)
        k = prof["kundali"]
        if not full_reports_available():
            text = offline_notes(k)
            storage.save_text(pid, "notes.md", text)
            yield text
            return
        d1 = prof["reports"]["d1"] or "(D1 report not generated yet — work from the fact sheet)"
        d9 = prof["reports"]["d9"] or "(D9 report not generated yet — work from the fact sheet)"
        chat = "\n".join(f"{m['role']}: {m['content']}" for m in prof["chat"][-8:])
        content = (f"FACT SHEET D1\n{chart_fact_sheet(k, 'D1')}\n\nFACT SHEET D9\n{chart_fact_sheet(k, 'D9')}\n\n"
                   f"=== LAGNA REPORT ===\n{d1}\n\n=== NAVAMSHA REPORT ===\n{d9}\n\n=== FOLLOW-UP Q&A ===\n{chat or 'none'}")
        buf = []
        try:
            for t in _stream(NOTES_SYSTEM, [{"role": "user", "content": content}], max_tokens=6000):
                buf.append(t)
                yield t
        finally:
            if buf:
                storage.save_text(pid, "notes.md", "".join(buf))


# ======================================================================
# Offline (no API key) fallbacks — basic rule-based text
# ======================================================================
def _planet_line(p: dict, meaning: dict) -> str:
    tone = {"Exalted": "very strong and gives excellent results", "Moolatrikona": "strong and well placed",
            "Own sign": "comfortable and strong", "Friendly sign": "reasonably supported",
            "Neutral sign": "of moderate strength", "Enemy sign": "under some strain",
            "Debilitated": "weak and needs support", "—": "a karmic node amplifying its house"}[p["dignity"]]
    extra = []
    if p["retrograde"]:
        extra.append("retrograde (results turn inward and may come after delay or revision)")
    if p["combust"]:
        extra.append("combust (its significations are overshadowed by the Sun)")
    if p["vargottama"]:
        extra.append("vargottama (same sign in D1 and D9 — gains reliability)")
    lord = f" As lord of house(s) {', '.join(map(str, p['lord_of']))}, it carries those matters into house {p['house']}." if p["lord_of"] else ""
    return (f"**{p['name']}** in {p['sign_name']}, house {p['house']} ({meaning[p['house']]}), "
            f"{p['nakshatra']} pada {p['pada']}: {tone}." + lord + (" It is " + "; ".join(extra) + "." if extra else ""))


def offline_report(k: dict, chart: str) -> str:
    out = ["> Basic offline mode — add a free Gemini or Groq key in My Profile for the full AI analysis.\n"]
    if chart == "D1":
        lg = k["lagna"]
        out.append(f"## Lagna\n{lg['sign_name']} rising at {lg['degree']} ({lg['nakshatra']} pada {lg['pada']}). Lagna lord **{lg['lord']}**.")
        out.append("## Planets")
        out += ["- " + _planet_line(p, AE.HOUSE_MEANING) for p in k["planets"]]
        out.append("## Houses")
        for h in k["house_lords"]:
            occ = next(x for x in k["charts"]["D1"]["houses"] if x["house"] == h["house"])["planets"]
            out.append(f"- **H{h['house']}** ({h['meaning']}) — {h['sign']}, lord {h['lord']} in H{h['lord_in_house']}"
                       + (f"; occupied by {', '.join(p['name'] for p in occ)}" if occ else ""))
        out.append("## Aspects")
        out += [f"- {a['planet']} → {a['aspect']} aspect on H{a['house']}" + (f" ({', '.join(a['on_planets'])})" if a["on_planets"] else "") for a in k["aspects"]["D1"]]
        out.append("## Yogas\n" + ("\n".join(f"- {y}" for y in k["yogas"]) or "- None of the common yogas detected."))
    else:
        out.append(f"## Navamsha Lagna\n{AE.SIGNS[k['charts']['D9']['lagna_sign']]}")
        out.append("## Planets in D9")
        for p in k["planets"]:
            change = "" if p["navamsha_dignity"] == p["dignity"] else f" (D1: {p['dignity']})"
            out.append(f"- **{p['name']}** — {p['navamsha_sign_name']}, {p['navamsha_dignity']}{change}" + (" — vargottama" if p["vargottama"] else ""))
        out.append("## Yogas\n" + ("\n".join(f"- {y}" for y in k["d9_yogas"]) or "- None detected."))
    d = k["dasha"]["current"]
    out.append(f"## Current Dasha\n{d['mahadasha']} Mahadasha till {d['md_end']}, {d['antardasha']} Antardasha till {d['ad_end']}.")
    return "\n\n".join(out)


def offline_notes(k: dict) -> str:
    fn = k["knrao"]["functional"]
    weak = [p for p in k["planets"] if (p["dignity"] in ("Debilitated", "Enemy sign") or p["combust"])
            or fn[p["name"]]["nature"] == "Malefic"]
    d = k["dasha"]["current"]
    for lord in (d["mahadasha"], d["antardasha"]):
        if lord and all(w["name"] != lord for w in weak):
            weak.append(next(p for p in k["planets"] if p["name"] == lord))
    try:
        import guide, interpret as _i
        summary = guide.md_join(guide.part_summary(_i.Chart(k)))
    except Exception:
        summary = ""
    out = ["> 🌸 Your notes and remedies, prepared by the Arundhati Nakshatra K.N. Rao engine.\n", summary,
           "## At a Glance",
           f"- Lagna {k['lagna']['sign_name']}, Moon sign {k['moon_sign']}, nakshatra {k['dasha']['moon_nakshatra']['name']}",
           f"- Running {d['mahadasha']}–{d['antardasha']} period (till {d['ad_end']})"]
    out += [f"- Yoga: {y}" for y in k["yogas"][:4]]
    cd = k["knrao"]["chara_dasha"]["current"]
    out.append(f"- Chara Dasha: {cd['mahadasha']} MD till {cd['md_end']}, {cd['antardasha']} AD till {cd['ad_end']}")
    out.append("- Functional benefics: " + ", ".join(p for p, v in fn.items() if v["nature"] in ("Benefic", "Yogakaraka"))
               + " | malefics: " + ", ".join(p for p, v in fn.items() if v["nature"] == "Malefic"))
    try:
        import interpret
        tw = interpret.timing_windows(interpret.Chart(k))
        out.append("\n## Key Date Windows (triple check)")
        for ev, ws in tw.items():
            strong = [w for w in ws if w["strength"] == "strong"] or ws[:2]
            if strong:
                out.append(f"- **{ev}**: " + ", ".join(f"{w['from']}{'→' + w['to'] if w['to'] != w['from'] else ''}" for w in strong[:3]))
    except Exception:
        pass
    out.append("\n## Remedies (Upaya)")
    for p in weak:
        m, day, act, gem = REMEDIES[p["name"]]
        nat = fn[p["name"]]["nature"]
        gemline = (f"\n- Gemstone (optional, only after consultation): {gem}" if nat in ("Benefic", "Yogakaraka") else
                   "\n- No gemstone — this planet is not a functional benefic for your lagna; pacify it, do not strengthen it")
        out.append(f"### {p['name']} — {nat}; {p['dignity']}{', combust' if p['combust'] else ''}\n- Mantra: *{m}* — 108 times on {day}\n- {act}" + gemline)
    out.append("\n_Astrology is guidance, not a substitute for medical, legal or financial advice._")
    return "\n".join(out)
