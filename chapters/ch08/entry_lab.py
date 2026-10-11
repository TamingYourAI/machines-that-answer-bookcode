"""Builders' Chapter 8 lab: connecting to the business, every way in.

Six steps:

  1. three entry points  the same two seconds of a Service Line call over SIP
                         (RTP), a WebSocket media stream, and WebRTC; each
                         adapter delivers the one internal contract
  2. the adapter matrix  what five entry points give and give up, and which
                         of those claims a conformance check exercised
  3. loss                the same 1 percent packet loss on RTP over UDP and
                         on a WebSocket over TCP
  4. barge-in            how much of the fee line plays on after the caller
                         says yes, and what the agent records as heard
  5. context             the five screen-pop fields across two transfers, in
                         a SIP header and as attached data
  6. after the transfer  what the agent pays while it stays in the audio
                         path, and the desk's disposition arriving late

Modes (select with ENTRY_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. The companion app's transports are the live
           versions of the WebSocket and WebRTC adapters.

  python3 entry_lab.py                  run and print the report
  python3 entry_lab.py --write-fixture  regenerate fixtures/ from the data
  python3 entry_lab.py --check          compare with the frozen output

Evidence class of every number printed: simulated. The audio is synthetic,
the networks are stand-in models, and the platforms are fixtures.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import random
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

# ---------------------------------------------------------------- the contract

FRAME_MS, RATE = 20, 16_000            # the internal format, fixed once
FRAME_BYTES = RATE * FRAME_MS // 1000 * 2


@dataclass(frozen=True)
class Event:
    plane: str        # "media", "control", or "context"
    kind: str
    data: object


# Every adapter turns its entry point into these events, and nothing else.
CONTRACT = {
    "media": ("audio: 20 ms frames, 16-bit PCM, 16 kHz",
              "play: chunks tagged with their line", "clear"),
    "control": ("start", "dtmf", "transfer", "stop, with a reason"),
    "context": ("caller and number dialed", "attached data, in and out",
                "the disposition"),
}

# ---------------------------------------------------------------- audio


def formant(hz: float) -> float:
    return 1 + ((hz - 700) / 300) ** 2 + ((hz - 1200) / 400) ** 2


def caller(rate: int, ms: int = 2000) -> list[int]:
    """A synthetic vowel: harmonics of 140 Hz shaped by two formants."""
    out = []
    for i in range(rate * ms // 1000):
        t = i / rate
        v = sum(math.sin(2 * math.pi * 140 * k * t) / formant(140 * k)
                for k in range(1, 20) if 140 * k < rate / 2)
        out.append(int(6000 * v))
    return out


def ulaw_encode(s: int) -> int:
    """G.711 mu-law, one 16-bit sample to one byte."""
    sign = 0x80 if s < 0 else 0
    s = min(abs(s), 32635) + 0x84
    exp, mask = 7, 0x4000
    while exp and not s & mask:
        exp, mask = exp - 1, mask >> 1
    return ~(sign | exp << 4 | (s >> (exp + 3)) & 0x0F) & 0xFF


def ulaw_decode(b: int) -> int:
    b = ~b & 0xFF
    s = (((b & 0x0F) << 3) + 0x84 << ((b >> 4) & 7)) - 0x84
    return -s if b & 0x80 else s


def pcm(samples: list[int]) -> bytes:
    clamped = [max(-32768, min(32767, s)) for s in samples]
    return struct.pack(f"<{len(clamped)}h", *clamped)


def from_8k(ulaw: bytes) -> bytes:
    """mu-law at 8 kHz to the contract: decode, then double the rate."""
    x = [ulaw_decode(b) for b in ulaw]
    up = []
    for i, s in enumerate(x):
        up += [s, (s + x[min(i + 1, len(x) - 1)]) // 2]
    return pcm(up)


def from_48k(x: list[int]) -> bytes:
    """Decoded WebRTC audio at 48 kHz to the contract (stand-in filter)."""
    return pcm([sum(x[i:i + 3]) // 3 for i in range(0, len(x), 3)])


# ---------------------------------------------------------------- 1. adapters

KEYS = "0123456789*#"
PCMU, TEL_EVENT = 0, 101


def rtp_packets(digit: str) -> list[dict]:
    """Two seconds of the caller as RTP: G.711 every 20 ms, then one key
    press as a telephone event whose end is sent three times."""
    x = caller(8000)
    frames = [x[i:i + 160] for i in range(0, len(x), 160)]
    pkts = [{"pt": PCMU, "ts": i * 160,
             "payload": bytes(ulaw_encode(s) for s in f)}
            for i, f in enumerate(frames)]
    ev = bytes([KEYS.index(digit), 0x80 | 10, 0x03, 0x20])
    return pkts + [{"pt": TEL_EVENT, "ts": 16_000, "payload": ev}] * 3


def ws_messages(start: dict, digit: str) -> list[str]:
    """The same call as a platform's WebSocket media stream (JSON)."""
    x = caller(8000)
    msgs = [json.dumps({"event": "start", "start": start})]
    for i in range(len(x) // 160):
        chunk = bytes(ulaw_encode(s) for s in x[i * 160:i * 160 + 160])
        msgs.append(json.dumps({
            "event": "media", "sequenceNumber": str(i + 2),
            "media": {"track": "inbound", "chunk": str(i + 1),
                      "timestamp": str(i * 20),
                      "payload": base64.b64encode(chunk).decode()},
            "streamSid": start["streamSid"]}))
    msgs.append(json.dumps({"event": "dtmf", "dtmf": {"digit": digit}}))
    msgs.append(json.dumps({"event": "stop"}))
    return msgs


class Outbound:
    """Audio sent to the entry point and not yet played to the caller."""
    STOP = ""

    def __init__(self) -> None:
        self.queued_ms = 0

    def play(self, ms: int) -> None:
        self.queued_ms += ms

    def clear(self) -> str:
        """Barge-in: drop everything that has not played."""
        self.queued_ms = 0
        return self.STOP


class SipEntry(Outbound):
    name = "SIP from the suite"
    STOP = "stop sending RTP"

    def receive(self, invite: dict, packets: list[dict]):
        yield Event("context", "start", invite)
        ends = set()
        for p in packets:
            if p["pt"] == PCMU:
                yield Event("media", "audio", from_8k(p["payload"]))
            elif p["pt"] == TEL_EVENT and p["payload"][1] & 0x80:
                if p["ts"] not in ends:        # one press, three end packets
                    ends.add(p["ts"])
                    yield Event("control", "dtmf", KEYS[p["payload"][0]])
        yield Event("control", "stop", "BYE")

    def transfer(self, target: str) -> str:
        return f"REFER sip:{target}"

    def write(self, fields: dict) -> dict:
        return {"attached_data": dict(fields)}


class WebSocketEntry(Outbound):
    name = "WebSocket stream"
    STOP = json.dumps({"event": "clear"})      # the platform drops its buffer

    def receive(self, messages: list[str]):
        for m in map(json.loads, messages):
            if m["event"] == "start":
                yield Event("context", "start", m["start"])
            elif m["event"] == "media":
                ulaw = base64.b64decode(m["media"]["payload"])
                yield Event("media", "audio", from_8k(ulaw))
            elif m["event"] == "dtmf":
                yield Event("control", "dtmf", m["dtmf"]["digit"])
            elif m["event"] == "stop":
                yield Event("control", "stop", "stream closed")

    def transfer(self, target: str) -> dict:
        return {"action": "transfer", "to": target}

    def write(self, fields: dict) -> dict:
        return {"attached_data": dict(fields)}


class WebRtcEntry(Outbound):
    name = "WebRTC in the app"
    STOP = "stop the outbound track"

    def receive(self, session: dict, frames: list[list[int]],
                keys: list[str]):
        yield Event("context", "start", session)
        for f in frames:
            yield Event("media", "audio", from_48k(f))
        for k in keys:
            yield Event("control", "dtmf", json.loads(k)["key"])
        yield Event("control", "stop", "track ended")

    def write(self, fields: dict) -> dict:
        return {"case": dict(fields)}


def webrtc_frames() -> list[list[int]]:
    x = caller(48_000)
    return [x[i:i + 960] for i in range(0, len(x), 960)]


def wire_bytes(path: str, msg: str | None = None) -> int:
    """Bytes on the wire for 20 ms of audio, with every header counted."""
    ip, udp, tcp, rtp = 20, 8, 20, 12
    if path == "sip":
        return 160 + rtp + udp + ip                  # G.711 payload
    if path == "ws":
        return len(msg) + 8 + tcp + ip               # masked frame header
    return 32_000 // 8 // 50 + rtp + 10 + udp + ip  # Opus at 32 kbit/s, SRTP


def summary(events: list[Event]) -> tuple[int, int, set]:
    audio = [e for e in events if e.kind == "audio"]
    shapes = {len(e.data) for e in audio}
    kinds = [e.kind for e in events if e.kind != "audio"]
    return len(audio), kinds.count("dtmf"), shapes | set(kinds)


# ---------------------------------------------------------------- 2. matrix

PATHS = ("SIP", "WebSocket", "WebRTC", "bot channel", "agent-agent")
ROWS = ("audio in", "touch-tones", "barge-in stop", "transfer",
        "context in", "context out")


def conformance(adapter, data: dict) -> dict[str, bool]:
    """Checks run against a live adapter; a claim without one is untested."""
    if adapter is None:
        return {}
    ev = list(entry_events(adapter, data))
    frames, digits, _ = summary(ev)
    start = next(e.data for e in ev if e.kind == "start")
    ok = {"audio in": frames == 100 and all(
              len(e.data) == FRAME_BYTES for e in ev if e.kind == "audio"),
          "touch-tones": digits == 1,
          "barge-in stop": stops(adapter),
          "context in": bool(start)}
    if hasattr(adapter, "transfer"):
        ok["transfer"] = "billing" in str(adapter.transfer("billing@acd"))
    fields = data["fields"]
    ok["context out"] = set(next(iter(adapter.write(fields).values()))) == \
        set(fields)
    return ok


def stops(adapter) -> bool:
    adapter.play(1000)
    return bool(adapter.clear()) and adapter.queued_ms == 0


def entry_events(adapter, data: dict):
    if isinstance(adapter, SipEntry):
        return adapter.receive(data["invite"], rtp_packets(data["digit"]))
    if isinstance(adapter, WebSocketEntry):
        return adapter.receive(ws_messages(data["ws_start"], data["digit"]))
    return adapter.receive(data["session"], webrtc_frames(),
                           [json.dumps({"key": data["digit"]})])


# ---------------------------------------------------------------- 3. loss

ONE_WAY_MS, BUFFER_MS = 40, 60          # Chapter 7's stand-ins


def udp_arrivals(n: int, lost: set[int]) -> list[float | None]:
    """RTP over UDP: a lost packet never arrives; nothing waits for it."""
    return [None if i in lost else FRAME_MS * i + ONE_WAY_MS
            for i in range(n)]


def tcp_arrivals(n: int, lost: set[int], dupacks: int = 3) -> list[float]:
    """A WebSocket over TCP: a lost segment is sent again once three later
    ones are acknowledged (a round trip later), and TCP delivers in order,
    so every frame behind it waits."""
    out, ready = [], 0.0
    for i in range(n):
        t = FRAME_MS * i + ONE_WAY_MS
        if i in lost:
            t = FRAME_MS * (i + dupacks) + 3 * ONE_WAY_MS
        ready = max(ready, t)
        out.append(ready)
    return out


def play_out(arrivals: list[float | None], buffer_ms: int) -> dict:
    n = len(arrivals)
    late = [a - (FRAME_MS * i + ONE_WAY_MS) for i, a in enumerate(arrivals)
            if a is not None]
    return {"missing": sum(a is None for a in arrivals) / n,
            "late": sum(x > buffer_ms for x in late) / n,
            "worst": max(late) + ONE_WAY_MS, "needs": max(late)}


# ---------------------------------------------------------------- 4. barge-in

FEE_LINE = ("The first opening is Tuesday at nine. There's a forty-dollar "
            "call-out fee. Shall I book it?")
WORDS_PER_MIN = 150                     # the voice brief (Chapter 3)
MARK_EVERY_MS = 200                     # a mark after each chunk sent


def line_ms(text: str) -> int:
    return round(len(text.split()) / WORDS_PER_MIN * 60_000)


def chars_at(text: str, ms: float) -> int:
    return min(len(text), int(len(text) * ms / line_ms(text)))


def barge_in(path: str, at_ms: int) -> tuple[int, str]:
    """Audio that plays on after the cancel, and what the agent records."""
    total = line_ms(FEE_LINE)
    if path == "sip":             # the agent paces its own packets
        return ONE_WAY_MS, f"{chars_at(FEE_LINE, at_ms)} of 91, own clock"
    if path == "ws-clear":        # clear crosses the network; marks come back
        heard = at_ms // MARK_EVERY_MS * MARK_EVERY_MS
        return ONE_WAY_MS, f"{chars_at(FEE_LINE, heard)} of 91, from marks"
    if path == "ws-no-clear":     # the whole line was pushed, as fast as made
        return total - at_ms, "91 of 91: sent, not heard"
    return total - at_ms, "the platform's transcript"


# ---------------------------------------------------------------- 5. context

UUI_LIMIT = 128                          # octets, the old ISDN limit
ORDER = ("account", "verified", "intent", "ticket", "last two turns")


def in_header(fields: dict) -> dict:
    """Pack fields into one User-to-User header, in order, until full."""
    kept, used = {}, 0
    for k in ORDER:
        size = len(f"{k}={fields[k]};".encode())
        if used + size <= UUI_LIMIT:
            kept[k], used = fields[k], used + size
    return kept


def transfer_twice(fields: dict, carrier: str) -> tuple[dict, dict]:
    """Agent to billing, then billing to payments. A header belongs to one
    SIP leg; attached data belongs to the call, so every leg reads it."""
    if carrier == "header":
        first = in_header(fields)
        return first, {}                # the second leg is a new INVITE
    return dict(fields), dict(fields)


# ---------------------------------------------------------------- 6. after

WAIT_MIN, TALK_MIN, PER_MIN = 6, 8, 0.18


def bridged_cost(released: bool) -> tuple[int, float]:
    minutes = 0 if released else WAIT_MIN + TALK_MIN
    return minutes, round(minutes * PER_MIN, 2)


SECRET = b"stand-in webhook secret"


def sign(body: str) -> str:
    return hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()


def apply_webhooks(deliveries: list[dict], cases: dict) -> list[str]:
    """The desk's disposition: verified, applied once, to the case store."""
    seen, out = set(), []
    for d in deliveries:
        if not hmac.compare_digest(sign(d["body"]), d["signature"]):
            out.append(f"{d['id']}  refused: the signature does not match")
            continue
        if d["id"] in seen:
            out.append(f"{d['id']}  a retry: ignored, already applied")
            continue
        seen.add(d["id"])
        body = json.loads(d["body"])
        case = cases[body["call"]]
        out.append(f"{d['id']}  applied to case {case}: "
                   f"{body['disposition']}")
    return out


# ---------------------------------------------------------------- inputs

CLAIMS = {                # what each path's documentation says it does
    "SIP": ("G.711 8k", "events", "stop RTP", "REFER", "attached",
            "attached"),
    "WebSocket": ("mu-law 8k", "messages", "clear", "API call", "parameters",
                  "API call"),
    "WebRTC": ("Opus 48k", "keypad msg", "stop track", "bridge", "sign-in",
               "case"),
    "bot channel": ("text only", "platform", "none", "platform", "fields",
                  "fields"),
    "agent-agent": ("none", "none", "n/a", "hand back", "task", "result"),
}


FIELDS = {"account": "5108", "verified": "PIN", "intent": "billing question",
          "ticket": "T-88213",
          "last two turns": "Caller: My bill doubled this month. I want to "
          "talk to a person. Agent: I'll put you through to billing now. I'm "
          "sending them your account and what you've told me."}


def deliveries() -> list[dict]:
    body = json.dumps({"call": "CA-0142", "disposition":
                       "resolved, bill explained", "after_hangup_s": 160})
    forged = body.replace("resolved", "refund due")
    return [{"id": "d-501", "body": body, "signature": sign(body)},
            {"id": "d-501", "body": body, "signature": sign(body)},
            {"id": "d-502", "body": forged, "signature": sign(body)}]


def inputs(mode: str) -> dict:
    if mode == "mock":
        rng = random.Random(8)
        return {
            "invite": {"from": "+13125550142", "to": "+13125550100",
                       "call": "CA-0142"},
            "ws_start": {"streamSid": "MZ-0142", "callSid": "CA-0142",
                         "customParameters": {"line": "service"}},
            "session": {"user": "signed in", "account": "5108"},
            "digit": "2", "fields": FIELDS,
            "lost": sorted(rng.sample(range(3000), 30)),
            "barge_in_ms": 3300, "cases": {"CA-0142": "c-5108"},
            "claims": {k: list(v) for k, v in CLAIMS.items()},
            "deliveries": deliveries()}
    if mode == "fixture":
        return json.loads((FIXTURES / "entry.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ---------------------------------------------------------------- report



def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    say = out.append
    say(f"entry lab, mode={mode}; evidence class: simulated")
    say("")
    say("1. one call, three entry points, one contract")
    say(f"   {'entry point':<20}{'on the wire':<28}{'kbit/s':>7}{'frames':>8}"
        f"{'keys':>6}")
    sip, ws, rtc = SipEntry(), WebSocketEntry(), WebRtcEntry()
    msg = ws_messages(data["ws_start"], data["digit"])[1]
    rows = [(sip, "RTP, G.711 mu-law, 8 kHz", wire_bytes("sip")),
            (ws, "JSON, base64 mu-law, 8 kHz", wire_bytes("ws", msg)),
            (rtc, "SRTP, Opus at 32 kbit/s", wire_bytes("rtc"))]
    shapes = []
    for adapter, wire, b in rows:
        n, keys, shape = summary(list(entry_events(adapter, data)))
        shapes.append(shape)
        say(f"   {adapter.name:<20}{wire:<28}{b * 8 / FRAME_MS:>7.1f}{n:>8}"
            f"{keys:>6}")
    same = "yes" if all(s == shapes[0] for s in shapes) else "no"
    say(f"   the same contract from all three: {same} (20 ms frames of "
        f"{FRAME_BYTES} bytes,")
    say("   start, one touch-tone, stop)")
    say("")
    say("2. the adapter matrix (* claimed, not yet tested)")
    live = {"SIP": sip, "WebSocket": ws, "WebRTC": rtc}
    tested = {p: conformance(live.get(p), data) for p in PATHS}
    say(f"   {'':<14}" + "".join(f"{p:<12}" for p in PATHS).rstrip())
    for r, row in enumerate(ROWS):
        cells = []
        for p in PATHS:
            v = data["claims"][p][r]
            t = tested[p].get(row)
            cells.append(v if t else "FAILED" if t is False else v + "*")
        say(f"   {row:<14}" + "".join(f"{c:<12}" for c in cells).rstrip())
    say(f"   {'tested':<14}" + "".join(
        f"{str(sum(tested[p].values())) + ' of 6':<12}" for p in PATHS).rstrip())
    say("")
    lost = set(data["lost"])
    say(f"3. the same loss on two transports ({len(lost) / 3000 * 100:.0f}% of 3000 "
        f"packets, one way {ONE_WAY_MS} ms,")
    say(f"   a {BUFFER_MS} ms jitter buffer)")
    say(f"   {'transport':<22}{'never arrive':>13}{'too late':>10}"
        f"{'worst delay':>13}")
    for name, arr in (("RTP over UDP", udp_arrivals(3000, lost)),
                      ("WebSocket over TCP", tcp_arrivals(3000, lost))):
        r = play_out(arr, BUFFER_MS)
        say(f"   {name:<22}{r['missing'] * 100:>12.1f}%{r['late'] * 100:>9.1f}%"
            f"{r['worst']:>10.0f} ms")
    need = play_out(tcp_arrivals(3000, lost), BUFFER_MS)["needs"]
    say(f"   to play every TCP frame, the buffer must grow to {need:.0f} ms")
    say("")
    at = data["barge_in_ms"]
    say(f"4. barge-in {at:,} ms into the fee line ({len(FEE_LINE)} characters, "
        f"{line_ms(FEE_LINE):,} ms)")
    say(f"   {'path':<34}{'plays on':>9}  recorded as heard")
    for label, path in (("SIP, paced by the agent", "sip"),
                        ("WebSocket, clear and marks", "ws-clear"),
                        ("WebSocket, no clear", "ws-no-clear"),
                        ("bot channel, platform plays", "bot channel")):
        ms, rec = barge_in(path, at)
        say(f"   {label:<34}{f'{ms:,} ms':>9}  {rec}")
    say("")
    fields = data["fields"]
    say("5. context across two transfers (agent to billing, then payments)")
    say(f"   {'carried in':<28}{'to billing':<16}to payments")
    for label, how in (("a SIP header (User-to-User)", "header"),
                       ("attached data", "attached")):
        a, b = transfer_twice(fields, how)
        say(f"   {label:<28}{f'{len(a)} of 5 fields':<16}{len(b)} of 5 fields")
    need = len(f"last two turns={fields['last two turns']};".encode())
    say(f"   the header holds {UUI_LIMIT} octets; the last two turns alone "
        f"need {need}")
    say("")
    say("6. after the transfer")
    say(f"   the agent in the audio path ({WAIT_MIN} min wait, {TALK_MIN} min "
        "with a person):")
    for label, released in (("bridged", False), ("released", True)):
        m, c = bridged_cost(released)
        note = (f"${c:.2f} a transfer at ${PER_MIN:.2f} a minute" if m else
                "REFER: the agent leaves the call")
        say(f"     {label:<10}{m:>2} minutes, {note}")
    say("   the desk's disposition, 160 s after the caller hung up:")
    for line in apply_webhooks(data["deliveries"], data["cases"]):
        say(f"     {line}")
    return "\n".join(out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("ENTRY_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"entry_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "entry.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/entry.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("ENTRY_LAB_MODE", "mock")))
    else:
        run_mode()
