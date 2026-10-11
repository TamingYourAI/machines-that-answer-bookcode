"""The phone, through Twilio, two ways.

ConversationRelay: Twilio hears and speaks (its own recognition and voice); our server gets
the caller's words as text over a WebSocket and answers with text. Only a Twilio account is
needed. Interruptions arrive as "interrupt" messages with the part of our reply that was
played, which is what the agent needs to know which terms were heard.

Media Streams: Twilio sends the call's audio (8 kHz mu-law) over a WebSocket and plays what
we send back; our hearing and speaking providers do the rest, through the same VoiceSession
as WebRTC. Barge-in sends "clear" so Twilio drops what it buffered.

Message shapes are written to Twilio's docs (checked 2026-09-27; the docs pages were reached
through search, see docs/providers.md) and tested against simulated Twilio messages.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Awaitable, Callable
from xml.sax.saxutils import escape, quoteattr

from ..agent import Agent
from ..audio import pcm_to_ulaw, ulaw_to_pcm
from ..voice import VoiceSession


# ---------------------------------------------------------------- TwiML and signatures

def twiml_relay(ws_url: str, welcome: str, action_url: str, params: dict) -> str:
    p = "".join(f"<Parameter name={quoteattr(k)} value={quoteattr(v)}/>"
                for k, v in params.items())
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>'
            f"<Connect action={quoteattr(action_url)}>"
            f"<ConversationRelay url={quoteattr(ws_url)} welcomeGreeting={quoteattr(welcome)} "
            f'interruptible="true" dtmfDetection="true">{p}</ConversationRelay>'
            "</Connect></Response>")


def twiml_stream(ws_url: str, params: dict) -> str:
    p = "".join(f"<Parameter name={quoteattr(k)} value={quoteattr(v)}/>"
                for k, v in params.items())
    return ('<?xml version="1.0" encoding="UTF-8"?><Response><Connect>'
            f"<Stream url={quoteattr(ws_url)}>{p}</Stream></Connect></Response>")


def twiml_dial(number: str, whisper: str = "") -> str:
    say = f"<Say>{escape(whisper)}</Say>" if whisper else ""
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>'
            f"<Dial>{escape(number)}</Dial>{say}</Response>")


def twiml_say_hangup(text: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><Response>'
            f"<Say>{escape(text)}</Say><Hangup/></Response>")


def signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """X-Twilio-Signature: HMAC-SHA1 over the full URL followed by each POST parameter's
    name and value, sorted by name, base64-encoded."""
    data = url + "".join(k + params[k] for k in sorted(params))
    return base64.b64encode(hmac.new(auth_token.encode(), data.encode(),
                                     hashlib.sha1).digest()).decode()


def valid_signature(auth_token: str, url: str, params: dict[str, str], got: str) -> bool:
    return bool(got) and hmac.compare_digest(signature(auth_token, url, params), got)


# ---------------------------------------------------------------- ConversationRelay

Send = Callable[[dict], Awaitable[None]]


class RelayCall:
    """One call over ConversationRelay. Feed it Twilio's messages; it sends replies."""

    def __init__(self, make_agent: Callable[[dict], Agent], send: Send,
                 on_event: Callable[[dict], Awaitable[None]] | None = None):
        self.make_agent, self.send, self.on_event = make_agent, send, on_event
        self.agent: Agent | None = None
        self.last_reply: list[tuple[str, int, int]] = []   # (line id, start, end) in reply

    async def handle(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "setup":
            self.agent = self.make_agent(msg)
            events = await self.agent.begin()
            # the welcome greeting was spoken by Twilio from the TwiML; mark it and say the rest
            says = [e for e in events if e["type"] == "say"]
            if says:
                self.agent.mark(says[0]["id"], "heard")
            await self._emit([e for e in events if not (says and e is says[0])])
        elif self.agent is None:
            return
        elif kind == "prompt" and msg.get("last", True):
            await self._emit(await self.agent.hear(msg.get("voicePrompt", ""),
                                                   {"lang": msg.get("lang")}))
        elif kind == "interrupt":
            self._interrupted(msg.get("utteranceUntilInterrupt", ""))
        elif kind == "dtmf":
            await self._emit(await self.agent.dtmf(msg.get("digit", "")))
        elif kind == "error":
            if self.on_event:
                await self.on_event({"type": "error", "detail": msg.get("description")})

    def _interrupted(self, heard: str) -> None:
        n = len(heard)
        for lid, a, b in self.last_reply:
            if n >= b:
                continue
            self.agent.mark(lid, "interrupted", max(0, n - a))

    async def _emit(self, events: list[dict]) -> None:
        speech, self.last_reply = "", []
        for e in events:
            if e["type"] == "say":
                start = len(speech) + (1 if speech else 0)
                speech = (speech + " " + e["speech"]).strip()
                self.last_reply.append((e["id"], start, len(speech)))
        if speech:
            await self.send({"type": "text", "token": speech, "last": True})
        for e in events:
            if self.on_event and e["type"] != "say":
                await self.on_event(e)
            if e["type"] == "transfer":
                await self.send({"type": "end", "handoffData": json.dumps({
                    "reason": "transfer", "number": e.get("number", ""),
                    "whisper": e.get("summary", {}).get("whisper", "")})})
            elif e["type"] == "end":
                await self.send({"type": "end", "handoffData": json.dumps(
                    {"reason": e.get("reason", "end")})})


# ---------------------------------------------------------------- Media Streams

class MediaStreamCall:
    """One call over Media Streams: mu-law 8 kHz both ways, through a VoiceSession."""

    def __init__(self, make_session: Callable[[dict, Send], VoiceSession], send: Send,
                 transfer: Callable[[str, dict], Awaitable[None]] | None = None):
        self.make_session, self.send, self.transfer = make_session, send, transfer
        self.session: VoiceSession | None = None
        self.stream_sid = ""
        self.call_sid = ""
        self.pump = None
        self.marks = 0
        self.drained_lines: list[str] = []
        self.pending_marks: dict[str, str] = {}

    async def handle(self, msg: dict) -> None:
        import asyncio
        ev = msg.get("event")
        if ev == "start":
            st = msg.get("start", {})
            self.stream_sid = msg.get("streamSid") or st.get("streamSid", "")
            self.call_sid = st.get("callSid", "")
            self.session = self.make_session(st, self._event)
            self.session.require_playback_ack = True
            self.session.playback_pending = lambda: bool(self.pending_marks or self.drained_lines)
            self.session.playout.on_line_done = self.drained_lines.append
            self.session.on_clear = self._clear
            self.session.on_end = self._end
            await self.session.start()
            self.pump = asyncio.ensure_future(self._pump())
        elif ev == "media" and self.session:
            payload = base64.b64decode(msg["media"]["payload"])
            await self.session.feed(ulaw_to_pcm(payload), 8000)
        elif ev == "dtmf" and self.session:
            digit = msg.get("dtmf", {}).get("digit", "")
            await self.session._dispatch(await self.session.agent.dtmf(digit))
        elif ev == "mark" and self.session:
            lid = self.pending_marks.pop(msg.get("mark", {}).get("name", ""), None)
            if lid:
                self.session.agent.mark(lid, "heard")
        elif ev == "stop" and self.session:
            await self.close()

    async def _pump(self) -> None:
        """Send audio first, then its mark. Only a returned, uncleared mark is evidence."""
        import asyncio
        import time
        t0, n = time.monotonic(), 0
        while self.session and not self.session.closed:
            n += 1
            if self.session.playout.busy():
                pcm = self.session.read_out(20)
                await self.send({"event": "media", "streamSid": self.stream_sid,
                                 "media": {"payload": base64.b64encode(
                                     pcm_to_ulaw(pcm)).decode()}})
            while self.drained_lines:
                lid = self.drained_lines.pop(0)
                if self.session.agent.lines[lid].status == "interrupted":
                    continue
                self.marks += 1
                name = f"{lid}:{self.marks}"
                self.pending_marks[name] = lid
                await self.send({"event": "mark", "streamSid": self.stream_sid,
                                 "mark": {"name": name}})
            wait = t0 + n * 0.02 - time.monotonic()
            await asyncio.sleep(max(0.0, wait))

    async def _clear(self) -> None:
        # Twilio returns waiting marks on clear too. Invalidate before the send,
        # so a racing returned mark cannot turn canceled speech into agreement.
        for lid in set(self.pending_marks.values()) | set(self.drained_lines):
            self.session.agent.mark(lid, "interrupted", 0)
        self.pending_marks.clear()
        self.drained_lines.clear()
        await self.send({"event": "clear", "streamSid": self.stream_sid})

    async def _event(self, e: dict) -> None:
        # A generated line has no playback evidence. Marks are sent by _pump.
        pass

    async def _end(self, e: dict) -> None:
        if e["type"] == "transfer" and self.transfer:
            await self.transfer(self.call_sid, e)

    async def close(self) -> None:
        if self.pump:
            self.pump.cancel()
        if self.session:
            await self.session.close()


async def redirect_call(account_sid: str, auth_token: str, call_sid: str, twiml: str,
                        client=None) -> bool:
    """Replace a live call's instructions (for a transfer from Media Streams)."""
    import httpx
    c = client or httpx.AsyncClient(timeout=10)
    try:
        r = await c.post(f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/"
                         f"{call_sid}.json", data={"Twiml": twiml},
                         auth=(account_sid, auth_token))
        return r.status_code < 300
    finally:
        if client is None:
            await c.aclose()
