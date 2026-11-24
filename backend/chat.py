"""
Kundali chat: answer questions about one saved kundali.

1. Retrieve the guide sections relevant to the question (keyword + topic map; Hindi/Hinglish words included).
2. With an AI key: send chart facts + those sections + recent chat to the AI (Gemini / Groq / Claude) and stream the answer.
3. Without a key: answer directly from the retrieved guide sections.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Iterator

import llm
import storage

TOPICS = {
    "marriage": (r"marri|shaadi|shadi|vivah|spouse|husband|wife|partner|love|relationship|wedding|pati|patni|divorce|rishta",
                 ["7th House", "Marriage", "Spouse", "Darakaraka", "Upapada", "Venus", "Navamsha"]),
    "career": (r"career|job|work|naukri|business|promotion|profession|office|boss|salary|employ|govern|sarkari",
               ["10th House", "Career", "Amatyakaraka", "Saturn", "Sun", "6th House"]),
    "money": (r"money|wealth|\bdhan|finance|income|\brich\b|savings|invest|paisa|\bloan|debt|profit",
              ["2nd House", "11th House", "Financial", "Dhana", "Wealth"]),
    "children": (r"child|baby|\bkids?\b|santan|pregnan|\bson\b|daughter|progeny|\bbeta\b|\bbeti\b|bachch|bachh",
                 ["5th House", "Children", "Jupiter"]),
    "health": (r"health|disease|\bill\b|illness|sick|surgery|hospital|swasthya|bimari|weight|stress|anxiety",
               ["1st House", "6th House", "8th House", "Health", "Rising Sign"]),
    "foreign": (r"foreign|abroad|videsh|\bvisa\b|settle|relocat|overseas|\busa\b|\buk\b|canada|australia|travel",
                ["12th House", "9th House", "Foreign", "Rahu"]),
    "education": (r"educat|study|studies|exam|degree|college|padhai|phd|masters|learn",
                  ["4th House", "5th House", "Higher education", "Mercury", "Jupiter"]),
    "property": (r"property|\bhouse\b|\bhome\b|\bflat\b|\bland\b|\bcar\b|\bcars\b|vehicle|\bghar\b|makaan|\bplot\b",
                 ["4th House", "Property", "Mars"]),
    "mother": (r"mother|\bmom\b|\bmaa\b|\bmata\b|\bmummy\b", ["4th House", "Moon"]),
    "father": (r"father|\bdad\b|\bpapa\b|\bpita", ["9th House", "Sun"]),
    "siblings": (r"brother|sister|sibling|bhai|behen", ["3rd House", "11th House", "Mars"]),
    "now": (r"\bnow\b|current|this year|next year|coming|dasha|period|mahadasha|antardasha|\babhi\b|202\d|203\d",
            ["Mahadasha", "you are here", "Important Dates", "Chapters"]),
    "personality": (r"personality|nature|who am i|strength|weakness|character|swabhav",
                    ["Rising Sign", "Your Mind", "Your Soul", "Guidance Summary"]),
    "spiritual": (r"spiritual|moksha|god|dharma|meditat|religio|bhakti|purpose|soul",
                  ["Soul's Purpose", "Dharma", "12th House", "9th House", "Ketu"]),
    "yoga": (r"\byoga|raj yog|dosha|manglik|mangal|kaal sarp", ["Yogas", "Mangal Dosha", "Raja Yoga"]),
    "remedy": (r"remed|upay|upaya|mantra|gem|stone|ratna|puja|fast|vrat|donat|daan", ["Remedies", "guidance"]),
}
PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
HINDI_PLANET = {"surya": "Sun", "chandra": "Moon", "mangal": "Mars", "budh": "Mercury", "guru": "Jupiter",
                "brihaspati": "Jupiter", "shukra": "Venus", "shani": "Saturn"}
ORD = {1: "1st", 2: "2nd", 3: "3rd"}


def _sections(pid: str, k: dict) -> list[tuple[str, str]]:
    """Split the saved (or freshly built) guides into (title, text) chunks at ### / ## headings."""
    import guide
    prof = storage.get_profile(pid)
    d1 = prof["reports"].get("d1") or "\n".join(b for _, b in guide.guide_d1(k))
    d9 = prof["reports"].get("d9") or guide.guide_d9(k)
    notes = prof["reports"].get("notes") or ""
    chunks = []
    for src in (d1, d9, notes):
        title, buf = "Overview", []
        for line in src.splitlines():
            if line.startswith("## ") or line.startswith("### "):
                if buf:
                    chunks.append((title, "\n".join(buf).strip()))
                title, buf = line.lstrip("#").strip(), [line]
            else:
                buf.append(line)
        if buf:
            chunks.append((title, "\n".join(buf).strip()))
    return [c for c in chunks if len(c[1]) > 60]


def retrieve(pid: str, k: dict, question: str, limit_chars: int = 14000) -> tuple[list[str], list[tuple[str, str]]]:
    q = question.lower()
    exact = []
    for m in re.finditer(r"(\d{1,2})\s*(?:st|nd|rd|th)?\s*(?:house|bhav|bhava|ghar)", q):
        n = int(m.group(1))
        if 1 <= n <= 12:
            exact.append(f"{ORD.get(n, str(n) + 'th')} House")
    q_topics = re.sub(r"\d{1,2}\s*(?:st|nd|rd|th)?\s*(?:house|bhav|bhava|ghar)", " ", q)
    topics = [t for t, (rx, _) in TOPICS.items() if re.search(rx, q_topics)]
    wants = [w for t in topics for w in TOPICS[t][1]]
    for hi, en in HINDI_PLANET.items():
        if re.search(rf"\b{hi}", q):
            exact.append(en)
    exact += [p for p in PLANETS if re.search(rf"\b{p.lower()}\b", q)]
    WHEN = {"marriage": "💍 Marriage", "career": "💼 Career", "children": "👶 Children", "property": "🏡 Property",
            "money": "💰 Financial", "foreign": "✈️ Foreign", "education": "🎓 Higher"}
    if re.search(r"\bwhen\b|\bkab\b|timing|\byear\b|\bage\b|kitne saal|date", q):
        exact += [WHEN[t] for t in topics if t in WHEN] + ["Marriage timing" if "marriage" in topics else ""]
        exact = [e for e in exact if e]
    if not wants and not exact:
        topics = ["personality", "now"]
        wants = TOPICS["personality"][1] + TOPICS["now"][1]
    words = [w for w in re.findall(r"[a-z]{4,}", q) if w not in {"what", "when", "will", "does", "about", "have", "kundali", "chart", "tell", "there", "which", "should", "would", "could", "your"}]
    scored = []
    for title, text in _sections(pid, k):
        tl, xl = title.lower(), text.lower()
        s = (sum(6 for w in exact if w.lower() in tl) + sum(0.8 for w in exact if w.lower() in xl) +
             sum(3 for w in wants if w.lower() in tl) + sum(0.5 for w in wants if w.lower() in xl) + sum(0.3 for w in words if w in xl))
        if s > 0:
            scored.append((s, title, text))
    scored.sort(key=lambda x: -x[0])
    out, used = [], 0
    for s, title, text in scored:
        if used + len(text) > limit_chars:
            continue
        out.append((title, text))
        used += len(text)
        if len(out) >= 8:
            break
    return topics, out


CHAT_SYSTEM = """You are the astrologer-assistant of "Arundhati Nakshatra", answering questions about ONE person's
kundali in the tradition of K.N. Rao (Parashari + Jaimini; Lahiri ayanamsa). You are given the computed chart facts
and the relevant sections of the person's life guide.

Rules:
- Answer the question directly first (1–2 sentences), then explain WHY from the chart: name the exact houses, lords,
  planets, dashas, Chara Dasha and Jupiter–Saturn transits you rely on.
- For timing questions, use the Vimshottari periods and the triple-check date windows provided; give date ranges and say
  how confident they are. Never invent dates that are not supported by the data.
- Speak warmly to the person as "you". Be specific to this chart — no generic horoscope lines.
- Be balanced and kind: no fear-mongering, no predictions of death, no medical, legal or financial certainty.
  For health, advise seeing a doctor. Remedies: simple mantra, prayer, charity, service; gemstones only for functional
  benefics and only after consulting the astrologer.
- If the question needs a human consultation, suggest the Book Appointment tab.
- Reply in the language the user writes in (English, Hindi or Hinglish). Use short paragraphs and bullet points.
  Keep it to about 150–350 words unless asked for more."""


def _facts(k: dict, compact: bool) -> str:
    from agents import chart_fact_sheet
    d1 = chart_fact_sheet(k, "D1")
    if compact:
        keep = [ln for ln in d1.splitlines() if ln.startswith(("Native", "LAGNA", "Moon sign", "- ", "VIMSHOTTARI", "Upcoming", "CHARA", "FUNCTIONAL", "Today"))]
        return "\n".join(keep)[:5000]
    return d1 + "\n\n" + chart_fact_sheet(k, "D9")


def offline_answer(question: str, topics: list[str], secs: list[tuple[str, str]], k: dict) -> str:
    cur = k["dasha"]["current"]
    head = "> 🌸 Answered from your built-in K.N. Rao guide.\n\n"
    if not secs:
        return head + "I couldn't find that topic in your guide. Try asking about career, marriage, children, money, health, travel, a planet or a house number."
    intro = (f"**Here is what your chart says** about {', '.join(topics) if topics else 'your question'}. "
             f"You are currently in the **{cur['mahadasha']}–{cur['antardasha']}** period (until {cur['ad_end']}).\n\n")
    body = []
    for title, text in secs[:4]:
        lines = [ln for ln in text.splitlines()[1:] if ln.strip()]
        body.append(f"### {title}\n" + "\n".join(lines[:14]))
    return head + intro + "\n\n".join(body)


def ask(pid: str, question: str) -> Iterator[str]:
    prof = storage.get_profile(pid)
    k = prof["kundali"]
    chat = prof["chat"]
    compact = llm.is_compact()
    topics, secs = retrieve(pid, k, question, limit_chars=4000 if compact else 16000)
    buf: list[str] = []
    import quota
    try:
        if not llm.available():
            ans = offline_answer(question, topics, secs, k)
            buf.append(ans)
            yield ans
            return
        if not quota.can_ask(pid):
            q = quota.state(pid)
            ans = (f"🌸 You have used all {q['total']} of your free AI questions for this kundali.\n\n"
                   "To continue, **book a consultation** with the astrologer, or enter a **question code** if you have one.")
            yield ans          # not saved to the chat history
            return
        ctx = (f"CHART FACTS\n-----------\n{_facts(k, compact)}\n\n"
               f"RELEVANT SECTIONS OF THE LIFE GUIDE\n-----------------------------------\n"
               + "\n\n".join(t for _, t in secs) + f"\n\nToday: {dt.date.today().isoformat()}")
        msgs = [{"role": "user", "content": ctx},
                {"role": "assistant", "content": "I have studied this kundali and its guide. Please ask your question."}]
        for m in chat[-(4 if compact else 10):]:
            msgs.append({"role": m["role"], "content": m["content"][:1500 if compact else 4000]})
        msgs.append({"role": "user", "content": question})
        for t in llm.stream(CHAT_SYSTEM, msgs, max_tokens=1200 if compact else 2500):
            buf.append(t)
            yield t
        if buf:
            quota.use_one(pid)   # count only answers the AI actually gave
    except llm.LLMError as e:
        msg = f"\n\n⚠️ {e}\n\nMeanwhile, here is what your guide says:\n\n" + offline_answer(question, topics, secs, k)
        buf.append(msg)
        yield msg
    finally:
        if buf:
            chat += [{"role": "user", "content": question}, {"role": "assistant", "content": "".join(buf)}]
            storage.save_chat(pid, chat[-60:])


SUGGESTIONS = [
    "When is a good time for marriage?",
    "What does my chart say about my career?",
    "What will my current dasha bring?",
    "Will I go abroad?",
    "What are my strengths and weaknesses?",
    "Which remedies should I follow?",
    "Mere bachchon ke baare mein kya likha hai?",
]
