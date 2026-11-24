// Arundhati Nakshatra — frontend
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const app = $("#app");
const api = async (url, opts = {}) => {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---------- tiny markdown renderer
function md(src) {
  const lines = (src || "").replace(/\r/g, "").split("\n");
  let html = "", inList = null, inTable = false, para = [];
  const inline = (t) => esc(t)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<em>$2</em>")
    .replace(/(^|\s)_([^_]+?)_(?=\s|[.,;:!?]|$)/g, "$1<em>$2</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
  const flush = () => { if (para.length) { html += `<p>${inline(para.join(" "))}</p>`; para = []; } };
  const closeList = () => { if (inList) { html += `</${inList}>`; inList = null; } };
  const closeTable = () => { if (inTable) { html += "</tbody></table></div>"; inTable = false; } };
  for (const raw of lines) {
    const l = raw.trimEnd();
    let m;
    if (/^\s*\|.*\|\s*$/.test(l)) {
      flush(); closeList();
      const cells = l.trim().slice(1, -1).split("|").map((c) => c.trim());
      if (cells.every((c) => /^:?-{2,}:?$/.test(c))) continue;
      if (!inTable) { html += `<div class="tablewrap"><table><thead><tr>${cells.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>`; inTable = true; }
      else html += `<tr>${cells.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`;
      continue;
    } else closeTable();
    if (!l.trim()) { flush(); closeList(); continue; }
    if ((m = l.match(/^(#{1,4})\s+(.*)/))) { flush(); closeList(); const n = Math.min(m[1].length + 1, 5); html += `<h${n}>${inline(m[2])}</h${n}>`; continue; }
    if (/^(-{3,}|\*{3,})$/.test(l.trim())) { flush(); closeList(); html += "<hr/>"; continue; }
    if (l.startsWith("🔎")) { flush(); closeList(); html += `<p class="tech">${inline(l)}</p>`; continue; }
    if ((m = l.match(/^>\s?(.*)/))) { flush(); closeList(); html += `<blockquote>${inline(m[1])}</blockquote>`; continue; }
    if ((m = l.match(/^\s*[-*•]\s+(.*)/))) { flush(); if (inList !== "ul") { closeList(); html += "<ul>"; inList = "ul"; } html += `<li>${inline(m[1])}</li>`; continue; }
    if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) { flush(); if (inList !== "ol") { closeList(); html += "<ol>"; inList = "ol"; } html += `<li>${inline(m[1])}</li>`; continue; }
    closeList(); para.push(l.trim());
  }
  flush(); closeList(); closeTable();
  return html;
}

// stream a text/plain response into an element
async function streamInto(url, el, body, onDone) {
  el.innerHTML = '<p class="muted pulse">The agent is reading the chart…</p>';
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const reader = r.body.getReader(), dec = new TextDecoder();
  let text = "", last = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    text += dec.decode(value, { stream: true });
    if (Date.now() - last > 120) { el.innerHTML = md(text) + '<span class="cursor"></span>'; last = Date.now(); }
  }
  el.innerHTML = md(text);
  onDone && onDone(text);
  return text;
}

// ---------- status badge
function paintBadge(s) {
  const b = $("#aiBadge");
  b.textContent = s.ai ? "✨ AI on" : "✿ Guide mode";
  b.className = "badge " + (s.ai ? "on" : "off");
  b.title = s.ai ? "AI chat is available" : "Answers come from the built-in K.N. Rao guide";
}
let aiStatus = { ai: false };
api("/api/status").then((s) => { aiStatus = s; paintBadge(s); if (s.login) $("#logoutLink").hidden = false; });
// installable iPhone/Android app (service worker needs https or localhost)
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
// if the login session expires, go to the login page
const _fetch = window.fetch;
window.fetch = async (...a) => { const r = await _fetch(...a); if (r.status === 401 && String(a[0]).startsWith("/api/")) location.href = "/login"; return r; };

// ---------- router
function render(tpl) { app.innerHTML = ""; app.append($(`#tpl-${tpl}`).content.cloneNode(true)); window.scrollTo(0, 0); }
function route() {
  const h = location.hash || "#/";
  $$("nav a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === h));
  if (h.startsWith("#/k/")) return viewProfile(h.slice(4));
  if (h === "#/saved") return viewSaved();
  if (h === "#/me") return viewMe();
  viewHome();
}
window.addEventListener("hashchange", route);

// ---------- intake (home)
function viewHome() {
  render("home");
  const f = $("#intake"), pin = $("#placeInput"), list = $("#placeList");
  let timer, res = [], active = -1, seq = 0;
  const choose = (r) => {
    pin.value = r.name.split(",").slice(0, 3).join(",").trim();
    f.lat.value = (+r.lat).toFixed(4); f.lon.value = (+r.lon).toFixed(4); f.tz.value = r.tz;
    $("#coordHint").textContent = `· ${(+r.lat).toFixed(3)}, ${(+r.lon).toFixed(3)} (${r.tz})`;
    pin.classList.add("picked"); list.hidden = true;
  };
  const paint = () => {
    list.innerHTML = res.length ? res.map((r, i) => `<li data-i="${i}" class="${i === active ? "active" : ""}">${esc(r.name)}
      <small>${(+r.lat).toFixed(2)}, ${(+r.lon).toFixed(2)} · ${esc(r.tz)}${r.pop ? " · pop " + (r.pop >= 1e6 ? (r.pop / 1e6).toFixed(1) + "M" : Math.round(r.pop / 1e3) + "k") : ""}${r.source ? " · " + esc(r.source) : ""}</small></li>`).join("")
      : '<li class="muted">No match. Try another spelling, add the state ("Rampur, Uttar Pradesh"), or type coordinates like 25.32, 82.97</li>';
    list.hidden = false;
    $$("li[data-i]", list).forEach((li) => li.onmousedown = (e) => { e.preventDefault(); choose(res[li.dataset.i]); });
  };
  // Free browser-side fallback: Open-Meteo geocoding (no key, CORS enabled)
  const openMeteo = async (q) => {
    try {
      const r = await fetch(`https://geocoding-api.open-meteo.com/v1/search?count=8&language=en&format=json&name=${encodeURIComponent(q.split(",")[0].trim())}`);
      const d = await r.json();
      return (d.results || []).map((x) => ({ name: [x.name, x.admin2, x.admin1, x.country].filter((v, i, a) => v && a.indexOf(v) === i).join(", "),
        lat: x.latitude, lon: x.longitude, tz: x.timezone, source: "Open-Meteo" }));
    } catch { return []; }
  };
  pin.addEventListener("input", () => {
    clearTimeout(timer);
    pin.classList.remove("picked"); f.lat.value = ""; f.lon.value = ""; $("#coordHint").textContent = "";
    const q = pin.value.trim();
    if (q.length < 2) { list.hidden = true; return; }
    list.innerHTML = '<li class="muted pulse">Searching places…</li>'; list.hidden = false;
    timer = setTimeout(async () => {
      const my = ++seq;
      let r = await api(`/api/geocode?q=${encodeURIComponent(q)}`).catch(() => []);
      if (!r.length) r = await openMeteo(q);
      if (my !== seq) return;  // a newer keystroke is in flight
      res = r; active = res.length ? 0 : -1; paint();
    }, 250);
  });
  pin.addEventListener("keydown", (e) => {
    if (list.hidden || !res.length) return;
    if (e.key === "ArrowDown") { active = (active + 1) % res.length; paint(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { active = (active - 1 + res.length) % res.length; paint(); e.preventDefault(); }
    else if (e.key === "Enter") { e.preventDefault(); choose(res[Math.max(active, 0)]); }
    else if (e.key === "Escape") list.hidden = true;
  });
  pin.addEventListener("blur", () => setTimeout(() => list.hidden = true, 150));
  pin.addEventListener("focus", () => { if (res.length && !f.lat.value) paint(); });
  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(f));
    if (!data.lat || !data.lon) {
      if (res.length) { choose(res[0]); return f.requestSubmit(); }
      $("#intakeErr").textContent = "Please pick your birth place from the suggestions (or open 'Coordinates & timezone')."; pin.focus(); return;
    }
    const btn = $("button[type=submit]", f); btn.disabled = true; btn.textContent = "Casting the chart…";
    try {
      const r = await api("/api/kundali", { method: "POST", body: JSON.stringify({ ...data, lat: +data.lat, lon: +data.lon }) });
      location.hash = `#/k/${r.id}`;
    } catch (err) { $("#intakeErr").textContent = err.message; btn.disabled = false; btn.textContent = "✿ Reveal my Kundali"; }
  });
  // lat/lon required but hidden in <details>: open it if invalid
  f.lat.addEventListener("invalid", () => $(".adv", f).open = true);
}

// ---------- saved list
async function viewSaved() {
  render("saved");
  const [ps, sess] = await Promise.all([api("/api/profiles"), api("/api/admin/session").catch(() => ({}))]);
  if (sess.admin) { $("#savedTitle").textContent = "All Kundalis"; $("#savedSub").textContent = "Admin view — every kundali created by anyone using the app."; }
  $("#savedList").innerHTML = ps.length ? ps.map((p) => `
    <a class="card saved" href="#/k/${p.id}">
      <b>${esc(p.name)}</b><span class="muted">${esc(p.date)} · ${esc(p.time?.slice(0, 5))}</span>
      <span class="muted">${esc(p.place)}</span>
      <span class="ticks">${p.has_d1 ? "<i>D1 ✓</i>" : ""}${p.has_d9 ? "<i>D9 ✓</i>" : ""}${p.has_notes ? "<i>Notes ✓</i>" : ""}</span>
    </a>`).join("") : '<p class="muted">No kundalis on this device yet. <a href="#/">Create one</a>.</p>';
}

// ---------- profile view
let current = null;
async function viewProfile(pid) {
  render("profile");
  const p = await api(`/api/profiles/${pid}`).catch(() => null);
  if (!p) { app.innerHTML = '<p class="card">Profile not found.</p>'; return; }
  current = p;
  const k = p.kundali, b = p.birth;
  $("#pName").textContent = b.name;
  $("#pMeta").textContent = `${b.date} · ${b.time.slice(0, 5)} · ${b.place} (${b.tz})`;
  const d = k.dasha.current;
  $("#pChips").innerHTML = [
    ["Lagna", k.lagna.sign_name], ["Rashi", k.moon_sign], ["Nakshatra", `${k.dasha.moon_nakshatra.name} ${k.dasha.moon_nakshatra.pada}`],
    ["Dasha", `${d.mahadasha} / ${d.antardasha}`]].map(([a, v]) => `<span class="chip"><small>${a}</small>${esc(v)}</span>`).join("");

  // tabs
  $$(".tabs button").forEach((btn) => btn.onclick = () => {
    $$(".tabs button").forEach((x) => x.classList.toggle("active", x === btn));
    $$(".tab").forEach((t) => t.hidden = t.id !== `tab-${btn.dataset.tab}`);
    if (btn.dataset.tab === "book") initBooking();
  });

  app.append($("#tpl-chat").content.cloneNode(true));
  initChat(p);
  renderKundali(k);
  if (k.knrao) renderKnRao(k);
  initAnalysis(p);
  initNotes(p);
}

function renderKundali(k) {
  const retro = Object.fromEntries(k.planets.map((p) => [p.name, p.retrograde]));
  const decorate = (ch) => ({ ...ch, houses: ch.houses.map((h) => ({ ...h, planets: h.planets.map((p) => ({ ...p, retro: retro[p.name] })) })) });
  const titles = { D1: ["Janam Kundali", "Lagna chart (D1)"], D9: ["Navamsha Kundali", "D9 — marriage & dharma"],
    D10: ["Dashamsha", "D10 — career"], D7: ["Saptamsha", "D7 — children"],
    Chandra: ["Chandra Kundali", "Moon as Lagna"], Chalit: ["Bhava Chalit", "Sripati bhava cusps"] };
  $("#charts").innerHTML = Object.entries(titles).map(([key, [t, s]]) => `
    <figure class="card chart-card"><figcaption><b>${t}</b><small>${s}</small></figcaption>${drawChart(decorate(k.charts[key]))}
    ${key === "Chalit" && k.charts.Chalit.shifted.length ? `<p class="muted tiny">Shifted: ${k.charts.Chalit.shifted.map((x) => `${x.planet} ${x.rashi_house}→${x.bhava}`).join(", ")}</p>` : ""}</figure>`).join("");

  const rows = [{ name: "Lagna", sign_name: k.lagna.sign_name, degree: k.lagna.degree, house: 1, nakshatra: k.lagna.nakshatra, pada: k.lagna.pada, nak_lord: "", dignity: "", navamsha_sign_name: k.lagna.navamsha_sign_name }, ...k.planets];
  $("#planetTable").innerHTML = `<thead><tr><th>Graha</th><th>Rashi</th><th>Degree</th><th>House</th><th>Nakshatra</th><th>Pada</th><th>Nak. Lord</th><th>Dignity</th><th>Functional</th><th>D9</th><th>D10</th><th></th></tr></thead><tbody>` +
    rows.map((p) => `<tr><td><b>${p.name}</b></td><td>${p.sign_name}</td><td>${p.degree}</td><td>${p.house}</td><td>${p.nakshatra}</td><td>${p.pada}</td><td>${p.nak_lord}</td>
    <td><span class="dig ${(p.dignity || "").split(" ")[0].toLowerCase()}">${p.dignity}</span></td><td><span class="fn ${(p.functional || "").split(" ")[0].toLowerCase()}">${p.functional || ""}</span></td><td>${p.navamsha_sign_name}</td><td>${p.d10_sign_name || ""}</td>
    <td class="flags">${p.retrograde ? "<i title='Retrograde'>R</i>" : ""}${p.combust ? "<i title='Combust'>C</i>" : ""}${p.vargottama ? "<i title='Vargottama'>V</i>" : ""}</td></tr>`).join("") + "</tbody>";

  const D = k.dasha;
  $("#dashaHead").innerHTML = `Birth nakshatra <b>${D.moon_nakshatra.name}</b> (pada ${D.moon_nakshatra.pada}), balance at birth <b>${D.balance_at_birth}</b>. Running <b>${D.current.mahadasha}</b> Mahadasha till ${D.current.md_end}, <b>${D.current.antardasha}</b> Antardasha till ${D.current.ad_end}.`;
  $("#dasha").innerHTML = D.mahadashas.slice(0, 10).map((m) => `
    <details class="md-row ${m.current ? "current" : ""}" ${m.current ? "open" : ""}>
      <summary><b>${m.lord}</b> Mahadasha <span class="muted">${m.years} yrs</span><span class="dates">${m.start} → ${m.end}</span></summary>
      <div class="antars">${m.antardashas.map((a) => `<div class="${a.current ? "current" : ""}"><b>${m.lord.slice(0, 2)}–${a.lord}</b><span>${a.start} → ${a.end}</span></div>`).join("")}</div>
    </details>`).join("");
}

function renderKnRao(k) {
  const kn = k.knrao, short = (s) => s.split(" ")[0];
  $("#jaimini").innerHTML = `<div class="kgrid">${kn.karakas.map((x) => `<div><b>${x.code}</b><span>${x.planet}</span><small>${x.name} · ${x.signifies}</small></div>`).join("")}</div>
    <p class="tiny muted">Karakamsha: <b>${kn.karakamsha.sign_name}</b> (AK ${kn.karakamsha.atmakaraka}) · Arudha Lagna: <b>${kn.arudha_lagna.sign_name}</b> (H${kn.arudha_lagna.house}) · Upapada: <b>${kn.upapada.sign_name}</b> (H${kn.upapada.house})</p>`;
  $("#functional").innerHTML = Object.entries(kn.functional).map(([p, v]) => `<div class="fnrow"><b>${p}</b><span class="fn ${v.nature.split(" ")[0].toLowerCase()}">${v.nature}</span><small class="muted">${esc(v.reason)}</small></div>`).join("");
  const cd = kn.chara_dasha;
  $("#charaHead").innerHTML = `Starts from Lagna, runs <b>${cd.direction}</b> (9th from Lagna is ${cd.ninth_from_lagna}). Current: <b>${cd.current.mahadasha}</b> MD till ${cd.current.md_end}, <b>${cd.current.antardasha}</b> AD till ${cd.current.ad_end}.`;
  $("#chara").innerHTML = cd.periods.slice(0, 14).map((m) => `
    <details class="md-row ${m.current ? "current" : ""}" ${m.current ? "open" : ""}>
      <summary><b>${m.sign_name}</b> <span class="muted">H${(m.sign - k.lagna.sign + 12) % 12 + 1} · ${m.years} yrs${m.cycle === 2 ? " · 2nd cycle" : ""}</span><span class="dates">${m.start} → ${m.end}</span></summary>
      <div class="antars">${m.antardashas.map((a) => `<div class="${a.current ? "current" : ""}"><b>${short(m.sign_name)}–${short(a.sign_name)}</b><span>${a.start} → ${a.end}</span></div>`).join("")}</div>
    </details>`).join("");
  $("#transit").innerHTML = `<thead><tr><th>Period</th><th>Jupiter</th><th>Saturn</th><th>Houses from Lagna</th><th>Houses from Moon</th></tr></thead><tbody>` +
    kn.double_transit.map((r) => `<tr><td>${r.from}${r.to !== r.from ? " → " + r.to : ""}</td><td>${short(r.jupiter)}</td><td>${short(r.saturn)}</td>
    <td>${r.houses_from_lagna.map((h) => `<span class="hchip">${h}</span>`).join("") || "—"}</td><td>${r.houses_from_moon.map((h) => `<span class="hchip m">${h}</span>`).join("") || "—"}</td></tr>`).join("") + "</tbody>";
}

function initAnalysis(p) {
  let chart = "D1";
  const show = () => {
    const txt = current.reports[chart.toLowerCase()];
    $("#report").innerHTML = txt ? md(txt) : `<p class="muted">No ${chart === "D1" ? "Lagna" : "Navamsha"} analysis yet. Click <b>Generate analysis</b> — the Analyst Agent will study every graha, house, aspect, yoga and the dasha timeline.</p>`;
    $("#genReport").textContent = txt ? "Regenerate" : "Generate analysis";
    $("#reportState").textContent = txt ? "Saved to your data folder." : "";
  };
  $$(".subtabs button[data-chart]").forEach((b) => b.onclick = () => { $$(".subtabs button[data-chart]").forEach((x) => x.classList.toggle("active", x === b)); chart = b.dataset.chart; show(); });
  $("#genReport").onclick = async () => {
    const btn = $("#genReport"); btn.disabled = true; $("#reportState").textContent = "Analysing… (the AI writes section by section; a full report takes 3–6 minutes)";
    const which = chart;
    const t = await streamInto(`/api/profiles/${p.id}/analyse/${which}`, $("#report")).catch((e) => { $("#report").textContent = e.message; });
    if (t) current.reports[which.toLowerCase()] = t;
    btn.disabled = false; btn.textContent = "Regenerate"; $("#reportState").textContent = "Saved to your data folder.";
  };
  show();
}

// ---------- floating kundali chat
async function initChat(p) {
  const panel = $("#chatPanel"), log = $("#chatLog"), form = $("#chatForm"), ta = $("textarea", form);
  $("#chatWho").textContent = `${p.birth.name} · ${p.kundali.lagna.sign_name.split(" (")[0]} Lagna · ${p.kundali.dasha.current.mahadasha}–${p.kundali.dasha.current.antardasha} dasha`;
  const foot = () => $("#chatFoot").innerHTML = aiStatus.ai ? "AI answers use your chart and the K.N. Rao method" : "Answers come from your personal K.N. Rao guide";
  // ---- free-question counter
  let q = null;
  const paintQuota = () => {
    const pill = $("#qPill"), out = $("#qOut");
    if (!q || !q.ai) { pill.hidden = true; out.hidden = true; form.hidden = false; return; }
    pill.hidden = false;
    pill.textContent = q.remaining > 0 ? `${q.remaining} of ${q.total} free left` : "0 questions left";
    pill.classList.toggle("low", q.remaining <= 1);
    out.hidden = q.remaining > 0; form.hidden = q.remaining <= 0;
    if (q.remaining <= 0) $("#chatChips").hidden = true;
  };
  const loadQuota = async () => { q = await api(`/api/profiles/${p.id}/quota`).catch(() => null); paintQuota(); };
  $("#qBook").onclick = () => { $("#chatClose").click(); $('.tabs button[data-tab="book"]').click(); window.scrollTo(0, 0); };
  $("#qCode").onsubmit = async (e) => {
    e.preventDefault();
    const inp = $("input", e.target);
    try {
      const r = await api(`/api/profiles/${p.id}/redeem`, { method: "POST", body: JSON.stringify({ code: inp.value }) });
      q = { ...q, ...r }; inp.value = ""; $("#qMsg").innerHTML = `<span class="ok">${esc(r.message)}</span>`; paintQuota();
      setTimeout(() => { $("#qMsg").textContent = ""; ta.focus(); }, 2500);
    } catch (err) { $("#qMsg").innerHTML = `<span class="err">${esc(err.message)}</span>`; }
  };
  const bubble = (m) => `<div class="msg ${m.role}">${m.role === "user" ? esc(m.content) : md(m.content)}</div>`;
  const paint = () => {
    log.innerHTML = current.chat.length ? current.chat.map(bubble).join("")
      : `<div class="msg assistant"><p>Namaste ${esc(p.birth.name.split(" ")[0])} 🌸 I have studied your kundali — your Lagna, Navamsha, dashas and transits.</p><p>Ask me anything, in English or Hindi.</p></div>`;
    log.scrollTop = log.scrollHeight;
  };
  const sugg = await api("/api/chat/suggestions").catch(() => []);
  $("#chatChips").innerHTML = sugg.map((q) => `<button type="button" class="chip-q">${esc(q)}</button>`).join("");
  $$("#chatChips .chip-q").forEach((b) => b.onclick = () => { ta.value = b.textContent; form.requestSubmit(); });
  const open = () => { panel.hidden = false; $(".chat-fab").hidden = true; foot(); paint(); loadQuota(); setTimeout(() => ta.focus(), 50); };
  $$(".open-chat").forEach((b) => b.onclick = open);
  $("#chatClose").onclick = () => { panel.hidden = true; $(".chat-fab").hidden = false; };
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
  ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 120) + "px"; });
  form.onsubmit = async (e) => {
    e.preventDefault();
    const qText = ta.value.trim(); if (!qText) return;
    ta.value = ""; ta.style.height = "auto";
    if (!current.chat.length) log.innerHTML = "";
    log.insertAdjacentHTML("beforeend", bubble({ role: "user", content: qText }) + '<div class="msg assistant"></div>');
    const el = log.lastElementChild;
    $("#chatChips").hidden = true;
    const btn = $("button", form); btn.disabled = true;
    const qEl = el.previousElementSibling;
    // follow the answer while it streams, but never scroll the question out of view
    const follow = setInterval(() => { log.scrollTop = Math.min(log.scrollHeight, qEl.offsetTop - 12); }, 200);
    const t = await streamInto(`/api/profiles/${p.id}/ask`, el, { question: qText }).catch((err) => (el.textContent = err.message, ""));
    clearInterval(follow); log.scrollTop = qEl.offsetTop - 12; btn.disabled = false;
    await loadQuota();
    if (!t.includes("used all")) current.chat.push({ role: "user", content: qText }, { role: "assistant", content: t });
  };
}

function initNotes(p) {
  if (current.reports.notes) { $("#notes").innerHTML = md(current.reports.notes); $("#genNotes").textContent = "Refresh notes"; }
  $("#genNotes").onclick = async () => {
    const btn = $("#genNotes"); btn.disabled = true; $("#notesState").textContent = "Reading all reports…";
    const t = await streamInto(`/api/profiles/${p.id}/notes`, $("#notes"));
    current.reports.notes = t; btn.disabled = false; btn.textContent = "Refresh notes"; $("#notesState").textContent = "Saved to your data folder.";
  };
}

// ---------- booking
let bookMsgs = [];
async function initBooking() {
  const a = await api("/api/astrologer");
  $("#astroCard").innerHTML = `<div class="avatar">${esc(a.name[0] || "A")}</div><div><b>${esc(a.name)}</b><small>${esc(a.title)}</small><p class="muted tiny">${esc(a.bio)}</p></div>`;
  $("#svcSelect").innerHTML = a.services.map((s) => `<option value="${esc(s.name)}">${esc(s.name)} — ${s.minutes} min</option>`).join("");
  const f = $("#bookForm");
  f.name.value = current.birth.name;
  const dateIn = $("#bookDate");
  dateIn.min = new Date().toISOString().slice(0, 10);
  dateIn.onchange = async () => {
    const r = await api(`/api/slots?date=${dateIn.value}`);
    $("#slotSelect").innerHTML = r.slots.length ? r.slots.map((s) => `<option>${s}</option>`).join("") : '<option value="">No free slots that day</option>';
  };
  f.onsubmit = async (e) => {
    e.preventDefault();
    try {
      const ap = await api("/api/book", { method: "POST", body: JSON.stringify({ ...Object.fromEntries(new FormData(f)), profile_id: current.id }) });
      $("#bookMsg").innerHTML = `<span class="ok">✓ Booked! ID <b>${ap.id}</b> — ${ap.date} at ${ap.time}</span>`;
      dateIn.onchange();
    } catch (err) { $("#bookMsg").innerHTML = `<span class="err">${esc(err.message)}</span>`; }
  };
  const log = $("#bookLog");
  const paint = () => log.innerHTML = bookMsgs.map((m) => `<div class="msg ${m.role}">${m.role === "user" ? esc(m.content) : md(m.content)}</div>`).join("");
  if (!bookMsgs.length) { bookMsgs = [{ role: "assistant", content: `Namaste ${esc(current.birth.name.split(" ")[0])} 🙏 I can book your kundali consultation with **${a.name}**. What would you like guidance on, and when suits you?` }]; }
  paint();
  $("#bookChat").onsubmit = async (e) => {
    e.preventDefault();
    const inp = $("input", e.target), q = inp.value.trim(); if (!q) return; inp.value = "";
    bookMsgs.push({ role: "user", content: q }); paint();
    log.insertAdjacentHTML("beforeend", '<div class="msg assistant muted pulse">…</div>');
    const r = await api("/api/booking-chat", { method: "POST", body: JSON.stringify({ messages: bookMsgs.slice(1), profile_id: current.id }) });
    bookMsgs.push({ role: "assistant", content: r.reply }); paint();
    if (r.booked) log.insertAdjacentHTML("beforeend", `<div class="booked">✓ Appointment <b>${r.booked.id}</b> confirmed — ${r.booked.date} ${r.booked.time}, ${esc(r.booked.service)}</div>`);
    log.scrollTop = log.scrollHeight;
  };
}

// ---------- my profile
async function viewMe() {
  render("me");
  const sess = await api("/api/admin/session");
  if (!sess.admin) return adminLock(sess);
  $("#adminBody").hidden = false; $("#adminLogout").hidden = false;
  $("#adminLogout").onclick = async () => { await api("/api/admin/logout", { method: "POST" }); viewMe(); };

  // --- AI assistant
  const ai = await api("/api/admin/ai");
  const pill = $("#aiPill"), keyIn = $("#keyInput");
  const paintAI = (st, msg) => {
    pill.textContent = st.ai ? "On" : "Off"; pill.className = "ai-pill " + (st.ai ? "on" : "off");
    const pv = $("input[name=provider]:checked")?.value || st.provider;
    const info = st.providers[pv];
    $("#getKey").href = info.get_key; $("#getKey").textContent = pv === "anthropic" ? "Get a key ↗" : "Get a free key ↗";
    $("#keySaved").innerHTML = st.keys_set[pv] ? `✓ A key is saved${pv === st.provider && st.key_hint ? ` (${esc(st.key_hint)})` : ""} — leave the box empty to keep it.` : "";
    keyIn.placeholder = st.keys_set[pv] ? "•••••••• saved" : (pv === "gemini" ? "AIza…" : pv === "groq" ? "gsk_…" : "sk-ant-…");
    $$(".prov").forEach((l) => l.classList.toggle("sel", $("input", l).checked));
    if (msg !== undefined) $("#aiMsg").innerHTML = msg;
  };
  $(`input[name=provider][value=${ai.provider}]`).checked = true;
  $("#aiForm").model.value = ai.model && ai.model !== "auto" ? "" : "";
  paintAI(ai, ai.ai ? `<span class="ok">Working with ${esc(ai.provider_label)} · model ${esc(ai.model)}</span>` : '<span class="muted">Not set up yet — the chat answers from the built-in guide until you add a key.</span>');
  $$("input[name=provider]").forEach((r) => r.onchange = () => paintAI(ai));
  $("#keyEye").onclick = () => { const sh = keyIn.type === "password"; keyIn.type = sh ? "text" : "password"; $("#keyEye").textContent = sh ? "Hide" : "Show"; };
  $("#aiForm").onsubmit = async (e) => {
    e.preventDefault();
    const btn = $("#aiSave"); btn.disabled = true; btn.textContent = "Testing…";
    const body = Object.fromEntries(new FormData(e.target)); if (!body.model) delete body.model;
    const st = await api("/api/admin/ai", { method: "PUT", body: JSON.stringify(body) }).catch((err) => ({ ...ai, error: err.message }));
    btn.disabled = false; btn.textContent = "Save & test"; keyIn.value = "";
    Object.assign(ai, st);
    paintAI(ai, st.error ? `<span class="err">✗ ${esc(st.error)}</span>` : st.ai ? `<span class="ok">✓ Working! ${esc(st.provider_label)} replied “${esc(st.test_reply || "OK")}” · model ${esc(st.model)}</span>` : '<span class="err">No key saved for this provider yet.</span>');
    aiStatus = { ...aiStatus, ai: st.ai && !st.error, provider_label: st.provider_label }; paintBadge(aiStatus);
  };

  // --- free questions
  const freeNum = $("#freeNum"); freeNum.value = ai.free_questions;
  $$("#freeForm .step-btn").forEach((b) => b.onclick = () => { freeNum.value = Math.max(0, (+freeNum.value || 0) + +b.dataset.d); });
  $("#freeForm").onsubmit = async (e) => {
    e.preventDefault();
    const st = await api("/api/admin/ai", { method: "PUT", body: JSON.stringify({ free_questions: String(+freeNum.value || 0) }) });
    $("#freeMsg").textContent = `Saved ✓ — every kundali now gets ${st.free_questions} free question${st.free_questions === 1 ? "" : "s"}.`;
  };

  // --- question codes
  const paintCodes = (codes) => $("#codeList").innerHTML = codes.length ? codes.map((c) => `
    <div class="code ${c.used_by ? "used" : ""}">
      <div class="code-main"><b>${esc(c.code)}</b><span>${c.questions} questions${c.note ? " · " + esc(c.note) : ""}</span></div>
      <div class="code-side">${c.used_by ? `<small>Used by ${esc(c.used_by_name || "a client")}<br>${esc(c.used_on)}</small>`
        : `<button type="button" class="btn ghost tiny" data-copy="${esc(c.code)}">Copy</button><button type="button" class="btn ghost tiny" data-del="${esc(c.code)}">✕</button>`}</div>
    </div>`).join("") : '<p class="muted tiny">No codes yet.</p>';
  paintCodes(await api("/api/admin/codes"));
  $("#codeForm").onsubmit = async (e) => {
    e.preventDefault();
    await api("/api/admin/codes", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
    e.target.note.value = ""; paintCodes(await api("/api/admin/codes"));
  };
  $("#codeList").onclick = async (e) => {
    const c = e.target.dataset.copy, d = e.target.dataset.del;
    if (c) { try { await navigator.clipboard.writeText(c); } catch { } e.target.textContent = "Copied ✓"; setTimeout(() => e.target.textContent = "Copy", 1500); }
    if (d) { await api(`/api/admin/codes/${d}`, { method: "DELETE" }); paintCodes(await api("/api/admin/codes")); }
  };

  // --- astrologer profile
  const a = await api("/api/astrologer"), f = $("#meForm");
  for (const k of ["name", "title", "bio", "phone", "email", "location", "start_time", "end_time", "slot_minutes", "timezone"]) f[k].value = a[k] ?? "";
  f.languages.value = (a.languages || []).join(", ");
  f.services.value = a.services.map((s) => `${s.name} | ${s.minutes}`).join("\n");
  $("#daysBox").innerHTML = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => `<label class="day"><input type="checkbox" value="${d}" ${a.working_days.includes(d) ? "checked" : ""}/>${d}</label>`).join("");
  f.onsubmit = async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(f));
    d.languages = d.languages.split(",").map((x) => x.trim()).filter(Boolean);
    d.slot_minutes = +d.slot_minutes || 45;
    d.services = d.services.split("\n").map((l) => l.split("|").map((x) => x.trim())).filter((x) => x[0]).map(([name, m]) => ({ name, minutes: +m || 45 }));
    d.working_days = $$("#daysBox input:checked").map((x) => x.value);
    await api("/api/astrologer", { method: "PUT", body: JSON.stringify(d) });
    $("#meMsg").textContent = "Saved ✓";
  };

  // --- appointments
  const paint = (list) => $("#apptList").innerHTML = list.length ? list.map((x) => `
    <div class="appt ${x.status}"><div><b>${x.date} · ${x.time}</b> <span class="muted">${esc(x.mode || "")}</span><br>${esc(x.name)} · ${esc(x.phone)}<br><small>${esc(x.service)}${x.notes ? " — " + esc(x.notes) : ""}</small>
    ${x.profile_id ? `<br><a href="#/k/${x.profile_id}">Open kundali →</a>` : ""}</div>
    <div><span class="tag">${x.status}</span>${x.status !== "cancelled" ? `<button class="btn ghost tiny" data-c="${x.id}">Cancel</button>` : ""}</div></div>`).join("") : '<p class="muted">No appointments yet.</p>';
  paint(await api("/api/appointments"));
  $("#apptList").onclick = async (e) => { const id = e.target.dataset.c; if (id) { await api(`/api/appointments/${id}/cancel`, { method: "POST" }); paint(await api("/api/appointments")); } };
}

function adminLock(sess) {
  const f = $("#adminLock"); f.hidden = false;
  if (!sess.has_password) {
    $("#lockTitle").textContent = "Create your admin password";
    $("#lockHint").textContent = "First time here — choose a password. You'll need it to open this page; clients won't see it.";
    $("#lockBtn").textContent = "Create & open";
  }
  f.onsubmit = async (e) => {
    e.preventDefault();
    try { await api("/api/admin/login", { method: "POST", body: JSON.stringify({ password: f.password.value }) }); viewMe(); }
    catch (err) { $("#lockErr").textContent = err.message; }
  };
}

route();
