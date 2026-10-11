"""Builders' Chapter 16 lab: instructions and knowledge on the Service Line.

Six steps:

  1. the SOP, compiled   the meter-fault procedure (Chapter 5) as structured
                         steps with preconditions and tools, and one step's
                         instruction as the model receives it
  2. evidence first      one question, retrieved naively and then with
                         access filters, validity, and precedence
  3. rendered for the ear  the settled answer in two sentences, with its
                         material exception and its source ids
  4. freshness           the same question the day after the waiver ends
  5. abstaining          questions the evidence does not cover
  6. a long call         the context by turn 40: the whole history, or the
                         last turns and a summary beside the state object

Modes (select with KNOWLEDGE_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Put your own knowledge items, owners, and end
           dates into the fixture's schema, and run your own questions
           (evidence class: recorded replay if the questions are real).

  python3 knowledge_lab.py                  run and print the report
  python3 knowledge_lab.py --write-fixture  regenerate fixtures/
  python3 knowledge_lab.py --check          compare with the frozen output

Evidence class of every number printed: simulated. The items, accounts,
and questions are stand-ins shaped like the Service Line's; the retriever
is a word-overlap stand-in, not a search engine.
"""
from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

STOP = {"a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "my",
        "is", "are", "be", "will", "i", "you", "your", "can", "do", "it",
        "was", "were", "by", "with", "at", "any", "if", "their", "this"}


# ------------------------------------------------ 1. the SOP, compiled


def instruction(step: dict) -> str:
    """One compiled step, as the model receives it on that step."""
    needs = ", ".join(step["needs"]) or "nothing"
    tools = ", ".join(step["tools"]) or "none"
    return (f"Step {step['id']} ({step['block']}). {step['say']} "
            f"Tools: {tools}. The policy layer checks first: {needs}.")


# --------------------------------------------------- 2. evidence first


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in STOP}


def search(question: str, items: list[dict]) -> list[dict]:
    """A stand-in retriever: rank items by shared words, best first."""
    q = words(question)
    scored = [(len(q & words(it["text"])), it) for it in items]
    return [it for n, it in sorted(scored, key=lambda s: -s[0]) if n > 0]


def allowed(item: dict, caller: str) -> bool:
    """The access filter runs before ranking: public items, and this
    caller's own records, reached by a lookup on the verified account."""
    return item["audience"] in ("public", caller)


def valid(item: dict, on: date, items: list[dict] = ()) -> str | None:
    """Why an item may not be spoken on a date, or None. An item derived
    from another lives no longer than its source (lineage)."""
    if not item["owner"]:
        return "no owner"
    if item["from"] and on < date.fromisoformat(item["from"]):
        return "not started"
    if item["to"] and on > date.fromisoformat(item["to"]):
        return "ended " + date.fromisoformat(item["to"]).strftime("%-d %B")
    source = next((it for it in items if it["id"] == item.get("source")),
                  None)
    if source and valid(source, on):
        return f"its source, {source['id']}, " + valid(source, on)
    return None


def settle(question: str, items: list[dict], caller: str,
           on: date) -> dict:
    """Evidence first: filter by access, drop what may not be spoken, and
    let the highest-ranked policy decide; flag the sources it overrules."""
    found = search(question, items)
    usable = [it for it in found if allowed(it, caller)
              and valid(it, on, items) is None]
    sources = [it for it in usable if it["rank"]]
    topic = sources[0]["topic"] if sources else None   # the best match's
    same = sorted((it for it in sources if it["topic"] == topic),
                  key=lambda it: it["rank"])
    winner = same[0] if same else None
    flagged = [it for it in found if allowed(it, caller) and it["rank"]
               and it is not winner and it["topic"] == topic]
    record = next((it for it in usable if it["audience"] == caller), None)
    return {"found": found, "winner": winner, "record": record,
            "flagged": flagged}


# ------------------------------------------- 3. rendered for the ear

NUMBER = {1: "one", 2: "two", 3: "three"}


def render(s: dict) -> str:
    """Settle the facts, then say them in one breath: at most two
    sentences, the material exception kept."""
    w, rec = s["winner"], s["record"]
    if w is None:
        return ""
    if w["id"] == "memo-114" and rec:
        due = rec["late_fees_in_storm"]
        can = min(due, w["terms"]["fees"])
        if due > can:
            return (f"The storm waiver takes off one twelve-dollar late fee, "
                    f"so {NUMBER[can]} of your {NUMBER[due]} fees can come "
                    "off. Shall I do that now?")
        return ("The storm waiver takes off your twelve-dollar late fee. "
                "Shall I do that now?")
    return w["spoken"]


def checks(line: str, terms: list[str]) -> dict:
    sentences = [x for x in re.split(r"(?<=[.?!])\s+", line) if x]
    return {"sentences": len(sentences),
            "longest": max(len(x.split()) for x in sentences),
            "kept": [t for t in terms if t in line],
            "lost": [t for t in terms if t not in line]}


# --------------------------------------------------------- 4. freshness


def after_the_end(s: dict, items: list[dict], on: date) -> str:
    memo = next(it for it in items if it["id"] == "memo-114")
    if valid(memo, on, items):
        return ("The storm waiver ended on 30 September, so the late fees "
                "stand. I can set up a payment plan if that helps.")
    return render(s)


# -------------------------------------------------------- 5. abstaining


def coverage(question: str, item: dict | None) -> float:
    """Share of the question's content words the evidence speaks to."""
    q = words(question)
    return len(q & words(item["text"])) / len(q) if item else 0.0


def answer_or_abstain(question: str, items: list[dict], caller: str,
                      on: date, floor: float) -> str:
    s = settle(question, items, caller, on)
    best = s["winner"] or next(iter(
        it for it in s["found"] if allowed(it, caller)
        and valid(it, on, items) is None), None)
    if coverage(question, best) < floor:
        return "abstain"
    return best["id"]


# ------------------------------------------------------- 6. a long call


def context_tokens(turns: int, per_turn: int, keep: int,
                   summary: int) -> tuple[int, int]:
    """Tokens of history at a turn: all of it, or the last few turns
    plus a summary of the rest. The state object holds the facts."""
    whole = turns * per_turn
    kept = min(turns, keep) * per_turn + (summary if turns > keep else 0)
    return whole, kept


# ------------------------------------------------------------ inputs

STEPS = [  # the meter-fault procedure, compiled (Chapter 5)
    {"id": "1", "block": "greet", "say": "Say the disclosure and ask how "
     "you can help.", "needs": [], "tools": []},
    {"id": "2", "block": "identify", "say": "Ask for the account number and "
     "read it back in pairs.", "needs": [], "tools": ["find_account"]},
    {"id": "2a", "block": "verify", "say": "Before anything else, check the "
     "area for an outage. If there is one, give its status and do not book.",
     "needs": ["account found"], "tools": ["outage_status"]},
    {"id": "3", "block": "capture", "say": "Ask what the meter shows, in "
     "the caller's words.", "needs": ["no outage"], "tools": ["open_ticket"]},
    {"id": "4", "block": "escalate", "say": "If the caller smells gas, say "
     "the safety script word for word, then transfer.", "needs": [],
     "tools": ["transfer"]},
    {"id": "5", "block": "collect", "say": "Offer the first opening with the "
     "call-out fee in the same breath.", "needs": ["ticket open"],
     "tools": ["find_slot"]},
    {"id": "5a", "block": "escalate", "say": "If the meter is new and the "
     "caller asks about the fee, a supervisor decides.",
     "needs": ["ticket open"], "tools": ["request_approval"]},
    {"id": "6", "block": "act", "say": "Book only on a yes to the "
     "read-back.", "needs": ["verified", "a yes"], "tools": ["book_visit"]},
    {"id": "7", "block": "confirm", "say": "Say it is booked and that you "
     "are texting the details.", "needs": ["committed"],
     "tools": ["send_text"]},
    {"id": "8", "block": "close", "say": "Ask if there is anything else, "
     "then close.", "needs": [], "tools": ["set_disposition"]}]
ITEMS = [
    {"id": "web-storm-page", "kind": "web page", "rank": 4, "topic": "late",
     "owner": "communications lead", "audience": "public",
     "from": "2026-09-12", "to": None, "source": "memo-114",
     "text": "Customers affected by the storm will not be charged late fees "
             "for September."},
    {"id": "memo-114", "kind": "policy memo", "rank": 1, "topic": "late",
     "owner": "billing policy lead", "audience": "public",
     "from": "2026-09-12", "to": "2026-09-30",
     "text": "Per Policy Memo 114, customers in the designated storm area "
             "who incurred late payment charges on statements issued between "
             "1 and 30 September are eligible for a one-time waiver (max. "
             "$12) of late fees, subject to account verification.",
     "spoken": "Yes: if your bill was due during the storm, we can remove "
               "the twelve-dollar late fee once. Shall I check your account?",
     "terms": {"fees": 1}},
    {"id": "price-list", "kind": "price list", "rank": 2, "topic": "fee",
     "owner": "field operations manager", "audience": "public",
     "from": "2026-07-01", "to": "2026-12-31",
     "text": "A technician visit carries a forty-dollar call-out fee.",
     "spoken": "A technician visit carries a forty-dollar call-out fee."},
    {"id": "billing-guide", "kind": "guide", "rank": 3, "topic": "bill",
     "owner": "billing policy lead", "audience": "public",
     "from": "2026-01-01", "to": "2026-12-31",
     "text": "An estimated reading is used when the meter could not be read; "
             "the next actual reading corrects the bill.",
     "spoken": "When the meter can't be read, the bill uses an estimate, and "
               "the next reading corrects it."},
    {"id": "acct-6042", "kind": "account record", "rank": 0, "topic": None,
     "owner": "the billing system", "audience": "acct-6042",
     "from": None, "to": None, "late_fees_in_storm": 2,
     "text": "Account 6042: electricity and gas bills due in September, both "
             "paid late; two late fees; storm area; no waiver in twelve "
             "months."},
    {"id": "acct-7719", "kind": "account record", "rank": 0, "topic": None,
     "owner": "the billing system", "audience": "acct-7719",
     "from": None, "to": None, "late_fees_in_storm": 1,
     "text": "Account 7719: late fee removed under the storm waiver on 20 "
             "September; storm area."}]
QUESTION = "Will I be charged late fees for September because of the storm?"
CALLER = "acct-6042"
ASKED_ON = "2026-09-24"
DAY_AFTER = "2026-10-01"
TERMS = ["one twelve-dollar late fee", "one of your two"]
OTHERS = [  # step 5: questions the items may or may not cover
    "What is the call-out fee for a technician visit?",
    "Why is my bill based on an estimated reading?",
    "Will rates go up next year because of the storm?",
    "Can I get a smart meter fitted?"]
FLOOR = 0.4          # share of the question the evidence must cover
LONG_CALL = {"turns": 40, "per_turn": 130, "keep": 2, "summary": 180}


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"steps": STEPS, "items": ITEMS, "question": QUESTION,
                "caller": CALLER, "asked_on": ASKED_ON,
                "day_after": DAY_AFTER, "terms": TERMS, "others": OTHERS,
                "floor": FLOOR, "long_call": LONG_CALL}
    if mode == "fixture":
        return json.loads((FIXTURES / "knowledge.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ------------------------------------------------------------ report


def block(put, lead: str, text: str, width: int = 78) -> None:
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"knowledge lab, mode={mode}; evidence class: simulated")
    put("")
    steps = data["steps"]
    put("1. the meter-fault procedure, compiled into steps (Chapter 5)")
    put(f"   {'step':<6}{'block':<10}{'the policy layer checks':<26}tools")
    for st in steps:
        put(f"   {st['id']:<6}{st['block']:<10}"
            f"{', '.join(st['needs']) or '-':<26}"
            f"{', '.join(st['tools']) or '-'}")
    gated = sum(1 for st in steps if st["needs"])
    put(f"   {len(steps)} steps; {gated} with preconditions in code, not "
        "in the prompt")
    put("   step 2a, as the model receives it:")
    block(put, "     ", "\"" + instruction(steps[2]) + "\"")
    put("")
    on = date.fromisoformat(data["asked_on"])
    items, caller, q = data["items"], data["caller"], data["question"]
    put(f"2. evidence for one question, {on.strftime('%-d %B')} "
        f"({caller}, verified by PIN)")
    block(put, "   ", f"\"{q}\"")
    put(f"   {'found, best match first':<24}{'rank':<6}{'may it be spoken?'}")
    s = settle(q, items, caller, on)
    for it in s["found"]:
        why = ("no: not this caller" if not allowed(it, caller)
               else f"no: {valid(it, on, items)}" if valid(it, on, items)
               else "yes, by lookup" if it["audience"] == caller
               else "yes")
        rank = str(it["rank"]) if it["rank"] else "-"
        put(f"   {it['id']:<24}{rank:<6}{why}")
    naive = s["found"][0]
    put("   without filters or precedence, the best match speaks:")
    block(put, "     ", f"\"{naive['text']}\"")
    block(put, "   ", f"with them, {s['winner']['id']} (rank "
          f"{s['winner']['rank']}) outranks "
          + ", ".join(f"{f['id']} (rank {f['rank']})" for f in s["flagged"])
          + "; the conflict goes to the owners of both")
    put("")
    line = render(s)
    c = checks(line, data["terms"])
    memo = s["winner"]
    put("3. the answer, settled and then rendered for the ear")
    put(f"   the memo as written: {len(memo['text'].split())} words in one "
        "sentence")
    put("   its speakable answer, before the account is known:")
    block(put, "     ", f"\"{memo['spoken']}\"")
    put(f"   for {s['record']['id']}, with two fees in the storm:")
    block(put, "     ", f"\"{line}\"")
    put(f"   {c['sentences']} sentences; the longest {c['longest']} words; "
        f"the exception kept: {'yes' if not c['lost'] else 'no'}")
    put(f"   the trace keeps the evidence: {memo['id']}, {s['record']['id']}")
    put("")
    after = date.fromisoformat(data["day_after"])
    s2 = settle(q, items, caller, after)
    put(f"4. the same question on {after.strftime('%-d %B')}")
    for it in s2["found"]:
        if allowed(it, caller) and valid(it, after, items):
            block(put, f"   {it['id']:<18}",
                  f"not spoken: {valid(it, after, items)}")
    put("   the agent:")
    block(put, "     ", f"\"{after_the_end(s2, items, after)}\"")
    put("   the owner was asked to renew, change, or let it lapse a week "
        "before")
    put("")
    put(f"5. answer or abstain (the evidence must cover "
        f"{data['floor']:.0%} of the question)")
    for other in data["others"]:
        got = answer_or_abstain(other, items, caller, on, data["floor"])
        verdict, src = ("abstain", "") if got == "abstain" \
            else ("answer", got)
        put(f"   {verdict:<9}{src:<14}\"{other}\"")
    put("   an abstention says so, and offers a text or a person")
    put("")
    lc = data["long_call"]
    put(f"6. a long call: history at turn {lc['turns']} "
        f"({lc['per_turn']} tokens a turn)")
    whole, kept = context_tokens(lc["turns"], lc["per_turn"], lc["keep"],
                                 lc["summary"])
    put(f"   the whole history                  {whole:>6,} tokens")
    put(f"   the last {lc['keep']} turns and a summary        {kept:>6,} "
        "tokens")
    put("   the facts that decide the call (verified, the offer, the yes, "
        "the")
    put("   operations) live in the state object, not in the history")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("KNOWLEDGE_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"knowledge_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "knowledge.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/knowledge.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("KNOWLEDGE_LAB_MODE", "mock")))
    else:
        run_mode()
