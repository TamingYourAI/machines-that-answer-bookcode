"""Builders' Chapter 7 lab: transport and telephony, with no trunk needed.

Six steps:

  1. the invite         a SIP INVITE from the carrier (a fixture): who is calling, how well
                        the carrier vouches for it, the codecs offered, touch-tones, and the
                        address the audio will go to; then the answer
  2. narrowband         what the telephone path removes from a voice, and what converting
                        twice adds
  3. the jitter buffer  delay against late packets, for five buffer sizes
  4. touch-tones        the same digits sent in the audio and as events, through a clean line
                        and a lossy one
  5. the outbound gate  outbound attempts checked for emergency numbers, destinations,
                        premium rates, rate, spend, and the hour
  6. texts              confirmation texts checked for registration, consent, and opt-out

Modes (select with TELEPHONY_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Point a trunk at the companion app and export the INVITE and
           an RTP capture in the fixture schema.

  python3 telephony_lab.py                  run and print the report
  python3 telephony_lab.py --write-fixture  regenerate fixtures/ from the data here
  python3 telephony_lab.py --check          compare with the frozen output in outputs/

Evidence class of every number printed: simulated. The signals are synthetic, the network is a
stand-in model, and the SIP messages are fixtures; nothing here measures a carrier.
"""
from __future__ import annotations

import base64
import json
import math
import os
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

# ---------------------------------------------------------------- 1. the invite


def _b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


INVITE = "\r\n".join([
    "INVITE sip:+13125550100@agent.utility.example SIP/2.0",
    "Via: SIP/2.0/TLS 203.0.113.10:5061;branch=z9hG4bK77f3",
    "From: <sip:+13125550142@carrier.example>;tag=4417",
    "To: <sip:+13125550100@agent.utility.example>",
    "Call-ID: 7f3a2231@carrier.example",
    "P-Asserted-Identity: <sip:+13125550142@carrier.example>",
    "Identity: " + ".".join([_b64({"alg": "ES256", "ppt": "shaken"}),
                             _b64({"attest": "A", "orig": {"tn": "13125550142"},
                                   "dest": {"tn": ["13125550100"]}}), "sig"]),
    "Content-Type: application/sdp",
    "",
    "v=0",
    "o=carrier 2231 1 IN IP4 10.20.30.40",
    "c=IN IP4 10.20.30.40",
    "m=audio 40000 RTP/AVP 0 8 101",
    "a=rtpmap:0 PCMU/8000",
    "a=rtpmap:8 PCMA/8000",
    "a=rtpmap:101 telephone-event/8000",
    "a=fmtp:101 0-16",
    "a=ptime:20",
])
AGENT_CODECS = ["G722/8000", "PCMU/8000", "PCMA/8000"]    # in order of preference
PRIVATE = re.compile(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)")


def parse_invite(msg: str) -> dict:
    head, _, sdp = msg.partition("\r\n\r\n")
    headers = dict(line.split(": ", 1) for line in head.split("\r\n")[1:])
    ident = headers.get("Identity", "")
    claims = {}
    if ident.count(".") >= 2:
        payload = ident.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    rtpmap = dict(re.findall(r"a=rtpmap:(\d+) (\S+)", sdp))
    m = re.search(r"m=audio (\d+) RTP/AVP ([\d ]+)", sdp)
    return {"from": re.search(r"sip:(\+\d+)", headers["From"]).group(1),
            "attest": claims.get("attest", "none"),
            "address": re.search(r"c=IN IP4 (\S+)", sdp).group(1),
            "port": int(m.group(1)),
            "offer": [rtpmap.get(pt, pt) for pt in m.group(2).split()],
            "ptime": int(re.search(r"a=ptime:(\d+)", sdp).group(1))}


def answer(offer: dict) -> dict:
    codec = next((c for c in AGENT_CODECS if c in offer["offer"]), None)
    dtmf = "telephone-event/8000" in offer["offer"]
    return {"codec": codec, "dtmf": "events (RFC 4733)" if dtmf else "in the audio",
            "nat": bool(PRIVATE.match(offer["address"]))}


# ---------------------------------------------------------------- 2. narrowband

RATE = 16000


def voice(ms: int = 400) -> list[float]:
    """A stand-in syllable: a vowel (harmonics of 180 Hz up to 3.4 kHz), then an "s"
    (noise between 4.5 and 7 kHz), at 16 kHz."""
    rng = random.Random(7)
    n = RATE * ms // 1000
    half = n // 2
    x = [sum(math.sin(2 * math.pi * 180 * k * i / RATE) / k for k in range(1, 19))
         * 0.12 for i in range(half)]
    phases = [rng.uniform(0, 2 * math.pi) for _ in range(26)]
    x += [sum(math.sin(2 * math.pi * (4500 + 100 * j) * i / RATE + phases[j])
              for j in range(26)) * 0.03 for i in range(n - half)]
    return x


def lowpass(x: list[float], cutoff: float, taps: int = 63) -> list[float]:
    """A windowed-sinc filter: what an 8 kHz channel lets through."""
    fc = cutoff / RATE
    mid = taps // 2
    h = []
    for i in range(taps):
        k = i - mid
        s = 2 * fc if k == 0 else math.sin(2 * math.pi * fc * k) / (math.pi * k)
        h.append(s * (0.54 - 0.46 * math.cos(2 * math.pi * i / (taps - 1))))
    n = len(x)                                  # centred: no delay, so no misalignment
    return [sum(h[j] * x[i + j - mid] for j in range(taps) if 0 <= i + j - mid < n)
            for i in range(n)]


def mulaw(v: float) -> float:
    """Encode and decode one sample with the G.711 mu-law curve (8 bits)."""
    mu = 255.0
    y = math.copysign(math.log1p(mu * min(1.0, abs(v))) / math.log1p(mu), v)
    q = round(y * 127) / 127
    return math.copysign((math.pow(1 + mu, abs(q)) - 1) / mu, q)


def phone_path(x: list[float]) -> list[float]:
    """Down to 8 kHz through the filter, mu-law, and back to 16 kHz."""
    y = lowpass(x, 3800)
    coded = [mulaw(v) for v in y[::2]]
    up = []
    for i, v in enumerate(coded):
        nxt = coded[i + 1] if i + 1 < len(coded) else v
        up += [v, (v + nxt) / 2]
    return up[: len(x)]


def energy(x: list[float]) -> float:
    return sum(v * v for v in x)


def high_share(x: list[float]) -> float:
    """The share of a signal's energy above 4 kHz."""
    low = lowpass(x, 4000)
    return energy([a - b for a, b in zip(x, low)]) / energy(x)


def snr_db(ref: list[float], y: list[float]) -> float:
    noise = energy([a - b for a, b in zip(ref, y)])
    return 10 * math.log10(energy(ref) / noise)


# ---------------------------------------------------------------- 3. the jitter buffer

N_PACKETS = 5000
BASE_MS = 40
BUFFERS_MS = (20, 40, 60, 80, 120)


def network(seed: int = 3) -> list[float]:
    """One-way delay of each 20 ms packet: a base, plus jitter with a long tail."""
    rng = random.Random(seed)
    return [BASE_MS + rng.expovariate(1 / 12) + (rng.random() < 0.01) * rng.uniform(60, 150)
            for _ in range(N_PACKETS)]


def late_share(delays: list[float], buffer_ms: int) -> float:
    return sum(d > BASE_MS + buffer_ms for d in delays) / len(delays)


# ---------------------------------------------------------------- 4. touch-tones

DTMF = {"1": (697, 1209), "2": (697, 1336), "3": (697, 1477), "4": (770, 1209),
        "5": (770, 1336), "6": (770, 1477), "7": (852, 1209), "8": (852, 1336),
        "9": (852, 1477), "*": (941, 1209), "0": (941, 1336), "#": (941, 1477)}
LOWS, HIGHS = (697, 770, 852, 941), (1209, 1336, 1477)
T_RATE = 8000
PACKET = T_RATE * 20 // 1000       # 160 samples: one 20 ms packet
TONE_PACKETS, GAP_PACKETS = 3, 3   # 60 ms of tone, 60 ms of silence per digit
DIGITS = "2231#"


def tone_packets(digits: str) -> list[list[float]]:
    pkts = []
    for d in digits:
        lo, hi = DTMF[d]
        for p in range(TONE_PACKETS):
            pkts.append([0.25 * (math.sin(2 * math.pi * lo * (p * PACKET + i) / T_RATE)
                                 + math.sin(2 * math.pi * hi * (p * PACKET + i) / T_RATE))
                         for i in range(PACKET)])
        pkts += [[0.0] * PACKET for _ in range(GAP_PACKETS)]
    return pkts


def goertzel(x: list[float], f: float) -> float:
    k = 2 * math.cos(2 * math.pi * f / T_RATE)
    s1 = s2 = 0.0
    for v in x:
        s1, s2 = v + k * s1 - s2, s1
    return s1 * s1 + s2 * s2 - k * s1 * s2


def detect(pkts: list[list[float]], min_packets: int = 2) -> str:
    """A digit is a pair of tones held for at least min_packets packets in a row."""
    out, run, last = "", 0, None
    for pkt in pkts:
        if energy(pkt) < 1e-3:
            d = None
        else:
            lo = max(LOWS, key=lambda f: goertzel(pkt, f))
            hi = max(HIGHS, key=lambda f: goertzel(pkt, f))
            d = next(k for k, v in DTMF.items() if v == (lo, hi))
        run = run + 1 if d == last else 1
        if d and d == last and run == min_packets:
            out += d
        last = d
    return out


def lossy(pkts: list[list[float]], lost: set[int]) -> list[list[float]]:
    """Packet loss hidden by repeating the last packet that arrived."""
    out, prev = [], [0.0] * PACKET
    for i, p in enumerate(pkts):
        prev = prev if i in lost else p
        out.append(prev)
    return out


def g711(pkts: list[list[float]]) -> list[list[float]]:
    return [[mulaw(v) for v in p] for p in pkts]


def events(digits: str, lost: set[int]) -> str:
    """RFC 4733 events travel in the same packet slots: updates while the key is held, then
    the end of the event three times. Each event carries its own timestamp, so two presses
    of one key stay two digits; a digit is lost only if every one of its packets is."""
    out = ""
    per = TONE_PACKETS + GAP_PACKETS
    for i, d in enumerate(digits):
        if any(k not in lost for k in range(i * per, (i + 1) * per)):
            out += d
    return out


# ---------------------------------------------------------------- 5. the outbound gate

EMERGENCY = {"911", "112", "999", "000", "933"}
PREMIUM = ("+1900", "+1976")
ALLOW_COUNTRY = "+1"
LIMITS = {"per_hour": 30, "spend_day": 20.00, "cost_per_min": 0.02, "minutes": 3}
HOURS = (8, 21)                    # local time at the called party


def gate(attempt: dict, placed_this_hour: int, spent_today: float) -> str:
    to = attempt["to"]
    digits = re.sub(r"\D", "", to)
    if digits in EMERGENCY or to in EMERGENCY:
        return "refused: emergency numbers are never dialed"
    if to.startswith(PREMIUM):
        return "refused: premium rate"
    if not to.startswith(ALLOW_COUNTRY):
        return "refused: outside the allowed countries"
    if placed_this_hour >= LIMITS["per_hour"]:
        return "refused: hourly limit"
    cost = LIMITS["cost_per_min"] * LIMITS["minutes"]
    if spent_today + cost > LIMITS["spend_day"]:
        return "refused: daily spend"
    if not HOURS[0] <= attempt["hour"] < HOURS[1] and attempt["kind"] != "owner":
        return "held: outside 8:00 to 21:00 for the called party"
    return "allowed"


def attempts() -> list[dict]:
    base = [{"to": "+13125550199", "hour": 18, "kind": "owner", "why": "owner, a transfer"},
            {"to": "+13125550142", "hour": 10, "kind": "customer",
             "why": "customer callback"},
            {"to": "911", "hour": 10, "kind": "customer", "why": "a caller's request"},
            {"to": "+19005550123", "hour": 10, "kind": "customer", "why": "premium number"},
            {"to": "+882345678901", "hour": 11, "kind": "customer",
             "why": "international"},
            {"to": "+13125550157", "hour": 22, "kind": "customer", "why": "late callback"}]
    burst = [{"to": f"+1312555{1000 + i:04d}", "hour": 14, "kind": "customer",
              "why": "a stolen credential"} for i in range(40)]
    return base + burst


# ---------------------------------------------------------------- 6. texts

SENDERS = {"+13125550100": {"kind": "10DLC", "registered": True},
           "+13125550101": {"kind": "10DLC", "registered": False},
           "+18885550100": {"kind": "toll-free", "registered": False}}


def may_text(msg: dict, consent: set[str], stopped: set[str]) -> str:
    s = SENDERS[msg["from"]]
    if not s["registered"]:
        return f"filtered by carriers: unregistered {s['kind']} number"
    if msg["to"] in stopped:
        return "refused: the recipient replied STOP"
    if msg["to"] not in consent and msg["kind"] != "reply":
        return "refused: no consent to text"
    return "sent"


def texts() -> tuple[list[dict], set[str], set[str]]:
    msgs = [{"from": "+13125550100", "to": "+13125550142", "kind": "confirmation"},
            {"from": "+13125550101", "to": "+13125550142", "kind": "confirmation"},
            {"from": "+18885550100", "to": "+13125550142", "kind": "confirmation"},
            {"from": "+13125550100", "to": "+13125550163", "kind": "confirmation"},
            {"from": "+13125550100", "to": "+13125550187", "kind": "reminder"}]
    return msgs, {"+13125550142", "+13125550187"}, {"+13125550187"}


# ---------------------------------------------------------------- inputs and report

def inputs(mode: str) -> dict:
    if mode == "mock":
        m, consent, stopped = texts()
        # loss comes in bursts: 60 ms lost between the two presses of "2", and two
        # single packets elsewhere
        return {"invite": INVITE, "attempts": attempts(), "texts": m,
                "consent": sorted(consent), "stopped": sorted(stopped),
                "lost": [3, 4, 5, 17, 26]}
    if mode == "fixture":
        return json.loads((FIXTURES / "telephony.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab (see the header)")


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    say = out.append
    say(f"telephony lab, mode={mode}; evidence class: simulated (synthetic signals)")
    say("")
    say("1. the invite (a fixture) and the answer")
    inv = parse_invite(data["invite"])
    ans = answer(inv)
    say(f"   caller {inv['from']}, attestation {inv['attest']} (the carrier vouches "
        "for the number)")
    say(f"   offered: {', '.join(inv['offer'])}; packets every {inv['ptime']} ms")
    say(f"   answer: {ans['codec']}, touch-tones as {ans['dtmf']}")
    if ans["nat"]:
        say(f"   warning: audio address {inv['address']} is private; without the "
            "border")
        say("   controller rewriting it, the caller hears nothing (one-way audio)")
    say("")
    say("2. narrowband: one syllable, a vowel then an \"s\"")
    x = voice()
    once = phone_path(x)
    twice = phone_path(once)
    say(f"   energy above 4 kHz: wideband {high_share(x) * 100:.0f}%, "
        f"after the phone path {high_share(once) * 100:.1f}%")
    ref = lowpass(x, 3800)
    say(f"   signal to noise against the band-limited voice: one pass "
        f"{snr_db(ref, once):.1f} dB,")
    say(f"   converted twice {snr_db(ref, twice):.1f} dB")
    say("")
    say(f"3. the jitter buffer ({N_PACKETS} packets, base delay {BASE_MS} ms)")
    delays = network()
    say(f"   {'buffer':>8}{'added delay':>14}{'late, lost':>13}")
    for b in BUFFERS_MS:
        say(f"   {str(b) + ' ms':>8}{str(b) + ' ms':>14}{late_share(delays, b) * 100:>12.1f}%")
    say("")
    say(f"4. touch-tones: {DIGITS} ({TONE_PACKETS * 20} ms tone, "
        f"{GAP_PACKETS * 20} ms gap)")
    pkts = tone_packets(DIGITS)
    lost = set(data["lost"])
    say(f"   in the audio, clean line          {detect(pkts)}")
    say(f"   in the audio, after G.711         {detect(g711(pkts))}")
    say(f"   in the audio, a 60 ms burst lost  {detect(lossy(pkts, lost)) or '(none)'}")
    say(f"   as events, the same packets lost  {events(DIGITS, lost)}")
    say("")
    say("5. the outbound gate: calls on the trunk")
    per_hour: dict[int, int] = {}
    spent, rows, burst = 0.0, [], {"allowed": 0, "refused": 0}
    for a in data["attempts"]:
        verdict = gate(a, per_hour.get(a["hour"], 0), spent)
        if verdict == "allowed":
            per_hour[a["hour"]] = per_hour.get(a["hour"], 0) + 1
            spent += LIMITS["cost_per_min"] * LIMITS["minutes"]
        if a["why"] == "a stolen credential":
            burst["allowed" if verdict == "allowed" else "refused"] += 1
        else:
            rows.append((a["why"], verdict))
    for why, verdict in rows:
        say(f"   {why:<20}{verdict}")
    say(f"   {'a stolen credential':<20}{burst['allowed']} of 40 placed, then "
        "refused: hourly limit")
    say("")
    say("6. texts from your numbers")
    consent, stopped = set(data["consent"]), set(data["stopped"])
    for m in data["texts"]:
        kind = SENDERS[m["from"]]["kind"]
        say(f"   {m['kind']:<13}{kind:<10}{may_text(m, consent, stopped)}")
    return "\n".join(out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("TELEPHONY_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"telephony_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "telephony.json").write_text(json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/telephony.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("TELEPHONY_LAB_MODE", "mock")))
    else:
        run_mode()
