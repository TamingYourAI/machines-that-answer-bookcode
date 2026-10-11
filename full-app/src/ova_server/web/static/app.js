import { BrowserVoice, RtcCall, TextCall, browserVoiceSupported } from "/static/voice.js";

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

const TRY = {
  claims: [
    "I need to report a claim. Someone backed into my car yesterday.",
    "What's the status of my claim?",
    "What's my deductible?",
    "Does my home policy include flood?",
    "Can you send me my proof of insurance?",
    "Can I speak to a person?",
  ],
  river: [
    "My kitchen drain is blocked.",
    "How much is a call-out?",
    "Are you open on Saturday?",
    "I need to cancel my visit.",
    "A pipe burst and there's water everywhere.",
  ],
};
const INTRO = {
  claims: { eyebrow: "Insurance claims, by voice", title: "Quillmere Mutual Claims Line",
    sub: "Report a claim by voice, add photos from your phone, check a claim's status, or ask about your policy. Quillmere Mutual is invented and every record is synthetic." },
  river: { eyebrow: "The Knowledge Line: the book's Appointment Line", title: "River Plumbing",
    sub: "A two-van plumbing company's booking line: book or cancel a visit, ask about hours and charges, and reach the owner in an emergency. Invented, from the book's examples." },
};

const state = {
  config: null, pack: "river", mode: "browser", signin: null, signinName: null,
  call: null, live: false, lines: new Map(), messages: 0, uploadToken: null,
  uploadClaim: null, lastPartial: null,
};

// ---------------------------------------------------------------- set-up
async function init() {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  const r = await fetch("/api/config");
  state.config = await r.json();
  const sel = $("#pack");
  for (const p of state.config.packs) {
    const o = el("option", "", p.name);
    o.value = p.id;
    sel.appendChild(o);
  }
  const params = new URLSearchParams(location.search);
  state.pack = params.get("pack") || state.config.default_pack || state.config.packs[0].id;
  sel.value = state.pack;
  sel.onchange = () => { if (!state.live) { state.pack = sel.value; renderIntro(); } else sel.value = state.pack; };
  if (!browserVoiceSupported()) state.mode = state.config.voice.webrtc ? "webrtc" : "text";
  renderIntro();
  document.querySelectorAll("#modes .chip").forEach((b) => (b.onclick = () => { state.mode = b.dataset.mode; renderModes(); }));
  $("#talk").onclick = onTalk;
  $("#typebox").onsubmit = (e) => { e.preventDefault(); onTyped(); };
  $("#phone-btn").onclick = () => $("#phone").classList.toggle("open");
  $("#camera").onclick = () => $("#file").click();
  $("#file").onchange = onFiles;
  $("#convo").addEventListener("click", () => { if (state.live && state.call && state.call.bargeIn) state.call.bargeIn(); });
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space" && state.live && document.activeElement !== $("#typed")) { e.preventDefault(); state.call.bargeIn && state.call.bargeIn(); }
  });
  if (state.config.kill && state.config.kill[state.pack]) $("#kill-banner").hidden = false;
}

function renderIntro() {
  const i = INTRO[state.pack] || { eyebrow: "Voice agent", title: state.pack, sub: "" };
  $("#brand-name").textContent = (state.config.packs.find((p) => p.id === state.pack) || {}).name || "Knowledge Line";
  $("#intro-eyebrow").textContent = i.eyebrow;
  $("#intro-title").textContent = i.title;
  $("#intro-sub").textContent = i.sub;
  const tl = $("#try");
  tl.innerHTML = "";
  for (const t of TRY[state.pack] || []) {
    const li = el("li");
    const q = el("q", "", t);
    li.appendChild(q);
    tl.appendChild(li);
  }
  $("#cheats").hidden = state.pack !== "claims";
  renderWho();
  renderModes();
}

function renderWho() {
  const who = $("#who");
  who.innerHTML = "";
  if (state.pack !== "claims") {
    $("#who-panel").hidden = true;
    return;
  }
  $("#who-panel").hidden = false;
  const anon = el("button", "chip", "Not signed in");
  anon.setAttribute("aria-pressed", String(!state.signin));
  anon.onclick = () => { state.signin = null; state.signinName = null; renderWho(); };
  who.appendChild(anon);
  for (const d of state.config.demo_signin || []) {
    const b = el("button", "chip", `${d.name} (${d.kind})`);
    b.setAttribute("aria-pressed", String(state.signinName === d.name));
    b.onclick = async () => {
      const r = await fetch("/api/demo/signin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ policy: d.policy }) });
      const j = await r.json();
      state.signin = j.token; state.signinName = j.name; renderWho();
    };
    who.appendChild(b);
  }
  $("#who-note").textContent = state.signin
    ? `Signed in as ${state.signinName}: the app's session vouches for you, so the agent does not ask who you are.`
    : "Not signed in: the agent asks for a policy or claim number and your date of birth before it reads anything personal.";
}

function renderModes() {
  const ok = { browser: browserVoiceSupported(), webrtc: state.config.voice.webrtc, text: true };
  if (!ok[state.mode]) state.mode = ok.browser ? "browser" : ok.webrtc ? "webrtc" : "text";
  document.querySelectorAll("#modes .chip").forEach((b) => {
    b.disabled = !ok[b.dataset.mode] || state.live;
    b.setAttribute("aria-pressed", String(b.dataset.mode === state.mode));
  });
  const notes = {
    browser: "Your browser hears and speaks (no keys on the server). In Chrome, recognition runs on Google's servers. Tap the conversation to cut in while the agent is talking.",
    webrtc: "The server hears and speaks over WebRTC, with barge-in: just talk over the agent. " + describeProviders(),
    text: "Type your side of the call. The agent's replies appear as text.",
  };
  let n = notes[state.mode];
  if (!state.config.voice.webrtc) n += " Server voice is off: the server has no hearing or speaking provider set (see docs/providers.md).";
  $("#mode-note").textContent = n;
}

function describeProviders() {
  const p = state.config.providers || {};
  return `Hearing: ${p.stt || "none"}. Speaking: ${p.tts || "none"}. Language model: ${p.llm || "none, rules only"}.`;
}

// ---------------------------------------------------------------- the call
async function onTalk() {
  if (state.live) { hangup(); return; }
  $("#convo").innerHTML = "";
  $("#msgs").innerHTML = '<p class="note" id="no-msgs">Nothing yet.</p>';
  state.messages = 0;
  $("#msg-badge").hidden = true;
  state.lines.clear();
  state.uploadToken = null;
  $("#camera").hidden = true;
  const opts = { pack: state.pack, signin: state.signin, onEvent, onState };
  try {
    if (state.mode === "browser") state.call = new BrowserVoice(opts);
    else if (state.mode === "webrtc") state.call = new RtcCall({ ...opts, iceServers: state.config.ice_servers || [] });
    else state.call = new TextCall({ ...opts, mode: "text" });
    setLive(true);
    status("Connecting...");
    await state.call.start();
    status(state.mode === "text" ? "Type below." : "Connected.");
    if (state.mode === "text") $("#typed").focus();
  } catch (err) {
    setLive(false);
    status("Could not start: " + err.message);
  }
}

function hangup() {
  if (state.call) state.call.hangup();
  setLive(false);
  sys("You hung up.");
}

function setLive(on) {
  state.live = on;
  const t = $("#talk");
  t.classList.toggle("live", on);
  t.setAttribute("aria-label", on ? "Hang up" : "Start the call");
  $("#talk-icon").innerHTML = on
    ? '<path d="M4 15c5-5 11-5 16 0l-2.5 2.5-3-1.5v-2.5a9 9 0 0 0-5 0V16l-3 1.5z" fill="currentColor"/>'
    : '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>';
  $("#intro").hidden = on && $("#convo").children.length > 0;
  $("#pack").disabled = on;
  renderModes();
  if (!on) $("#talk").classList.remove("listening");
}

function onState(s) {
  $("#talk").classList.toggle("listening", s === "listening");
  if (s === "listening") status("<b>Listening.</b> Go ahead.");
  if (s === "blocked") status("The microphone is blocked. Allow it, or choose Type.");
}

function status(html) { $("#status").innerHTML = html; }

function onTyped() {
  const v = $("#typed").value.trim();
  if (!v) return;
  $("#typed").value = "";
  if (!state.live) { status("Start the call first, then type."); return; }
  addCaller(v, true);
  state.call.sendText(v);
}

// ---------------------------------------------------------------- events from the agent
function onEvent(e) {
  switch (e.type) {
    case "call": state.callId = e.id; break;
    case "say": addAgent(e); break;
    case "speaking": markLine(e.id, "speaking"); status("<b>Speaking.</b> Tap the conversation to cut in."); break;
    case "played": markLine(e.id, "played"); break;
    case "interrupted": markCut(e.id, e.chars); break;
    case "partial": showPartial(e.text, e.final); break;
    case "caller": if (state.mode !== "text") addCaller(e.text, e.typed); break;
    case "card": addCard(e); break;
    case "message": addMessage(e); break;
    case "sources": addSources(e); break;
    case "latency": addLatency(e); break;
    case "transfer": addTransfer(e); break;
    case "end": sys("Call ended" + (e.outcome ? ": " + e.outcome : "") + "."); if (state.mode !== "browser") { setLive(false); } else setTimeout(() => setLive(false), 50); break;
    case "kill": $("#kill-banner").hidden = !e.on; break;
    case "closed": if (state.live && state.mode !== "browser") { setLive(false); } break;
    case "error": sys("Error: " + e.detail); break;
    default: break;
  }
}

function scroll() { window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }); }

function addAgent(e) {
  $("#intro").hidden = true;
  clearPartial();
  const d = el("div", "turn agent");
  d.dataset.id = e.id;
  d.dataset.register = e.register || "routine";
  d.appendChild(el("div", "who", "agent"));
  d.appendChild(el("div", "", e.text));
  $("#convo").appendChild(d);
  state.lines.set(e.id, d);
  scroll();
}

function markLine(id, what) {
  document.querySelectorAll(".turn.agent.speaking").forEach((n) => n.classList.remove("speaking"));
  const d = state.lines.get(id);
  if (d && what === "speaking") d.classList.add("speaking");
}

function markCut(id, chars) {
  const d = state.lines.get(id);
  if (!d) return;
  d.classList.remove("speaking");
  d.classList.add("cut");
  d.appendChild(el("div", "cutmark", chars ? `cut in after ${chars} characters` : "not played"));
}

function addCaller(text, typed) {
  $("#intro").hidden = true;
  clearPartial();
  const d = el("div", "turn caller");
  d.appendChild(el("div", "who", typed ? "you (typed)" : "you"));
  d.appendChild(el("div", "", text));
  $("#convo").appendChild(d);
  scroll();
}

function showPartial(text, final) {
  if (final) return clearPartial();
  if (!state.lastPartial) {
    state.lastPartial = el("div", "turn caller partial");
    $("#convo").appendChild(state.lastPartial);
  }
  state.lastPartial.textContent = text;
  scroll();
}
function clearPartial() { if (state.lastPartial) { state.lastPartial.remove(); state.lastPartial = null; } }

function sys(text) { $("#convo").appendChild(el("div", "sys", text)); scroll(); }

function addSources(e) {
  const d = el("div", "sources", "from " + e.sources.join(", ") + (e.how && e.how !== "extractive" ? ` (${e.how})` : ""));
  $("#convo").appendChild(d);
}

function addLatency(e) {
  const d = el("div", "latency");
  const chip = (label, v, cls) => { const s = el("span", cls || "", `${label} ${v} ms`); d.appendChild(s); };
  chip("wait for end of turn", e.endpoint_ms);
  chip("hear", e.stt_ms);
  chip("think", e.agent_ms);
  chip("first audio", e.tts_first_ms);
  chip("voice to voice (server)", e.voice_to_voice_ms, "total");
  $("#convo").appendChild(d);
}

export const showDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", day: "numeric", month: "short" });
};
export const showTime = (hhmm) => {
  if (!hhmm || !hhmm.includes(":")) return hhmm || "";
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}${m ? ":" + String(m).padStart(2, "0") : ""} ${h < 12 ? "am" : "pm"}`;
};
const LOSS = { collision: "Collision", glass: "Glass", theft: "Theft", vandalism: "Vandalism", storm: "Storm", water: "Water", fire: "Fire", animal: "Animal", other: "Other" };
const STATUS = { reported: "open, waiting for photos", photos_received: "photos received", inspection_scheduled: "inspection booked", estimate_ready: "estimate ready", payment_issued: "payment issued", closed: "closed" };

function addCard(e) {
  const c = el("div", "card");
  if (e.kind === "claim") {
    const k = e.claim;
    const h = el("h3");
    h.append(el("span", "", "Claim"), el("span", "mono", k.number), el("span", "status-pill", STATUS[k.status] || k.status));
    c.appendChild(h);
    const dl = el("dl");
    const row = (a, b) => { dl.append(el("dt", "", a), el("dd", "", b)); };
    row("What", LOSS[k.loss_type] || k.loss_type);
    row("When", showDate(k.loss_date) + (k.loss_time ? ", " + showTime(k.loss_time) : ""));
    if (k.location) row("Where", k.location);
    if (k.adjuster) row("Adjuster", k.adjuster);
    if (k.next && k.next.date) row("Next", `${k.next.what || "next step"} by ${showDate(k.next.date)}`);
    row("Photos", String(k.photos));
    c.appendChild(dl);
  } else if (e.kind === "upload") {
    state.uploadToken = e.url.split("/").pop();
    state.uploadClaim = e.claim;
    $("#camera").hidden = false;
    c.classList.add("signal");
    const h = el("h3");
    h.append(el("span", "", "Add photos to"), el("span", "mono", e.claim));
    c.appendChild(h);
    c.appendChild(el("div", "", "Take the whole damaged area, then close-ups. The agent hears about them as soon as they arrive."));
    const a = el("div", "actions");
    const b = el("button", "btn signal", "Take or choose photos");
    b.onclick = () => $("#file").click();
    a.appendChild(b);
    c.appendChild(a);
    c.appendChild(el("div", "thumbs"));
    c.id = "upload-card";
  } else if (e.kind === "photos") {
    c.appendChild(el("h3", "", `${e.count} photo${e.count === 1 ? "" : "s"} received for ${e.claim}`));
  } else if (e.kind === "booking") {
    const h = el("h3");
    h.append(el("span", "", "Visit booked"), el("span", "status-pill", e.booking.when));
    c.appendChild(h);
    const dl = el("dl");
    dl.append(el("dt", "", "Address"), el("dd", "", e.booking.address), el("dt", "", "Call-out"), el("dd", "", `$${e.booking.fee}, off the bill if the job goes ahead`));
    c.appendChild(dl);
  } else return;
  $("#convo").appendChild(c);
  scroll();
}

function addTransfer(e) {
  const c = el("div", "card signal");
  c.appendChild(el("h3", "", `Handing over to ${e.to}`));
  c.appendChild(el("div", "", "What they see before they say hello:"));
  c.appendChild(el("div", "mono", e.summary && e.summary.whisper ? e.summary.whisper : ""));
  if (!e.number) c.appendChild(el("p", "note", "In this demonstration no one is on the other end; on a phone line the call is connected."));
  $("#convo").appendChild(c);
  scroll();
}

function linkify(text) {
  const frag = document.createDocumentFragment();
  const parts = text.split(/(https?:\/\/\S+)/g);
  for (const p of parts) {
    if (/^https?:\/\//.test(p)) {
      const a = el("a", "", p.replace(/^https?:\/\/[^/]+/, ""));
      a.href = p.replace(/^https?:\/\/[^/]+/, location.origin);
      a.target = "_blank";
      a.rel = "noopener";
      frag.appendChild(a);
    } else frag.appendChild(document.createTextNode(p));
  }
  return frag;
}

function addMessage(m) {
  const box = $("#msgs");
  const none = $("#no-msgs");
  if (none) none.remove();
  const d = el("div", "sms");
  const to = m.channel === "sms" ? `text to the mobile ending ${m.to}` : `email to ${m.to}`;
  d.appendChild(el("div", "meta", `${to} · ${m.status}`));
  const body = el("div");
  body.appendChild(linkify(m.body));
  d.appendChild(body);
  box.prepend(d);
  state.messages += 1;
  const badge = $("#msg-badge");
  badge.textContent = String(state.messages);
  badge.hidden = false;
  sys(m.channel === "sms" ? "A text was sent. Open the phone panel to see it." : "An email was sent. Open the phone panel to see it.");
}

// ---------------------------------------------------------------- photos from the camera
async function onFiles() {
  const files = [...$("#file").files];
  $("#file").value = "";
  if (!files.length || !state.uploadToken) return;
  const card = $("#upload-card");
  const thumbs = card ? card.querySelector(".thumbs") : null;
  for (const f of files) {
    if (thumbs) {
      const img = el("img");
      img.src = URL.createObjectURL(f);
      img.alt = "photo to upload";
      thumbs.appendChild(img);
    }
  }
  status("Uploading photos...");
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f, f.name));
  const r = await fetch(`/api/links/${state.uploadToken}/photos`, { method: "POST", body: fd });
  if (!r.ok) { const j = await r.json().catch(() => ({})); status("Upload failed: " + (j.detail || r.status)); return; }
  const j = await r.json();
  status(`Uploaded. The claim has ${j.total} photo${j.total === 1 ? "" : "s"}.`);
}

init();
