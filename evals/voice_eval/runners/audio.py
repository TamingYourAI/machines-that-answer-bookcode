"""The audio runner: the caller speaks, in real time, in 20 ms packets of 16 kHz audio, and the
agent's audio is timed packet by packet. Evidence class: live laboratory, with a synthetic caller.

The protocol (the companion app's ``/ws/audio``; any system can expose the same):

    binary frames, both ways: 16 kHz, 16-bit, mono PCM
    agent -> {"type": "call", "id": "<call id>"}
    agent -> {"type": "say", "id": "<line id>", "text": "..."}    (the line it is about to speak)
    agent -> {"type": "end" | "transfer", ...}                    (the call is over)
    caller -> {"type": "hangup"}

The caller's voice is the companion's local Kokoro, in a voice unlike the agent's. The line's
conditions (noise, the phone codec, lost packets) are applied to it before it is sent. Between
turns the line carries silence, or the noise, without a break, as a phone line does.

What it measures, all at the caller's end of this connection:

- **gaps_ms**: from the end of each caller turn to the agent's first audible packet;
- **cut_offs**: pauses the caller left inside a turn in which the agent began to speak;
- **talk_over**: times the agent began to speak while the caller was speaking.

The measurements include this connection, not a phone network. On one machine that is close to
nothing; across a network it is not, and the report says where the runner ran.
"""
from __future__ import annotations

import asyncio
import functools
import json
import os
import time
from collections import deque
from pathlib import Path

import numpy as np
import websockets

from .. import conditions
from ..scenarios import Caller, Scenario
from ..stats import percentile
from . import RunResult
from .text import ws_url

FRAME_MS = 20
FRAME_BYTES = 640                       # 20 ms at 16 kHz, 16-bit
SPEECH_RMS = 250.0                      # an agent packet louder than this is speech
IDLE = 1.6                              # quiet that ends a turn, without played reports
CALLER_VOICE = os.environ.get("VOICE_EVAL_CALLER_VOICE", "am_michael")
MODELS = Path(os.environ.get("VOICE_EVAL_MODELS",
                             Path(__file__).resolve().parents[3] / "models"))

_tts = None


def voice():
    """The caller's voice: the companion's local Kokoro adapter, loaded once."""
    global _tts
    if _tts is None:
        from ova.providers.tts import KokoroTTS
        _tts = KokoroTTS(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"),
                         CALLER_VOICE)
    return _tts


@functools.lru_cache(maxsize=512)
def speak(words: str) -> bytes:
    from ova.audio import resample
    t = voice()
    return resample(t._synth(words), t.rate, 16000)


def _rms(frame: bytes) -> float:
    a = np.frombuffer(frame, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(a ** 2))) if len(a) else 0.0


class Line:
    """Both directions of one call, with the time of every packet."""

    def __init__(self, cond: dict, seed: int):
        self.cond = cond
        self.rng = np.random.default_rng(seed)
        self.queue: deque = deque()                     # ("speech" | "pause", frame) or marks
        self.marks: list[tuple[str, float]] = []        # ("speech_start" | "speech_end" | ...)
        self.agent: list[tuple[float, float]] = []      # (time, rms) of each agent packet
        self.events: list[dict] = []
        self.ended = False
        self.sending_speech = False

    def say(self, turn) -> None:
        for i, (words, _ms, pause) in enumerate(turn.pieces):
            pcm = conditions.apply(speak(words), self.cond, self.rng)
            self.queue.append(("mark", b"speech_start"))
            for k in range(0, len(pcm), FRAME_BYTES):
                self.queue.append(("speech", pcm[k:k + FRAME_BYTES].ljust(FRAME_BYTES, b"\0")))
            self.queue.append(("mark", b"speech_end"))
            if pause and i < len(turn.pieces) - 1:
                self.queue.append(("mark", b"pause_start"))
                bg = conditions.background(pause, self.cond, self.rng)
                for k in range(0, len(bg), FRAME_BYTES):
                    self.queue.append(("pause", bg[k:k + FRAME_BYTES]))
                self.queue.append(("mark", b"pause_end"))
        self.queue.append(("mark", b"turn_end"))

    def agent_speech_since(self, t: float) -> list[float]:
        return [ts for ts, r in self.agent if ts >= t and r > SPEECH_RMS]

    def last_agent_speech(self) -> float:
        loud = [ts for ts, r in self.agent if r > SPEECH_RMS]
        return loud[-1] if loud else 0.0


async def _sender(ws, line: Line):
    t0, n = time.monotonic(), 0
    while not line.ended:
        while line.queue and line.queue[0][0] == "mark":
            line.marks.append((line.queue.popleft()[1].decode(), time.monotonic()))
        if line.queue:
            kind, frame = line.queue.popleft()
            line.sending_speech = kind == "speech"
        else:
            frame = conditions.background(FRAME_MS, line.cond, line.rng)
            line.sending_speech = False
        try:
            await ws.send(frame)
        except websockets.ConnectionClosed:
            line.ended = True
            return
        n += 1
        await asyncio.sleep(max(0.0, t0 + n * FRAME_MS / 1000 - time.monotonic()))


async def _receiver(ws, line: Line, out: RunResult):
    try:
        async for msg in ws:
            now = time.monotonic()
            if isinstance(msg, bytes):
                line.agent.append((now, _rms(msg)))
                continue
            e = json.loads(msg)
            e["_t"] = now
            line.events.append(e)
            out.events.append(e)
            if e.get("type") == "call":
                out.call_id = e.get("id", "")
            elif e.get("type") == "say":
                out.say_terms[e.get("id")] = e.get("terms", [])
            elif e.get("type") in ("end", "transfer", "error"):
                line.ended = line.ended or e.get("type") == "error"
                line.events.append({"type": "_over", "_t": now})
    except websockets.ConnectionClosed:
        pass
    line.ended = True


def _over(line: Line) -> bool:
    return line.ended or any(e["type"] == "_over" for e in line.events)


async def _agent_turn(line: Line, since: float, wait: float = 30.0) -> list[str]:
    """Wait for the agent's turn to end, then return the lines it said since then.

    A system that reports each line as played (``{"type": "played", "id": ...}``) has ended its
    turn when every line it announced is played and the line has been quiet a moment. Without
    those reports, only a longer quiet will do: a local voice can pause a second between lines
    while it prepares the next one, and a caller who took that pause for the end of the turn
    would answer the wrong line."""
    start = time.monotonic()
    while time.monotonic() - start < wait:
        await asyncio.sleep(0.05)
        quiet = time.monotonic() - line.last_agent_speech()
        said = [e for e in line.events if e.get("type") == "say" and e["_t"] >= since]
        done = {e.get("id") for e in line.events if e.get("type") in ("played", "interrupted")}
        reports = any(e.get("type") == "played" for e in line.events)
        if reports and said and all(e.get("id") in done for e in said) and quiet > 0.4:
            break
        if not reports and line.agent_speech_since(since) and quiet > IDLE:
            break
        if _over(line) and quiet > 0.4:
            break
    return [e.get("text", "") for e in line.events if e.get("type") == "say" and e["_t"] >= since]


def measure(line: Line) -> dict:
    marks = line.marks
    ends = [t for k, t in marks if k == "turn_end"]
    starts = [t for k, t in marks if k == "speech_start"]
    gaps = []
    for t in ends:
        nxt = [s for s in starts if s > t]
        heard = [a for a in line.agent_speech_since(t) if not nxt or a < nxt[0]]
        if heard:
            gaps.append((heard[0] - t) * 1000)
    pauses = list(zip([t for k, t in marks if k == "pause_start"],
                      [t for k, t in marks if k == "pause_end"]))
    cut = sum(1 for a, b in pauses if any(a <= ts <= b for ts in line.agent_speech_since(a)))
    spans = list(zip([t for k, t in marks if k == "speech_start"],
                     [t for k, t in marks if k == "speech_end"]))
    loud = [ts for ts, r in line.agent if r > SPEECH_RMS]
    onsets = [ts for i, ts in enumerate(loud) if i == 0 or ts - loud[i - 1] > 0.3]
    over = sum(1 for ts in onsets if any(a <= ts <= b for a, b in spans))
    return {"gaps_ms": [round(g) for g in gaps], "gap_p95_ms": percentile(gaps, 95),
            "cut_offs": cut, "talk_over": over}


async def run(base_url: str, sc: Scenario, max_turns: int = 20, timeout: float = 300,
              seed: int = 0) -> RunResult:
    out = RunResult(sc.id, "audio")
    caller = Caller(sc)
    for t in sc.turns():                      # synthesize every line before the call starts
        for words, _, _ in t.pieces:
            speak(words)
    for _, words in sc.data["caller"].get("answers", []):
        speak(words)
    line = Line(dict(sc.data["conditions"]), seed)

    async def talk():
        url = ws_url(base_url, f"/ws/audio?pack={sc.pack}")
        async with websockets.connect(url, max_size=None) as ws:
            tasks = [asyncio.create_task(_sender(ws, line)),
                     asyncio.create_task(_receiver(ws, line, out))]
            since = time.monotonic()
            lines = await _agent_turn(line, since)
            for _ in range(max_turns):
                if _over(line):
                    break
                turn = caller.reply(lines)
                if turn is None:
                    break
                out.caller_turns.append(turn.text)
                line.say(turn)
                while line.queue and not line.ended:
                    await asyncio.sleep(0.02)
                since = time.monotonic()
                lines = await _agent_turn(line, since)
            try:
                await ws.send(json.dumps({"type": "hangup"}))
            except websockets.ConnectionClosed:
                pass
            line.ended = True
            for task in tasks:
                task.cancel()

    try:
        await asyncio.wait_for(talk(), timeout=timeout)
    except Exception as e:                    # noqa: BLE001 - a failed run is a result
        if not isinstance(e, asyncio.CancelledError):
            out.error = f"{type(e).__name__}: {e}"
    line.ended = True
    out.measures = measure(line)
    await asyncio.sleep(0.5)
    return out
