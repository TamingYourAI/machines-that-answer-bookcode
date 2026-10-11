// Three ways to reach the same agent. Each call object takes an onEvent callback and gets
// the agent's events: say, card, message, latency, transfer, end.
//
//   TextCall      a WebSocket; the caller types, the agent's lines appear as text
//   BrowserVoice  the same WebSocket, with the browser's own recognition and voice. It tells
//                 the agent which lines were heard, and how much of a line was played
//                 before the caller cut in (so a yes covers only what was heard)
//   RtcCall       WebRTC to the server: the server hears and speaks, events on a data channel

const wsURL = (path) => (location.protocol === "https:" ? "wss://" : "ws://") + location.host + path;

export class TextCall {
  constructor({ pack, signin, mode = "text", onEvent }) {
    Object.assign(this, { pack, signin, mode, onEvent });
    this.ws = null;
  }
  start() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(wsURL("/ws/talk"));
      this.ws.onopen = () => {
        this.send({ type: "start", pack: this.pack, mode: this.mode, signin: this.signin });
        resolve();
      };
      this.ws.onerror = () => reject(new Error("could not reach the server"));
      this.ws.onmessage = (m) => this.onEvent(JSON.parse(m.data));
      this.ws.onclose = () => this.onEvent({ type: "closed" });
    });
  }
  send(obj) { if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(obj)); }
  sendText(text) { this.send({ type: "caller", text, mode: this.mode }); }
  heard(id) { this.send({ type: "heard", id }); }
  interrupted(id, chars) { this.send({ type: "interrupted", id, chars }); }
  silence() { this.send({ type: "silence" }); }
  hangup() { this.send({ type: "hangup" }); try { this.ws.close(); } catch (e) {} }
}

export function browserVoiceSupported() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition) && "speechSynthesis" in window;
}

export class BrowserVoice {
  constructor({ pack, signin, onEvent, onState }) {
    this.onEvent = onEvent;
    this.onState = onState || (() => {});
    this.call = new TextCall({ pack, signin, mode: "browser", onEvent: (e) => this.handle(e) });
    this.queue = [];
    this.current = null;
    this.lastChar = 0;
    this.listening = false;
    this.ended = false;
    this.voice = null;
    const R = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.rec = new R();
    this.rec.lang = "en-US";
    this.rec.interimResults = true;
    this.rec.continuous = false;
    this.rec.maxAlternatives = 1;
    this.gotResult = false;
    this.rec.onresult = (ev) => {
      let text = "", final = false;
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        text += ev.results[i][0].transcript;
        if (ev.results[i].isFinal) final = true;
      }
      this.onEvent({ type: "partial", text, final });
      if (final && text.trim()) {
        this.gotResult = true;
        this.onEvent({ type: "caller", text: text.trim(), final: true });
        this.call.sendText(text.trim());
      }
    };
    this.rec.onerror = (e) => {
      if (e.error === "no-speech") { this.silent = true; }
      else if (e.error === "not-allowed") { this.onState("blocked"); this.ended = true; }
    };
    this.rec.onend = () => {
      this.listening = false;
      if (this.ended) return;
      if (!this.gotResult && this.silent) { this.silent = false; this.call.silence(); }
      else if (!this.gotResult && !this.current && this.queue.length === 0) this.listen();
      this.onState("idle");
    };
    const pick = () => {
      const vs = speechSynthesis.getVoices().filter((v) => v.lang && v.lang.startsWith("en"));
      this.voice = vs.find((v) => /natural|neural|google us|samantha|aria|jenny/i.test(v.name)) || vs[0] || null;
    };
    pick();
    speechSynthesis.onvoiceschanged = pick;
  }
  async start() { await this.call.start(); }
  handle(e) {
    if (e.type === "say") { this.queue.push(e); this.onEvent(e); this.pump(); return; }
    if (e.type === "end") { this.onEvent(e); this.finishAfterSpeech(); return; }
    this.onEvent(e);
  }
  pump() {
    if (this.current || this.queue.length === 0) return;
    this.stopListening();
    const e = this.queue.shift();
    this.current = e;
    this.lastChar = 0;
    const u = new SpeechSynthesisUtterance(e.speech);
    if (this.voice) u.voice = this.voice;
    u.rate = 1.0;
    u.onboundary = (b) => { this.lastChar = b.charIndex + (b.charLength || 0); };
    u.onstart = () => this.onEvent({ type: "speaking", id: e.id });
    u.onend = () => {
      if (this.current !== e) return;
      this.call.heard(e.id);
      this.onEvent({ type: "played", id: e.id });
      this.current = null;
      if (this.queue.length) this.pump();
      else if (!this.ended) this.listen();
    };
    speechSynthesis.speak(u);
  }
  // The caller cuts in: stop the voice now, and say how much of the line was played.
  bargeIn() {
    if (this.current) {
      const e = this.current;
      this.current = null;
      speechSynthesis.cancel();
      this.call.interrupted(e.id, this.lastChar);
      this.onEvent({ type: "interrupted", id: e.id, chars: this.lastChar });
      for (const q of this.queue) {
        this.call.interrupted(q.id, 0);
        this.onEvent({ type: "interrupted", id: q.id, chars: 0 });
      }
      this.queue = [];
    }
    this.listen();
  }
  listen() {
    if (this.listening || this.ended) return;
    this.gotResult = false;
    this.silent = false;
    try { this.rec.start(); this.listening = true; this.onState("listening"); } catch (err) {}
  }
  stopListening() {
    if (this.listening) { try { this.rec.abort(); } catch (err) {} this.listening = false; }
  }
  sendText(text) { this.bargeIn(); this.stopListening(); this.call.sendText(text); }
  finishAfterSpeech() {
    this.ended = true;
    const wait = () => (this.current || this.queue.length ? setTimeout(wait, 200) : this.hangup(false));
    wait();
  }
  hangup(send = true) {
    this.ended = true;
    this.stopListening();
    speechSynthesis.cancel();
    if (send) this.call.hangup();
    this.onState("ended");
  }
}

export class RtcCall {
  constructor({ pack, signin, onEvent, onState, iceServers = [] }) {
    Object.assign(this, { pack, signin, onEvent, iceServers });
    this.onState = onState || (() => {});
    this.audio = document.createElement("audio");
    this.audio.autoplay = true;
    this.audio.setAttribute("playsinline", "");
    document.body.appendChild(this.audio);
  }
  async start() {
    this.mic = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    this.pc = new RTCPeerConnection({ iceServers: this.iceServers });
    this.mic.getTracks().forEach((t) => this.pc.addTrack(t, this.mic));
    this.dc = this.pc.createDataChannel("events");
    this.dc.onmessage = (m) => this.onEvent(JSON.parse(m.data));
    this.pc.ontrack = (ev) => {
      this.audio.srcObject = ev.streams[0] || new MediaStream([ev.track]);
      this.audio.play().catch(() => {});
    };
    this.pc.onconnectionstatechange = () => {
      const s = this.pc.connectionState;
      if (s === "connected") this.onState("listening");
      if (s === "failed" || s === "closed") this.onEvent({ type: "closed" });
    };
    await this.pc.setLocalDescription(await this.pc.createOffer());
    await new Promise((resolve) => {
      if (this.pc.iceGatheringState === "complete") return resolve();
      const t = setTimeout(resolve, 2500);
      this.pc.addEventListener("icegatheringstatechange", () => {
        if (this.pc.iceGatheringState === "complete") { clearTimeout(t); resolve(); }
      });
    });
    const r = await fetch("/api/rtc/offer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sdp: this.pc.localDescription.sdp, type: this.pc.localDescription.type,
                             pack: this.pack, signin: this.signin }) });
    if (!r.ok) throw new Error((await r.json()).detail || "the server could not answer");
    const ans = await r.json();
    this.onEvent({ type: "call", id: ans.call, pack: this.pack, mode: "webrtc" });
    await this.pc.setRemoteDescription({ sdp: ans.sdp, type: ans.type });
  }
  send(obj) { if (this.dc && this.dc.readyState === "open") this.dc.send(JSON.stringify(obj)); }
  sendText(text) { this.send({ type: "text", text }); }
  bargeIn() { /* the server hears the caller and cuts in by itself */ }
  hangup() {
    this.send({ type: "hangup" });
    setTimeout(() => {
      try { this.pc.close(); } catch (e) {}
      this.mic && this.mic.getTracks().forEach((t) => t.stop());
      this.audio.remove();
    }, 150);
    this.onState("ended");
  }
}
