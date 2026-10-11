"""The audio session: one call's hearing, turn-taking, speaking, and barge-in.

A transport (WebRTC, a phone media stream, raw PCM over a WebSocket) feeds caller audio in and
pulls agent audio out. Between them:

  caller audio -> TurnDetector -> (end of turn) -> STT -> Agent.hear -> lines
  lines -> TTS -> Playout -> transport pulls frames in real time

The Playout knows which line every byte belongs to, so when the caller talks over the agent
the session can cancel at the transport (clear the buffer, stop synthesis) and tell the agent
how much of the line was played. The agent then knows which terms were heard (the event
timeline: generated, queued, played, heard). Latency is measured per turn from the end of the
caller's speech, as the server sees it, to the first reply audio handed to the transport.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .agent import Agent
from .audio import FRAME_MS, RATE, frames, resample
from .turn import TurnConfig, TurnDetector

SILENCE_S = (5.0, 5.0, 5.0)        # checks at 5, 10, and 15 seconds of silence (canon)

EventSink = Callable[[dict], Awaitable[None]]


@dataclass
class _Piece:
    line_id: str | None
    pcm: bytes
    pos: int = 0


class Playout:
    """Agent audio waiting to be played, tagged by line, read by the transport in frames."""

    def __init__(self, rate: int):
        self.rate = rate
        self.q: deque[_Piece] = deque()
        self.played: dict[str, int] = {}          # bytes of each line already handed out
        self.total: dict[str, int] = {}
        self.closed: set[str] = set()             # lines whose synthesis finished
        self.first_out: dict[str, float] = {}
        self.on_line_done: Callable[[str], None] | None = None

    def frame_bytes(self, ms: int = FRAME_MS) -> int:
        return self.rate * 2 * ms // 1000

    def push(self, line_id: str, pcm: bytes) -> None:
        if pcm:
            self.q.append(_Piece(line_id, pcm))
            self.total[line_id] = self.total.get(line_id, 0) + len(pcm)

    def close_line(self, line_id: str) -> None:
        self.closed.add(line_id)
        self._check_done(line_id)

    def busy(self) -> bool:
        return bool(self.q)

    def read(self, n: int) -> bytes:
        """n bytes of audio: agent speech if any is queued, silence otherwise."""
        out = bytearray()
        while len(out) < n and self.q:
            p = self.q[0]
            take = min(n - len(out), len(p.pcm) - p.pos)
            out += p.pcm[p.pos:p.pos + take]
            p.pos += take
            if p.line_id:
                self.played[p.line_id] = self.played.get(p.line_id, 0) + take
                self.first_out.setdefault(p.line_id, time.perf_counter())
            if p.pos >= len(p.pcm):
                self.q.popleft()
                if p.line_id:
                    self._check_done(p.line_id)
        if len(out) < n:
            out += bytes(n - len(out))
        return bytes(out)

    def _check_done(self, line_id: str) -> None:
        if line_id in self.closed and self.played.get(line_id, 0) >= self.total.get(line_id, 0) \
                and not any(p.line_id == line_id for p in self.q):
            if self.on_line_done:
                self.on_line_done(line_id)

    def clear(self) -> list[str]:
        """Drop everything not yet played; return the lines that were cut."""
        cut = []
        for p in self.q:
            if p.line_id and p.line_id not in cut:
                cut.append(p.line_id)
        self.q.clear()
        return cut


@dataclass
class TurnTiming:
    turn: int
    endpoint_ms: float
    stt_ms: float = 0.0
    agent_ms: float = 0.0
    tts_first_ms: float = 0.0
    to_first_audio_ms: float = 0.0
    meta: dict = field(default_factory=dict)


class VoiceSession:
    def __init__(self, agent: Agent, stt, tts, out_rate: int, send_event: EventSink,
                 on_clear: Callable[[], Awaitable[None]] | None = None,
                 on_end: Callable[[dict], Awaitable[None]] | None = None,
                 turn_cfg: TurnConfig | None = None, silence_s=SILENCE_S):
        self.agent, self.stt, self.tts = agent, stt, tts
        self.out_rate = out_rate
        self.send_event, self.on_clear, self.on_end = send_event, on_clear, on_end
        self.detector = TurnDetector(turn_cfg)
        self.playout = Playout(out_rate)
        self.playout.on_line_done = self._line_heard
        self.queue: asyncio.Queue = asyncio.Queue()
        self.speaking_line: str | None = None
        self.synth_task: asyncio.Task | None = None
        self.tasks: list[asyncio.Task] = []
        self.pending_in = b""
        self.last_activity = time.monotonic()
        self.silence_s = silence_s
        self.silence_n = 0
        self.timings: list[TurnTiming] = []
        self._turn_t0: float | None = None
        self._timing: TurnTiming | None = None
        self.closed = False
        self.ending = False
        self.require_playback_ack = False
        self.playback_pending: Callable[[], bool] = lambda: False
        agent.heard_of = self.heard_chars

    # ------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self.tasks.append(asyncio.create_task(self._speaker()))
        self.tasks.append(asyncio.create_task(self._silence_watch()))
        await self._dispatch(await self.agent.begin())

    async def close(self, outcome: str = "caller hung up") -> None:
        if self.closed:
            return
        self.closed = True
        for t in self.tasks + ([self.synth_task] if self.synth_task else []):
            t.cancel()
        await self.agent.end(outcome)

    # ------------------------------------------------------------ caller audio in
    async def feed(self, pcm: bytes, rate: int = RATE) -> None:
        """Caller audio at any rate; processed in 20 ms frames of 16 kHz."""
        if self.closed:
            return
        if rate != RATE:
            pcm = resample(pcm, rate, RATE)
        self.pending_in += pcm
        size = RATE * 2 * FRAME_MS // 1000
        while len(self.pending_in) >= size:
            frame, self.pending_in = self.pending_in[:size], self.pending_in[size:]
            self.detector.agent_speaking = self.is_speaking()
            for ev in self.detector.feed(frame):
                if ev.kind == "start":
                    self.last_activity = time.monotonic()
                    self.silence_n = 0
                elif ev.kind == "barge_in":
                    await self.interrupt()
                elif ev.kind == "end":
                    self.last_activity = time.monotonic()
                    self.tasks.append(asyncio.create_task(self._turn(ev.audio, ev.meta)))

    def is_speaking(self) -> bool:
        return self.playout.busy() or self.speaking_line is not None or \
            not self.queue.empty() or self.playback_pending()

    async def _turn(self, audio: bytes, meta: dict) -> None:
        t_end = time.perf_counter()
        timing = TurnTiming(self.agent.state.turn + 1,
                            endpoint_ms=meta.get("silence_ms", 0.0))
        t0 = time.perf_counter()
        tr = await self.stt.transcribe(audio, RATE)
        timing.stt_ms = (time.perf_counter() - t0) * 1000
        text = (tr.text or "").strip()
        if not text:
            return
        await self.send_event({"type": "caller", "text": text, "final": True,
                               "confidence": tr.confidence})
        t1 = time.perf_counter()
        events = await self.agent.hear(text, {"stt": self.stt.name,
                                              "confidence": tr.confidence})
        timing.agent_ms = (time.perf_counter() - t1) * 1000
        self._turn_t0, self._timing = t_end, timing
        await self._dispatch(events)

    # ------------------------------------------------------------ agent audio out
    async def _dispatch(self, events: list[dict]) -> None:
        for e in events:
            await self.queue.put(e)

    async def _speaker(self) -> None:
        while True:
            e = await self.queue.get()
            if e["type"] != "say":
                while self.playout.busy() or self.speaking_line:
                    await asyncio.sleep(0.02)       # after the lines before it are played
                await self.send_event(e)
                if e["type"] in ("end", "transfer") and not self.ending:
                    self.ending = True
                    if self.on_end:
                        await self.on_end(e)
                continue
            await self.send_event(e)
            self.speaking_line = e["id"]
            self.synth_task = asyncio.create_task(self._synthesize(e))
            try:
                await self.synth_task
            except asyncio.CancelledError:
                if self.closed:
                    return
            finally:
                self.synth_task = None

    async def _synthesize(self, e: dict) -> None:
        lid = e["id"]
        t0 = time.perf_counter()
        first = True
        try:
            async for chunk in self.tts.stream(e["speech"]):
                if first:
                    first = False
                    if self._timing is not None:
                        self._timing.tts_first_ms = (time.perf_counter() - t0) * 1000
                if self.tts.rate != self.out_rate:
                    chunk = resample(chunk, self.tts.rate, self.out_rate)
                self.playout.push(lid, chunk)
                # keep synthesis at most about a second ahead of playout
                while len(self.playout.q) > 12:
                    await asyncio.sleep(0.02)
            self.playout.close_line(lid)
            while self.playout.busy():
                await asyncio.sleep(0.01)
                self._note_first_audio(lid)
            self._note_first_audio(lid)
        finally:
            if self.speaking_line == lid:
                self.speaking_line = None
                self.last_activity = time.monotonic()

    def _note_first_audio(self, lid: str) -> None:
        if self._timing and self._turn_t0 and lid in self.playout.first_out:
            t = self._timing
            t.to_first_audio_ms = (self.playout.first_out[lid] - self._turn_t0) * 1000
            self.timings.append(t)
            self._timing, self._turn_t0 = None, None
            wall = t.endpoint_ms + t.to_first_audio_ms
            asyncio.create_task(self.send_event({
                "type": "latency", "turn": t.turn, "endpoint_ms": round(t.endpoint_ms),
                "stt_ms": round(t.stt_ms), "agent_ms": round(t.agent_ms),
                "tts_first_ms": round(t.tts_first_ms),
                "server_ms": round(t.to_first_audio_ms), "voice_to_voice_ms": round(wall)}))
            self.agent.rt.store.add_span(self.agent.call_id, t.turn, "latency", "turn", 0,
                                         wall, {"endpoint_ms": t.endpoint_ms,
                                                "stt_ms": t.stt_ms, "agent_ms": t.agent_ms,
                                                "tts_first_ms": t.tts_first_ms})

    def read_out(self, ms: int = FRAME_MS) -> bytes:
        """The transport pulls agent audio here, in real time."""
        return self.playout.read(self.playout.frame_bytes(ms))

    def _line_heard(self, line_id: str) -> None:
        self.agent.mark(line_id, "heard")
        asyncio.ensure_future(self.send_event({"type": "played", "id": line_id}))

    def heard_chars(self, line_id: str) -> int | None:
        """How much of a line's spoken form has been played: None when all of it."""
        rec = self.agent.lines.get(line_id)
        if self.require_playback_ack:
            return None if rec and rec.status == "heard" else 0
        total = self.playout.total.get(line_id)
        if rec is None or not total:
            return 0
        played = self.playout.played.get(line_id, 0)
        if line_id in self.playout.closed and played >= total:
            return None
        return int(len(rec.line.speech) * played / total)

    async def interrupt(self) -> None:
        """Barge-in: cancel at the transport, then say what was heard."""
        if not self.is_speaking():
            return
        cut = self.playout.clear()
        current = self.speaking_line
        if self.synth_task:
            self.synth_task.cancel()
        dropped, keep = [], []
        while not self.queue.empty():
            e = self.queue.get_nowait()
            if e["type"] == "say":
                dropped.append(e["id"])
            elif e["type"] in ("end", "transfer"):
                keep.append(e)                    # a transfer still happens
            else:
                await self.send_event(e)          # cards and state go straight out
        for e in keep:
            await self.queue.put(e)
        seen: set[str] = set()
        for lid in ([current] if current else []) + cut + dropped:
            if lid is None or lid in seen:
                continue
            seen.add(lid)
            rec = self.agent.lines.get(lid)
            total = self.playout.total.get(lid, 0)
            played = self.playout.played.get(lid, 0)
            chars = int(len(rec.line.speech) * played / total) \
                if rec and total and not self.require_playback_ack else 0
            self.agent.mark(lid, "interrupted", chars)
            await self.send_event({"type": "interrupted", "id": lid, "chars": chars})
        self.speaking_line = None
        if self.on_clear:
            await self.on_clear()

    # ------------------------------------------------------------ silence
    async def _silence_watch(self) -> None:
        while True:
            await asyncio.sleep(0.25)
            if self.is_speaking() or self.detector.in_speech or self.agent.state.ended:
                continue
            idx = min(self.silence_n, len(self.silence_s) - 1)
            if time.monotonic() - self.last_activity >= self.silence_s[idx]:
                self.silence_n += 1
                self.last_activity = time.monotonic()
                await self._dispatch(await self.agent.silence())
