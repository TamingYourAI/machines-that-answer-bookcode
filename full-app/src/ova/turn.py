"""Turn-taking: when the caller starts, when they have finished, and when they talk over us.

An energy detector with an adaptive noise floor, plus timing rules. It is deliberately simple
and every decision is logged with the numbers that drove it (builders' Chapter 11): a VAD
model (Silero) and a semantic end-of-turn check can replace `is_speech` and `end_of_turn`
behind the same interface (M2). The working values are the book's: a turn ends after about
600 ms of silence, and a barge-in needs about 200 ms of speech so a cough does not cut the
agent off.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .audio import FRAME_MS, dbfs


@dataclass
class TurnConfig:
    start_ms: int = 120             # speech this long starts a turn
    end_silence_ms: int = 600       # silence this long ends it
    barge_in_ms: int = 200          # speech this long, while the agent talks, cuts it off
    min_turn_ms: int = 250          # shorter than this is noise, not a turn
    max_turn_ms: int = 30000
    margin_db: float = 12.0         # above the noise floor counts as speech
    floor_db: float = -60.0         # starting noise floor
    min_speech_db: float = -48.0    # never call quieter than this speech
    preroll_ms: int = 200           # audio kept from before the start


@dataclass
class TurnEvent:
    kind: str                       # start | end | barge_in | noise
    at_ms: float
    audio: bytes = b""
    meta: dict = field(default_factory=dict)


class TurnDetector:
    def __init__(self, cfg: TurnConfig | None = None):
        self.cfg = cfg or TurnConfig()
        self.floor = self.cfg.floor_db
        self.t = 0.0
        self.in_speech = False
        self.speech_run = 0.0
        self.silence_run = 0.0
        self.buf: list[bytes] = []
        self.pre: list[bytes] = []
        self.turn_start = 0.0
        self.agent_speaking = False
        self.barged = False
        self.log: list[dict] = []

    def is_speech(self, level: float) -> bool:
        return level > max(self.floor + self.cfg.margin_db, self.cfg.min_speech_db)

    def feed(self, frame: bytes) -> list[TurnEvent]:
        """One 20 ms frame of 16 kHz PCM in; zero or more events out."""
        cfg, out = self.cfg, []
        self.t += FRAME_MS
        level = dbfs(frame)
        speech = self.is_speech(level)
        if not speech and not self.in_speech:      # track the room, slowly
            self.floor = 0.95 * self.floor + 0.05 * max(level, -90.0)
        if speech:
            self.speech_run += FRAME_MS
            self.silence_run = 0.0
        else:
            self.silence_run += FRAME_MS
            if not self.in_speech:
                self.speech_run = 0.0
        if not self.in_speech:
            self.pre.append(frame)
            keep = cfg.preroll_ms // FRAME_MS
            self.pre = self.pre[-keep:]
            if self.speech_run >= cfg.start_ms:
                self.in_speech = True
                self.turn_start = self.t - self.speech_run
                self.buf = list(self.pre)
                self.barged = False
                out.append(TurnEvent("start", self.turn_start, meta={"db": round(level, 1)}))
            return out + self._barge(level)
        self.buf.append(frame)
        out += self._barge(level)
        length = self.t - self.turn_start
        if self.silence_run >= cfg.end_silence_ms or length >= cfg.max_turn_ms:
            audio = b"".join(self.buf)
            speech_ms = length - self.silence_run
            self.in_speech, self.buf, self.speech_run = False, [], 0.0
            kind = "end" if speech_ms >= cfg.min_turn_ms else "noise"
            ev = TurnEvent(kind, self.t, audio, {"speech_ms": speech_ms,
                                                 "silence_ms": self.silence_run,
                                                 "floor_db": round(self.floor, 1)})
            self.log.append({"t": self.t, "event": kind, **ev.meta})
            out.append(ev)
        return out

    def _barge(self, level: float) -> list[TurnEvent]:
        if self.agent_speaking and not self.barged and self.in_speech and \
                self.speech_run >= self.cfg.barge_in_ms:
            self.barged = True
            self.log.append({"t": self.t, "event": "barge_in", "db": round(level, 1)})
            return [TurnEvent("barge_in", self.t, meta={"db": round(level, 1)})]
        return []
