"""Builders' Chapter 27 lab: deploy it.

One release, from its manifest to everyone's calls:

  1. the release manifest     every part that changes what callers hear, in
                              one record with one id, and what each
                              environment would really run
  2. shadow mode              the new release on a week of live calls, its
                              writes refused at the tool layer and counted,
                              against a flag each tool was trusted to check
  3. the evidence gate        every piece of evidence tied to the manifest
                              id, fresh, and passed; promotion only through it
  4. the canary               a small share of calls, stop rules written
                              first and split by language, and the rollback
  5. drain before swap        new calls meet the new release; calls already
                              in progress finish on the one they started on
  6. the emergency stop       a release doing harm: the unsafe action
                              refused on the calls in progress too, writes
                              in flight read back, callers moved to a person

Modes (select with DEPLOY_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Feed step 1 your own manifest and environment
           settings, and step 4 your canary's counts (evidence class: field).

  python3 deploy_lab.py                  run and print the report
  python3 deploy_lab.py --write-fixture  regenerate fixtures/
  python3 deploy_lab.py --check          compare with the frozen output

Evidence class: simulated. The releases, the evidence, the shadow week, the
canary's counts, and the calls in progress are stand-ins.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ------------------------------------------------- 1. the release manifest

PARTS = [  # part, release 31, release 32
    ["instructions (core)", "1.4", "1.4"],
    ["voice brief", "1.3", "1.3"],
    ["billing procedure", "2.1", "2.2"],
    ["visit procedure", "1.7", "1.7"],
    ["fixed lines", "3.0", "3.1"],
    ["knowledge", "k-118", "k-123"],
    ["policy rules", "p-44", "p-44"],
    ["turn-taking rules", "v2.4", "v2.4"],
    ["model", "m-12", "m-12"],
    ["recognizer", "r-2.8", "r-2.8"],
    ["voice", "B 4.1", "B 4.1"],
    ["tools", "t-19", "t-19"],
]

SETTINGS = {  # behavior settings, released with the parts
    "holding line after": "700 ms",
    "barge-in pause on voice": "100 ms",
    "voice speaking rate": "1.0",
}

ALLOWED = {"endpoint", "key reference", "region"}  # may differ by environment

ENVIRONMENTS = {
    "staging": {"voice speaking rate": "1.0", "endpoint": "stg",
                "key reference": "vault:stg/speech", "region": "east"},
    "production": {"voice speaking rate": "1.1", "endpoint": "prod",
                   "key reference": "vault:prod/speech", "region": "east"},
}


def manifest(parts: list[list], release: int, settings: dict) -> dict:
    """One record for everything that changes behavior. Its id is a hash of
    the contents, so two manifests with the same parts have the same id,
    whatever order they were written in."""
    col = 1 if release == 31 else 2
    body = {"parts": {p[0]: p[col] for p in parts}, "settings": settings}
    blob = json.dumps(body, sort_keys=True).encode()
    return {"release": release, "id": hashlib.sha256(blob).hexdigest()[:8],
            **body}


def drift(man: dict, env: dict) -> list[tuple[str, str, str]]:
    """Settings an environment would run that the manifest does not say.
    Only the allowed keys may differ between environments."""
    out = []
    for key, value in env.items():
        if key in ALLOWED:
            continue
        want = man["settings"].get(key)
        if value != want:
            out.append((key, value, want))
    return out


# ----------------------------------------------------------- 2. shadow

TOOLS = [  # name, kind, whether the tool itself checks the shadow flag
    ["lookup_account", "read", True],
    ["outage_status", "read", True],
    ["find_visit_slots", "read", True],
    ["book_visit", "write", True],
    ["cancel_visit", "write", True],
    ["change_address", "write", True],
    ["send_receipt", "write", False],   # another team's tool, added later
]

SHADOW_WEEK = {
    "calls": 612,
    "proposed": {"lookup_account": 598, "outage_status": 141,
                 "find_visit_slots": 92, "book_visit": 63, "cancel_visit": 9,
                 "change_address": 4, "send_receipt": 72},
    "live_writes": {"book_visit": 61, "cancel_visit": 9, "change_address": 4,
                    "send_receipt": 70},
    "to_review": 2,
}


def run_shadow(proposed: dict, at_tool_layer: bool) -> dict:
    """What happens to each proposed call from a shadow session. By a flag,
    each tool is trusted to hold back on its own and logs nothing; a tool
    that never checks the flag writes for real. At the tool layer, the
    gateway refuses every write from a shadow session and logs it."""
    out = {"read": {}, "reached": {}, "held": {}, "refused": {}}
    for name, kind, checks in TOOLS:
        n = proposed.get(name, 0)
        if kind == "read":
            out["read"][name] = n
        elif at_tool_layer:
            out["refused"][name] = n
        elif checks:
            out["held"][name] = n
        else:
            out["reached"][name] = n
    return out


# ------------------------------------------------------ 3. the evidence gate

MAX_AGE_DAYS = 7

EVIDENCE = [  # what, manifest (31 or 32), age in days, result, passed
    ["text: 200 scenarios", 32, 0, "200 of 200", True],
    ["audio: 5 runs of each", 32, 1, "996 of 1,000", True],
    ["phone: 40 test calls", 31, 6, "40 of 40", True],
    ["cross-chapter scenarios", 32, 0, "4 of 4", True],
    ["replay: 500 recorded calls", 32, 1, "0 regressions", True],
    ["shadow: 612 live calls", 32, 2, "0 writes out", True],
    ["sign-off: product owner", 32, 0, "signed", True],
]


def gate(evidence: list[list], man_id: str, ids: dict) -> list[tuple]:
    """Each piece of evidence counts only for the manifest it was produced
    on, only while it is fresh, and only if it passed."""
    rows = []
    for what, rel, age, result, passed in evidence:
        if ids[rel] != man_id:
            verdict = "another manifest"
        elif age > MAX_AGE_DAYS:
            verdict = "stale"
        elif not passed:
            verdict = "failed"
        else:
            verdict = "ok"
        rows.append((what, ids[rel], age, result, verdict))
    return rows


# -------------------------------------------------------- 4. the canary

CANARY = {
    "share": 5,
    "wait_p95": [736, 742],            # ms at the p95, release 31 / 32
    "false_commitments": [0, 0],
    "groups": [  # group, release 31 (k, n), release 32 (k, n)
        ["first language", [122, 2700], [4, 150]],
        ["second language", [43, 710], [7, 30]],
    ],
    "in_progress_on_32": 2,
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """The Wilson score interval for k events in n calls, in percent."""
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (
        1 + z * z / n)
    return 100 * max(0.0, centre - half), 100 * min(1.0, centre + half)


def judge(groups: list[list]) -> list[tuple]:
    """The stop rule for transfers after a repair: stop when release 32's
    95 percent interval lies wholly above release 31's rate, in any group
    or in all callers together."""
    rows = []
    all31 = [sum(g[1][0] for g in groups), sum(g[1][1] for g in groups)]
    all32 = [sum(g[2][0] for g in groups), sum(g[2][1] for g in groups)]
    for name, r31, r32 in [["all callers", all31, all32]] + groups:
        base = 100 * r31[0] / r31[1]
        lo, hi = wilson(*r32)
        rows.append((name, base, r31[1], r32[0], r32[1], lo, hi,
                     "STOP" if lo > base else "continue"))
    return rows


# ------------------------------------------------------ 5. drain before swap

SWAP_AT = 14 * 3600                    # 14:00:00
DRAIN_LIMIT_S = 30 * 60                # after this, a person takes the call
IN_PROGRESS = [35, 70, 95, 120, 160, 200, 240, 290, 330, 380, 420, 510, 600,
               680]                    # seconds each call has left


def clock(s: int) -> str:
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def swap(remaining: list[int], policy: str) -> dict:
    """Restarting the workers moves every call in progress to the new
    release mid-call. Draining sends new calls to the new release and lets
    each call in progress finish on the release it started on."""
    if policy == "restart":
        return {"changed_mid_call": len(remaining), "old_stops": SWAP_AT,
                "past_limit": 0}
    last = max(remaining)
    past = sum(r > DRAIN_LIMIT_S for r in remaining)
    return {"changed_mid_call": 0,
            "old_stops": SWAP_AT + min(last, DRAIN_LIMIT_S),
            "past_limit": past}


# ------------------------------------------------------- 6. the emergency stop

STOP = {  # release 34's policy rules lost the fee from the booking's terms
    "release": 34, "back_to": 33, "share": 25, "tool": "book_visit",
    "at": 16 * 3600 + 20 * 60,         # 16:20:00, found by a red line
    "calls": [  # seconds left, seconds until the booking's yes (-1: none),
                # a booking write in flight now, and if so whether it landed
        [420, 40, False, None], [300, 95, False, None],
        [600, 210, False, None], [240, 180, False, None],
        [180, -1, False, None], [90, -1, True, True],
        [510, -1, False, None], [360, -1, True, False],
        [150, -1, False, None],
    ],
}


def stop_paths(calls: list[list], path: str) -> dict:
    """What the calls already in progress on a harmful release meet. A drain
    lets each finish on it, so every call that reaches the booking's yes
    books without the fee. The emergency stop refuses the tool for that
    release at the gateway at once, reads back every write in flight from
    the scheduler instead of assuming it was cancelled, and moves each
    caller who reaches the booking to a person with the call's context.
    Neither path changes a call's release mid-call."""
    reach = [c for c in calls if 0 <= c[1] < c[0]]
    flight = [c for c in calls if c[2]]
    if path == "drain":
        return {"harm_after": len(reach), "moved": 0,
                "in_flight": len(flight), "landed": None,
                "changed_mid_call": 0}
    return {"harm_after": 0, "moved": len(reach),
            "in_flight": len(flight),
            "landed": sum(1 for c in flight if c[3]),
            "changed_mid_call": 0}


# ------------------------------------------------------------ inputs

def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"parts": PARTS, "settings": SETTINGS,
                "environments": ENVIRONMENTS, "shadow": SHADOW_WEEK,
                "evidence": EVIDENCE, "canary": CANARY,
                "in_progress": IN_PROGRESS, "stop": STOP}
    if mode == "fixture":
        return json.loads((FIXTURES / "deploy.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# -------------------------------------------------------------- report

def block(put, lead: str, text: str, width: int = 78) -> None:
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"deploy lab, mode={mode}; evidence class: simulated")
    put("")
    m31 = manifest(data["parts"], 31, data["settings"])
    m32 = manifest(data["parts"], 32, data["settings"])
    ids = {31: m31["id"], 32: m32["id"]}
    put("1. the release manifest: every part that changes what callers hear")
    put(f"   {'part':<22}{'release 31':<12}{'release 32':<12}")
    for part, a, b in data["parts"]:
        mark = "changed" if a != b else ""
        put(f"   {part:<22}{a:<12}{b:<12}{mark}".rstrip())
    changed = sum(a != b for _, a, b in data["parts"])
    put(f"   {'manifest id':<22}{m31['id']:<12}{m32['id']:<12}"
        f"{changed} parts changed")
    put("   what each environment would run, apart from endpoints, key")
    put("   references, and region:")
    for env, settings in data["environments"].items():
        diffs = drift(m32, settings)
        if not diffs:
            put(f"   {env:<12}matches {m32['id']}")
        for key, got, want in diffs:
            block(put, f"   {env:<12}", f"{key} {got}, the manifest says "
                  f"{want} (a hand edit in the provider's console)")
    put("   promotion refused until production matches the manifest")
    put("")
    sh = data["shadow"]
    flag = run_shadow(sh["proposed"], at_tool_layer=False)
    layer = run_shadow(sh["proposed"], at_tool_layer=True)
    put(f"2. shadow mode: release 32 hears a week of live calls "
        f"({sh['calls']}), speaks to")
    put("   nobody")
    put(f"   {'tool':<18}{'kind':<7}{'by a flag each tool checks':<28}"
        "at the tool layer")
    for name, kind, _ in TOOLS:
        n = sh["proposed"].get(name, 0)
        if kind == "read":
            a = b = f"read {n}"
        else:
            a = (f"SENT {n} to callers" if name in flag["reached"]
                 else "held back, not logged")
            b = f"refused, logged {n}"
        put(f"   {name:<18}{kind:<7}{a:<28}{b}")
    reached = sum(flag["reached"].values())
    put(f"   writes that reached real systems: by a flag {reached}, at the "
        f"tool layer {sum(layer['reached'].values())}")
    put("   what release 32 would have written, against release 31's real "
        "writes:")
    pairs = [f"{t} {layer['refused'][t]} / {sh['live_writes'][t]}"
             for t in layer["refused"]]
    for i in range(0, len(pairs), 2):
        put("   " + ", ".join(pairs[i:i + 2]))
    block(put, "   ", f"{sh['to_review']} calls to review, where release 32 "
          "booked and release 31 handed the caller to a person")
    put("")
    rows = gate(data["evidence"], m32["id"], ids)
    put(f"3. the evidence gate for manifest {m32['id']} (release 32)")
    put(f"   {'evidence':<29}{'manifest':<10}{'age':<5}{'result':<15}"
        "verdict")
    for what, mid, age, result, verdict in rows:
        put(f"   {what:<29}{mid:<10}{str(age) + ' d':<5}{result:<15}"
            f"{verdict}")
    bad = [r for r in rows if r[4] != "ok"]
    put(f"   gate: closed, {len(bad)} of {len(rows)} not valid for "
        f"{m32['id']}")
    rerun = [[w, 32 if r == 31 else r, 0 if r == 31 else a, res, p]
             for w, r, a, res, p in data["evidence"]]
    ok = all(r[4] == "ok" for r in gate(rerun, m32["id"], ids))
    put(f"   after the phone tests rerun on {m32['id']} (40 of 40): gate "
        f"{'open' if ok else 'closed'}")
    put("")
    c = data["canary"]
    put(f"4. the canary: release 32 on {c['share']}% of evening calls for a "
        "week")
    block(put, "   ", "stop rules, written first: the wait at the p95 over "
          "800 ms; any false commitment; transfers after a repair above "
          "release 31's rate, where release 32's 95% interval sits wholly "
          "above it")
    w31, w32 = c["wait_p95"]
    f31, f32 = c["false_commitments"]
    for label, text in (
            ("the wait at the p95",
             f"release 31 {w31} ms, release 32 {w32} ms"),
            ("false commitments", f"release 31 {f31}, release 32 {f32}")):
        put(f"   {label:<22}{text:<39}continue")
    put("   transfers after a repair")
    put(f"   {'group':<17}{'release 31':<16}{'release 32':<27}verdict")
    for name, base, n31, k, n, lo, hi, verdict in judge(c["groups"]):
        r32 = f"{k} of {n}: {lo:.1f} to {hi:.1f}%"
        put(f"   {name:<17}{f'{base:.1f}% of {n31:,}':<16}{r32:<27}"
            f"{verdict}")
    block(put, "   ", "rollback: release 32's share set to 0; new calls meet "
          f"release 31 at once; the {c['in_progress_on_32']} calls in "
          "progress on release 32 finish on it")
    put("")
    rem = data["in_progress"]
    put(f"5. drain before swap: release 31 to 33 at {clock(SWAP_AT)}, "
        f"{len(rem)} calls in progress")
    r = swap(rem, "restart")
    block(put, f"   {'restart the workers':<22}", f"{r['changed_mid_call']} "
          "calls resume on release 33 mid-call, their state written by "
          "release 31")
    d = swap(rem, "drain")
    put(f"   {'drain':<22}new calls meet release 33 from {clock(SWAP_AT)}")
    put(f"   {'':<22}the {len(rem)} finish on release 31; the last at "
        f"{clock(d['old_stops'])}")
    put(f"   {'':<22}release 31's workers stop at {clock(d['old_stops'])}")
    put(f"   calls changed under a live caller: restart "
        f"{r['changed_mid_call']}, drain {d['changed_mid_call']}")
    put(f"   calls past the drain limit ({DRAIN_LIMIT_S // 60} min, then a "
        f"person): {d['past_limit']}")
    put("")
    st = data["stop"]
    dr, em = stop_paths(st["calls"], "drain"), stop_paths(st["calls"], "stop")
    put(f"6. the emergency stop: release {st['release']} books visits whose "
        "yes missed the fee")
    put(f"   found at {clock(st['at'])} on its {st['share']}% canary; "
        f"{len(st['calls'])} calls in progress on release {st['release']}")
    put(f"   {'':<32}{'drain':<20}emergency stop")
    rows = [
        ("new calls", f"release {st['back_to']}", f"release {st['back_to']}"),
        (f"{st['tool']}, release {st['release']}", "open",
         "refused at the gateway"),
        ("more bookings without the fee", str(dr["harm_after"]),
         str(em["harm_after"])),
        ("bookings in flight", f"{dr['in_flight']}, as they land",
         f"{em['in_flight']}, read back"),
        ("callers moved to a person", str(dr["moved"]),
         f"{em['moved']}, at the booking"),
        ("calls whose release changed", str(dr["changed_mid_call"]),
         str(em["changed_mid_call"])),
    ]
    for label, a, b in rows:
        put(f"   {label:<32}{a:<20}{b}")
    landed, open_ = em["landed"], em["in_flight"] - em["landed"]
    block(put, "   ", f"read back: {landed} landed, so a person calls that "
          f"caller about the fee; {open_} did not, so the person on the call "
          "books it with the fee read")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("DEPLOY_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"deploy_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "deploy.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/deploy.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("DEPLOY_LAB_MODE", "mock")))
    else:
        run_mode()
