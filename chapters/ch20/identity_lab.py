"""Builders' Chapter 20 lab: systems of record, identity, and memory.

Four steps:

  1. lookup by number      the calling number finds candidate accounts,
                           never a verified caller
  2. the proof ladder      the level each action needs, what each method
                           proves, and a step-up before an address change
  3. the identity chain    a signed verification statement, checked by
                           the systems of record on every request
  4. memory                five tests of what an agent remembers about a
                           returning caller, naive and designed

Modes (select with IDENTITY_LAB_MODE or run_mode(mode=...)):
  mock     the records are built in this file (default)
  fixture  the same records loaded from fixtures/ (committed; same schema)
  live     not in this lab. Point lookup() at a read-only copy of your
           customer records, and check() at your systems' own checks.

  python3 identity_lab.py                  run and print the report
  python3 identity_lab.py --write-fixture  regenerate fixtures/
  python3 identity_lab.py --check          compare with the frozen output

Evidence class: none for the checks, which apply rules to stand-in
records; the step-up's seconds are stand-ins. The signing key is a
stand-in as well: a real key lives in a key service, never in code.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ------------------------------------------------ 1. lookup by number

def lookup(number: str, records: dict) -> list[str]:
    """Accounts that list the calling number: candidates, not proof."""
    return sorted(a for a, r in records.items() if number in r["phones"])


# ------------------------------------------------ 2. the proof ladder

LADDER = ["none", "pin", "pin + code", "a person"]
NEEDS = {  # the level each action needs (the compliance lead's ladder)
    "outage_status": "none", "office_hours": "none",
    "read_bill": "pin", "book_visit": "pin", "meter_reading": "pin",
    "change_address": "pin + code", "payment_plan": "pin + code",
    "card_payment": "a person", "close_account": "a person"}
GRANTS = {  # what each method proves on its own
    "number match": "none", "caller-ID attestation A": "none",
    "knowledge question": "none", "voiceprint": "none",
    "account and PIN": "pin", "app sign-in": "pin",
    "code to the phone on the account": "pin + code"}


def allowed(action: str, level: str) -> bool:
    need = NEEDS[action]
    if need == "a person":
        return False
    return LADDER.index(level) >= LADDER.index(need)


def step_up(level: str, method: str) -> str:
    """A method raises the level only as far as it proves. A code to the
    phone proves the phone, so it counts only on top of a PIN."""
    if method == "code to the phone on the account" and level != "pin":
        return level
    return max(level, GRANTS[method], key=LADDER.index)


# ------------------------------------------------ 3. the identity chain

KEY = b"stand-in key; a real one lives in a key service"
MINUTES = 15                        # how long a verification lasts


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(payload: str) -> str:
    return b64(hmac.new(KEY, payload.encode(), hashlib.sha256).digest())


def mint(subject: str, level: str, methods: list[str],
         audience: list[str], issued: int, jti: str,
         actor: str = "service-line-agent") -> str:
    """Who was verified, how, for which systems, until when. Times are
    minutes after midnight on the stand-in clock."""
    body = {"sub": subject, "act": actor, "level": level, "amr": methods,
            "aud": audience, "iat": issued, "exp": issued + MINUTES,
            "jti": jti}
    payload = b64(json.dumps(body, sort_keys=True).encode())
    return f"{payload}.{sign(payload)}"


def check(token: str, system: str, action: str, account: str,
          now: int) -> tuple[bool, str]:
    """What a system of record asks of every request (INT-7)."""
    payload, _, signature = token.partition(".")
    if not hmac.compare_digest(signature, sign(payload)):
        return False, "refused: the signature does not match"
    s = json.loads(unb64(payload))
    if system not in s["aud"]:
        return False, f"refused: not issued for {system}"
    if now >= s["exp"]:
        return False, f"refused: expired at {clock(s['exp'])}"
    if account != s["sub"]:
        return False, f"refused: the statement is for {s['sub']}"
    if not allowed(action, s["level"]):
        return False, f"refused: {action} needs {NEEDS[action]}"
    return True, (f"allowed; audit: {action} {account}, caller "
                  f"{s['sub']}, actor {s['act']}, statement {s['jti']}")


def edited(token: str, **changes) -> str:
    """A statement someone changed after it was signed."""
    payload, _, signature = token.partition(".")
    body = dict(json.loads(unb64(payload)), **changes)
    return f"{b64(json.dumps(body, sort_keys=True).encode())}.{signature}"


def clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ------------------------------------------------ 4. memory

NAIVE = {"key": "number", "early": True, "expires": False,
         "corrects": False, "consent": False, "derived": False}
DESIGNED = {"key": "account", "early": False, "expires": True,
            "corrects": True, "consent": True, "derived": True}


def recall(m: dict, items: list[dict], verified: bool,
           today: int) -> list[dict]:
    """What the agent may use on this call, before or after verifying."""
    if not verified and not m["early"]:
        return []
    live = [i for i in items if not (m["expires"] and today > i["until"])]
    if m["corrects"]:
        latest = {}
        for i in live:                      # a correction replaces
            latest[i["slot"]] = i
        live = list(latest.values())
    return live


def forget(m: dict, items: list[dict], summaries: list[str],
           slot: str | None = None) -> tuple[list[dict], list[str]]:
    """The caller asks the agent to forget one thing, or everything."""
    if not m["consent"] and slot is None:
        return items, summaries             # a naive memory ignores it
    keep = [i for i in items if slot is not None and i["slot"] != slot]
    if m["derived"]:                        # summaries go with the facts
        gone = {i["text"] for i in items} - {i["text"] for i in keep}
        summaries = [s for s in summaries
                     if not any(g in s for g in gone)]
    return keep, summaries


def memory_tests(m: dict, data: dict) -> list[tuple[str, str, bool]]:
    """Five tests from the chapter, each with what the agent would do."""
    d = data["memory"]
    out = []
    # 1. the wrong person: the son calls from the household landline
    items = d["household"]
    said = recall(m, items, verified=False, today=d["today"])
    out.append(("the wrong person",
                "reads her visit to him" if said else "the opening only",
                not said))
    # 2. a stale preference
    said = recall(m, d["stale"], verified=True, today=d["today"])
    age = (d["today"] - d["stale"][0]["said"]) // 30
    out.append(("a stale preference",
                f"used, {age} months old" if said else "expired: not used",
                not said))
    # 3. a corrected fact
    said = recall(m, d["corrected"], verified=True, today=d["today"])
    phones = [i["text"] for i in said]
    out.append(("a corrected fact", " and ".join(phones),
                phones == [d["corrected"][-1]["text"]]))
    # 4. consent withdrawn
    items, _ = forget(m, d["preferences"], [])
    said = recall(m, items, verified=True, today=d["today"])
    out.append(("consent withdrawn",
                "still used" if said else "deleted, logged", not said))
    # 5. deletion of one fact, from the facts and their summaries
    gone = next(i["text"] for i in d["preferences"]
                if i["slot"] == "contact")
    items, summaries = forget(m, d["preferences"], d["summaries"],
                              slot="contact")
    left = [s for s in summaries if gone in s]
    out.append(("deletion", "a summary still holds it" if left
                else "gone, summaries too", not left))
    return out


# ---------------------------------------------------------------- data

RECORDS = {  # stand-in customer records; numbers are fictional 555 01xx
    "2231": {"premises": "14 Alder Road", "phones": ["555 0131"]},
    "4012": {"premises": "22 Alder Road", "phones": ["555 0107"]},
    "6120": {"premises": "9 Ashby Close", "phones": ["555 0158"]},
    "6127": {"premises": "Flat 2, 1260 Kestrel Way",
             "phones": ["555 0158"]},
    "6133": {"premises": "Flat 5, 1260 Kestrel Way",
             "phones": ["555 0158"]}}
CALLS = [  # calling number, attestation
    ("555 0131", "A"), ("555 0158", "A"), ("555 0107", "B"),
    ("555 0199", "none")]
STEP_UP = {"account": "2231", "code_seconds": 45}
REQUESTS = [  # minute, system, action, account, the statement used
    (1206, "billing", "read_bill", "6120", "plain"),
    (1206, "billing", "read_bill", "6127", "plain"),
    (1207, "billing", "change_address", "6120", "plain"),
    (1208, "scheduling", "book_visit", "6120", "plain"),
    (1208, "payments", "read_bill", "6120", "plain"),
    (1209, "billing", "change_address", "6120", "edited"),
    (1221, "billing", "read_bill", "6120", "plain")]
MEMORY = {
    "today": 640,                           # day number, stand-in
    "household": [{"slot": "visit", "until": 700,
                   "text": "Your visit is Tuesday at nine."}],
    "stale": [{"slot": "contact time", "until": 580,
               "text": "call after six", "said": 215}],
    "corrected": [{"slot": "mobile", "until": 1000, "text": "555 0131"},
                  {"slot": "mobile", "until": 1000, "text": "555 0132"}],
    "preferences": [{"slot": "contact", "until": 1000,
                     "text": "a text, not a call"},
                    {"slot": "language", "until": 1000,
                     "text": "the second language"}],
    "summaries": ["Prefers a text, not a call; asked twice about fees.",
                  "Visit booked for Tuesday at nine."]}


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"records": RECORDS, "calls": CALLS, "step_up": STEP_UP,
                "requests": REQUESTS, "memory": MEMORY}
    if mode == "fixture":
        return json.loads((FIXTURES / "identity.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# -------------------------------------------------------------- report

def block(put, lead: str, text: str, width: int = 78) -> None:
    """Print text after a lead, wrapped at the page width and aligned."""
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"identity lab, mode={mode}; checks on stand-in records")
    put("")
    put("1. lookup by number: a candidate, never proof")
    put(f"   {'number':<10}{'caller ID':<11}{'accounts':<20}the agent may")
    for number, attest in data["calls"]:
        found = lookup(number, data["records"])
        may = ("ask for the account" if not found else
               f"ask for {found[0]}'s PIN" if len(found) == 1 else
               "ask which property first")
        put(f"   {number:<10}{attest:<11}"
            f"{', '.join(found) or '(none)':<20}{may}")
    put("   account data spoken before verification: none")
    put("")
    put("2. the proof ladder: the level each action needs")
    for level in LADDER:
        acts = [a for a, n in NEEDS.items() if n == level]
        block(put, f"   {level:<12}", ", ".join(acts))
    put("   what each method proves on its own")
    for method, level in GRANTS.items():
        note = "selects, never proves" if level == "none" else level
        put(f"   {method:<36}{note}")
    su = data["step_up"]
    put(f"   a step-up: account {su['account']} asks to change the billing "
        "address")
    level = step_up("none", "account and PIN")
    put(f"   {'verified by account and PIN':<36}level {level}")
    put(f"   {'change_address':<36}"
        f"{'allowed' if allowed('change_address', level) else 'refused'}")
    level = step_up(level, "code to the phone on the account")
    put(f"   {'code to the phone on the account':<36}level {level} "
        f"({su['code_seconds']} s, stand-in)")
    put(f"   {'change_address':<36}"
        f"{'allowed' if allowed('change_address', level) else 'refused'}")
    put("")
    put("3. the identity chain: one signed statement, checked on every "
        "request")
    token = mint("6120", "pin", ["pwd"], ["billing", "scheduling"],
                 issued=1205, jti="v-6120-1")
    block(put, "   ", "the statement: caller 6120, actor "
          "service-line-agent, level pin, for billing and scheduling, "
          "from 20:05 to 20:20 (signed with the stand-in key)")
    for minute, system, action, account, kind in data["requests"]:
        t = token if kind == "plain" else edited(token, level="pin + code")
        _, why = check(t, system, action, account, minute)
        note = " (level edited to pin + code)" if kind == "edited" else ""
        put(f"   {clock(minute)}  {system:<11}{action} {account}{note}")
        block(put, "          ", why)
    fix = mint("6127", "pin", ["pwd"], ["billing"], issued=551,
               jti="v-6127-1")
    _, why = check(fix, "billing", "read_bill", "6127", 552)
    put("   after the fix, on his next call: \"Which property is it?\", then "
        "6127's PIN")
    put(f"   {clock(552)}  billing    read_bill 6127")
    block(put, "          ", why)
    put("")
    put("4. memory: five tests, a naive memory against a designed one")
    put(f"   {'test':<20}{'naive':<28}designed")
    naive = memory_tests(NAIVE, data)
    designed = memory_tests(DESIGNED, data)
    for (name, n_said, _), (_, d_said, _) in zip(naive, designed):
        put(f"   {name:<20}{n_said:<28}{d_said}")
    put(f"   {'passed':<20}{sum(p for *_, p in naive)} of 5"
        f"{'':<22}{sum(p for *_, p in designed)} of 5")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("IDENTITY_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"identity_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "identity.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/identity.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("IDENTITY_LAB_MODE", "mock")))
    else:
        run_mode()
