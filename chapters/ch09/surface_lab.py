"""Builders' Chapter 9 lab: where the voice lives, on the client side.

Six steps:

  1. tokens          a signed-in app session becomes a short-lived token that
                     locks the agent; what the server refuses; a scan of two
                     app bundles for provider keys
  2. one stream      one agent-state stream drives the voice and the screen;
                     the card shows exactly the facts the voice speaks
  3. tap and talk    a tap and a spoken yes reach one confirmation; a stale
                     card is refused; a double tap books once
  4. old clients     three app versions against the server's contract, with
                     voice on and with the kill switch pressed
  5. on the device   voice-to-voice delay by device, against what the server
                     measures about itself
  6. typing          a typed question and a spoken one reach the same agent

Modes (select with SURFACE_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. The companion app's web client is the live
           version of steps 1 to 3 and 6.

  python3 surface_lab.py                  run and print the report
  python3 surface_lab.py --write-fixture  regenerate fixtures/ from the data
  python3 surface_lab.py --check          compare with the frozen output

Evidence class of every number printed: simulated. Device delays are
stand-in values from published ranges; measure your own devices.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

# ---------------------------------------------------------------- 1. tokens

SERVER_SECRET = b"stand-in signing key, kept on the server"
START_WITHIN_S = 60             # a token must open a session within a minute
LOCKED = ("agent", "instructions", "tools")


def mint(user: dict, now: int) -> str:
    """The app's backend, after its own sign-in check, mints a token that
    names the user and locks what the session may do."""
    claims = {"sub": user["account"], "via": "app sign-in",
              "start_by": now + START_WITHIN_S,
              "agent": "service-line", "instructions": "2026-09-29",
              "tools": ["read_bill", "book_visit"]}
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()
    sig = hmac.new(SERVER_SECRET, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def open_session(token: str, now: int, asks: dict | None = None) -> str:
    """The media edge checks the token before the agent hears a word."""
    body, _, sig = token.partition(".")
    good = hmac.new(SERVER_SECRET, body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, good):
        return "refused: the signature does not match"
    claims = json.loads(base64.urlsafe_b64decode(body))
    if now > claims["start_by"]:
        return "refused: expired; the app gets a new token"
    for k, v in (asks or {}).items():
        if k in LOCKED and v != claims[k]:
            return f"refused: the token locks the {k}"
    return f"accepted: account {claims['sub']} ({claims['via']})"


def tamper(token: str, field: str, value) -> str:
    body, _, sig = token.partition(".")
    claims = json.loads(base64.urlsafe_b64decode(body))
    claims[field] = value
    return base64.urlsafe_b64encode(json.dumps(claims).encode()).decode() \
        + "." + sig


KEY_PATTERN = re.compile(r"\b(sk|ek|AIza)[-_A-Za-z0-9]{16,}")


def scan(bundle: dict[str, str]) -> list[str]:
    """Anything inside an app can be copied: look for provider keys."""
    return [path for path, text in sorted(bundle.items())
            if KEY_PATTERN.search(text)]


# ---------------------------------------------------------------- 2. stream

# The agent core's events, and the state the client shows for each.
SHOWS = {"caller speaking": "listening", "end of turn": "thinking",
         "tool started": "working", "line played": "speaking",
         "offer": "awaiting approval", "confirmed": "working",
         "committed": "done", "failed": "failed",
         "connection lost": "reconnecting", "connection back": "listening"}


def facts(text: str) -> set[str]:
    """The facts a line or a card carries: amounts, days, times, fees."""
    return set(re.findall(r"\$\d+(?:\.\d\d)?|\b(?:Mon|Tues|Wednes|Thurs|"
                          r"Fri|Satur|Sun)day\b|\b\d{1,2}:\d\d\b", text))


def screen(events: list[dict]) -> list[tuple[str, str, str]]:
    """One stream in, the screen out: state and card, event by event."""
    rows, card = [], ""
    for e in events:
        card = e.get("card", card)
        rows.append((e["kind"], SHOWS[e["kind"]], e.get("card", "")))
    return rows


def agree(events: list[dict]) -> tuple[int, int]:
    """Facts spoken that the card shows, and facts shown never spoken."""
    spoken = set().union(*(facts(e.get("says", "")) for e in events))
    shown = set().union(*(facts(e.get("card", "")) for e in events))
    return len(spoken & shown), len(shown - spoken)


# ---------------------------------------------------------------- 3. confirm


def confirm(offer: dict, via: str, card_version: int, ops: dict) -> str:
    """A tap and a spoken yes are the same act: they confirm one offer, by
    its version. The first yes mints the offer's operation id, and a
    repeat finds it, so nothing is booked twice (Chapter 17)."""
    if card_version != offer["version"]:
        return "refused: stale card; the screen refreshes"
    key = (offer["id"], offer["version"])
    if key in ops:
        return f"one booking: {ops[key]} (a repeat)"
    n = len(ops) + 1
    ops[key] = "op-" + hashlib.sha256(f"yes {n}".encode()).hexdigest()[:4]
    return f"booked {ops[key]}, by {via}"


# ---------------------------------------------------------------- 4. clients

CONTRACT_MIN, CONTRACT_NOW = 2, 3


def session_for(client: dict, voice_on: bool) -> str:
    """The server decides; an old client cannot ignore what it refuses."""
    if client["contract"] < CONTRACT_MIN:
        return "refused: update the app"
    if not voice_on:
        if client["contract"] >= 3:
            return "voice stops; typing offered"
        return "session closed by the server"
    if client["contract"] < CONTRACT_NOW:
        return "voice; confirm by voice only"
    return "full: states, cards, tap"


# ---------------------------------------------------------------- 5. device

SERVER_SPANS_MS = 220 + 40 + 170 + 85 + 10     # Chapter 6's five spans
PARTS = ("network", "jitter buffer", "device audio")


def voice_to_voice(d: dict) -> int:
    return SERVER_SPANS_MS + sum(d[p] for p in PARTS)


# ---------------------------------------------------------------- 6. typing


def turn(text: str, via: str) -> tuple[str, str, str]:
    """Speech and typing arrive as the same contract event, so the same
    agent, knowledge, and rules answer both."""
    event = {"kind": "caller text", "text": text.lower().strip(" ?"),
             "via": via}
    tool = "read_bill" if "bill" in event["text"] else "none"
    return event["text"], tool, "allowed"


# ---------------------------------------------------------------- inputs

BUNDLES = {
    "prototype": {"config/speech.json":
                  '{"provider": "realtime", "api_key": '
                  '"sk-live-8f2c1d9e7a6b5c4d3e2f"}',
                  "js/app.js": "connect(provider, config.api_key)"},
    "release": {"config/speech.json": '{"session_url": "/voice/token"}',
                "js/app.js": "connect(edge, await fetchToken())"}}

EVENTS = [
    {"kind": "caller speaking"},
    {"kind": "end of turn"},
    {"kind": "tool started", "card": "reading your bill"},
    {"kind": "line played", "says": "Your September bill is $184.20. "
     "August was $91.60. September includes an estimated reading from "
     "your new meter.", "card": "Sep $184.20, Aug $91.60, estimated"},
    {"kind": "connection lost"},
    {"kind": "connection back"},
    {"kind": "offer", "says": "A technician can check the meter on "
     "Tuesday at 9:00. There's a $40 call-out fee. Shall I book it?",
     "card": "Tuesday 9:00, fee $40"},
    {"kind": "confirmed", "card": "booking"},
    {"kind": "committed", "says": "Booked for Tuesday at 9:00.",
     "card": "booked: Tuesday 9:00"}]

CLIENTS = [{"version": "3.4", "contract": 3},
           {"version": "3.1", "contract": 2},
           {"version": "2.9", "contract": 1}]

DEVICES = [
    {"name": "laptop, Wi-Fi, built-in speakers", "network": 60,
     "jitter buffer": 40, "device audio": 30},
    {"name": "phone, mobile network, earpiece", "network": 120,
     "jitter buffer": 40, "device audio": 20},
    {"name": "phone, mobile, Bluetooth (call)", "network": 120,
     "jitter buffer": 40, "device audio": 60},
    {"name": "phone, mobile, Bluetooth (media)", "network": 120,
     "jitter buffer": 40, "device audio": 170}]


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"user": {"account": "5108"}, "now": 1_000_000,
                "bundles": BUNDLES, "events": EVENTS, "clients": CLIENTS,
                "devices": DEVICES,
                "offer": {"id": "offer-7", "account": "5108",
                          "slot": "tue-0900", "version": 2},
                "question": "Why is my bill so high?"}
    if mode == "fixture":
        return json.loads((FIXTURES / "surface.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ---------------------------------------------------------------- report


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    say = out.append
    say(f"surface lab, mode={mode}; evidence class: simulated")
    say("")
    say("1. tokens: identity from the sign-in, the agent locked")
    now = data["now"]
    tok = mint(data["user"], now)
    cases = [("the signed-in app, at once", tok, now, None),
             ("the same token, 90 s later", tok, now + 90, None),
             ("claims edited in the app", tamper(tok, "sub", "2231"), now,
              None),
             ("the app adds a tool", tok, now,
              {"tools": ["read_bill", "book_visit", "refund"]})]
    for label, t, at, asks in cases:
        say(f"   {label:<28}{open_session(t, at, asks)}")
    for name, bundle in data["bundles"].items():
        found = scan(bundle)
        say(f"   {name + ' bundle':<28}provider keys found: {len(found)}"
            + (f" ({found[0]})" if found else ""))
    say("")
    say("2. one state stream, two outputs")
    say(f"   {'agent event':<18}{'screen state':<20}card")
    for kind, state, card in screen(data["events"]):
        say(f"   {kind:<18}{state:<20}{card}")
    both, extra = agree(data["events"])
    say(f"   facts spoken and shown: {both}; shown but never spoken: {extra}")
    say("")
    say("3. a tap and a yes reach one confirmation")
    offer, ops = data["offer"], {}
    for label, via, version in (("tap on the card", "tap", 2),
                                ("then a spoken yes", "voice", 2),
                                ("tap on a stale card", "tap", 1)):
        say(f"   {label:<22}{confirm(offer, via, version, ops)}")
    say("")
    say("4. old app versions, and the kill switch")
    say(f"   {'app':<6}{'contract':<10}{'voice on':<31}kill switch pressed")
    for c in data["clients"]:
        say(f"   {c['version']:<6}{'v' + str(c['contract']):<10}"
            f"{session_for(c, True):<31}{session_for(c, False)}")
    say("")
    say("5. voice to voice, measured on the device (stand-in values)")
    say(f"   {'where':<40}{'ms':>5}")
    say(f"   {'the server, its own spans':<40}{SERVER_SPANS_MS:>5}")
    for d in data["devices"]:
        ms = voice_to_voice(d)
        say(f"   {d['name']:<40}{ms:>5}" + ("  over the 800 ms wall"
                                           if ms > 800 else ""))
    say("")
    say("6. another way through: spoken and typed, one agent")
    for via in ("spoken", "typed"):
        text, tool, rule = turn(data["question"], via)
        say(f"   {via:<8}\"{text}\"  tool {tool}, {rule}")
    return "\n".join(line.rstrip() for line in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("SURFACE_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"surface_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "surface.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/surface.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("SURFACE_LAB_MODE", "mock")))
    else:
        run_mode()
