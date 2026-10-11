"""The Claims Line: Quillmere Mutual's voice agent for policyholders.

What it does: answers questions about a policy (grounded in the policy wording, and in the
caller's own policy once they are verified), takes a first notice of loss by voice, sends a
photo link by text and accepts photos in the app, reads a claim's status, sends documents by
email or text, and hands over to a claims specialist, or books a callback when no one is free.

What it never does: say that a loss is covered (an adjuster decides), read personal details
before verification, dial an emergency number, or text a link to a number that is not on the
policy.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from ova.dialogue import FormSkill, Skill, Slot
from ova.knowledge import KnowledgeBase
from ova.operations import OpResult, Proposal, ToolContract
from ova.runtime import Pack, PersonRoute, VoiceBrief
from ova.speech import (Line, Term, on_date, say_address, say_code, say_date, say_money,
                        say_phone_tail, say_time, show_date, show_time, words)

from .domain import ClaimsDesk, LOSS_WORDS, money

HERE = Path(__file__).resolve().parent

CONTRACTS = {c.name: c for c in [
    ToolContract("verify_caller", "instant", "none", "read", "n/a", "Thanks, Alex."),
    ToolContract("file_claim", "short", "explicit", "write", "withdraw_claim",
                 "Your claim is filed. The claim number is C L, two zero four, nine zero five."),
    ToolContract("send_upload_link", "short", "implicit", "write", "none",
                 "I've texted the link to the mobile ending four two one seven."),
    ToolContract("send_status_link", "short", "implicit", "write", "none",
                 "I've texted you a link to follow the claim."),
    ToolContract("send_document", "short", "implicit", "write", "none",
                 "I've emailed your proof of insurance to the address on the policy."),
    ToolContract("schedule_callback", "short", "explicit", "write", "cancel_callback",
                 "A claims specialist will call you tomorrow morning, by ten."),
]}

LOSS_CHOICES = {
    "animal": ["hit a deer", "deer", "animal", "hit an animal"],
    "glass": ["windshield", "windscreen", "cracked glass", "broken window", "chip in the glass",
              "glass"],
    "theft": ["stolen", "theft", "broke into", "broken into", "break in", "break-in",
              "burglary", "burgled", "robbed", "stole"],
    "vandalism": ["vandal", "vandalism", "vandalized", "keyed", "graffiti"],
    "collision": ["accident", "crash", "crashed", "collision", "hit", "rear ended",
                  "rear-ended", "collided", "fender bender", "ran into", "backed into",
                  "sideswiped", "t-boned", "wreck"],
    "storm": ["hail", "storm", "tree fell", "wind", "lightning", "tornado"],
    "water": ["water", "leak", "leaking", "burst", "pipe", "flooded", "flooding", "overflow"],
    "fire": ["fire", "smoke", "burned", "burnt"],
    "other": ["something else", "other"],
}
AUTO_TYPES = {"collision", "glass", "theft", "vandalism", "storm", "animal", "other", "fire"}
HOME_TYPES = {"water", "storm", "fire", "theft", "vandalism", "other"}

EMERGENCY = [
    r"\b(?:someone|somebody|anyone|he|she|they|my \w+|i|we|people)\s*(?:is|are|am|'s|'re|'m)"
    r"\s+(?:badly\s+|seriously\s+|really\s+)?(?:hurt|injured|bleeding|unconscious|trapped|"
    r"not breathing)\b",
    r"\b(?:on fire|still burning|is burning|smell gas|smells like gas|gas leak)\b",
    r"\b(?:need|call|get) (?:an|the) ambulance\b",
]

HOURS = {0: (8, 18), 1: (8, 18), 2: (8, 18), 3: (8, 18), 4: (8, 18), 5: (9, 13)}


def _mask_email(e: str) -> str:
    name, _, domain = e.partition("@")
    return f"{name[0]}...@{domain}"


class ClaimsPack(Pack):
    id = "claims"
    name = "Quillmere Mutual Claims Line"
    timezone = "America/Chicago"
    verify_skill = "verify"
    contracts = CONTRACTS
    labels = {"report_claim": "your claim", "claim_status": "your claim's status",
              "send_documents": "your documents", "callback": "your callback",
              "my_policy": "your question", "photos": "your photos"}
    intents = [
        ("report_claim", [r"\b(?:report|file|make|start|open|lodge|submit)\b.{0,20}\bclaim\b",
                          r"\b(?:accident|crash|crashed|collision|stolen|broke into|break in|"
                          r"broken into|burgl\w+|"
                          r"burst|flooded|hail|vandal\w*|rear ended|hit a deer|someone hit|"
                          r"hit my|backed into|windshield|broken window|tree fell|"
                          r"leaking|fire damage)\b",
                          r"\b(?:report|file)\s+(?:it|this|that|an? (?:accident|theft|loss|"
                          r"break-in|incident))\b",
                          r"\bfirst notice\b"]),
        ("claim_status", [r"\b(?:status|update|progress)\b.{0,30}\bclaim\b",
                          r"\bclaim\b.{0,30}\b(?:status|update|progress)\b",
                          r"\bwhere(?:'s| is) my (?:claim|payment|check)\b",
                          r"\b(?:check|checking) (?:on )?(?:my )?claim\b",
                          r"\bhas my claim\b", r"\bwhen will (?:i|my) .{0,20}\b(?:paid|payment|"
                          r"adjuster|hear)\b"]),
        ("send_documents", [r"\b(?:id card|insurance card|proof of insurance|"
                            r"declarations page|policy documents?|copy of my policy)\b"]),
        ("photos", [r"\b(?:send|upload|add|share)\b.{0,20}\b(?:photos?|pictures?|images?)\b"]),
        ("my_policy", [r"\bmy (?:deductible|coverage|coverages|policy|limits?|rental|"
                       r"roadside)\b", r"\bdo i have\b.{0,30}\b(?:rental|roadside|glass|"
                       r"coverage|flood)\b", r"\bam i covered\b"]),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.brief = VoiceBrief(
            speaker="Quillmere Mutual's automated claims assistant",
            greeting="This is Quillmere Mutual's automated claims assistant. I can report a "
                     "claim, check a claim's status, or answer a question about your policy. "
                     "How can I help?",
            are_you_a_person="No, I'm an automated assistant. I can put you through to a "
                             "claims specialist whenever you like.",
            capabilities="I can report a claim, check a claim's status, send your documents, "
                         "or answer questions about your policy. And I can put you through to "
                         "a person at any time.",
            closing="Thanks for calling Quillmere Mutual. Take care.",
            never_say=[
                (r"\b(?:you(?:'re| are)|that(?:'s| is)|it(?:'s| is)|this is) "
                 r"(?:fully |definitely |probably )?covered\b",
                 "Whether this claim is covered is decided by your adjuster, once they've "
                 "reviewed it."),
                (r"\bwe(?:'ll| will) (?:pay|cover) (?:for )?(?:it|this|that|the)\b",
                 "Your adjuster decides what the policy pays, once they've reviewed the "
                 "claim."),
            ],
            lexicon={"Quillmere": "Quill-meer"},
            registers={"routine": "brisk, friendly, the answer first",
                       "bad news": "the news first, one apology",
                       "distress": "slower, one instruction at a time",
                       "emergency": "the safety line, nothing else"},
            version="1.0",
        )
        self.knowledge = KnowledgeBase(synonyms={
            "windshield": ["glass", "windscreen"], "rental": ["hire", "loaner"],
            "tow": ["towing", "roadside"], "deductible": ["excess"],
            "photo": ["picture", "image"], "adjuster": ["adjustor", "handler"],
            "flood": ["flooding"], "stolen": ["theft"], "car": ["vehicle", "auto"],
            "house": ["home", "dwelling"], "hotel": ["living"]})
        self.knowledge.add_dir(HERE / "knowledge")
        self.repairs.lines["unclear"] = [
            "Sorry, I missed that.",
            "I'm still not catching it, sorry. You can also type it, or use your keypad."]
        self.desk: ClaimsDesk | None = None
        self.skills = self._skills()

    # ------------------------------------------------------------ setup
    def seed(self, store, clock) -> None:
        self.desk = ClaimsDesk(store)
        self.desk.seed(clock.today())

    def policy(self, ctx) -> dict | None:
        return self.desk.policy(ctx.state.identity.get("policy"))

    # ------------------------------------------------------------ people
    def person_route(self, ctx) -> PersonRoute:
        now = ctx.now
        hours = HOURS.get(now.weekday())
        wait = int(ctx.store.setting("claims:wait_min", "4") or 4)
        number = ctx.store.setting("claims:transfer_number", "") or ""
        if hours and hours[0] <= now.hour < hours[1] and \
                ctx.store.setting("claims:staffed", "on") == "on":
            return PersonRoute("a claims specialist", True, wait, number)
        nxt = now.date() + dt.timedelta(days=1)
        while nxt.weekday() not in HOURS:
            nxt += dt.timedelta(days=1)
        opens = HOURS[nxt.weekday()][0]
        day = "tomorrow" if nxt == now.date() + dt.timedelta(days=1) else f"on {nxt:%A}"
        return PersonRoute("a claims specialist", False, 0, number,
                           next_open=f"until {say_time(f'{opens}:00')} {day}",
                           callback_by=f"{day}, by {say_time(f'{opens + 2}:00')}")

    def summary(self, ctx) -> dict:
        s = ctx.state
        who = s.identity.get("first", "Caller not verified")
        if s.identity.get("level") != "none":
            who = f"Verified {who}"
        what = {"report_claim": "reporting", "claim_status": "asking status",
                "send_documents": "wants documents", "my_policy": "policy question"}.get(
            s.skill or "", "general question")
        bits = [who, what]
        if s.slots.get("loss_type"):
            bits.append(LOSS_WORDS.get(s.slots["loss_type"], ""))
        claim = s.facts.get("claim")
        bits.append(f"claim {claim}" if claim else "no claim filed")
        whisper = "; ".join(b for b in bits if b) + "."
        return {"whisper": " ".join(whisper.split()[:15]), "slots": dict(s.slots),
                "identity": {k: v for k, v in s.identity.items() if k != "dob"},
                "claim": claim}

    # ------------------------------------------------------------ safety
    async def emergency(self, ctx, text: str) -> bool:
        t = text.lower()
        if not any(re.search(p, t) for p in EMERGENCY):
            return False
        s = ctx.state
        first = not s.facts.get("safety_said")
        s.facts["safety_said"] = True
        if first:
            ctx.say("If anyone is hurt or in danger, please hang up and call emergency "
                    "services now. Your claim can wait.", register="emergency")
        else:
            ctx.say("Please get help first if anyone is hurt.", register="emergency")
        if s.skill == "report_claim" and s.expecting == "injured":
            s.slots["injured"] = True
            s.expecting = None
        ctx.say("If everyone is safe and you'd like to carry on, I'm here.",
                register="distress")
        if s.pending:
            await ctx.agent.reprompt()
        elif s.skill:
            await ctx.agent.next_step()
        return True

    # ------------------------------------------------------------ the caller's own policy
    async def personal_answer(self, ctx, u) -> bool:
        t = (u.text or "").lower()
        mine = re.search(r"\b(my|i have|do i|am i)\b", t) and re.search(
            r"\b(deductible|rental|roadside|glass|windshield|coverage|covered|limit|flood|"
            r"liability|living expenses)\b", t)
        if not mine:
            return False
        if ctx.state.identity.get("level") == "none":
            await ctx.agent.start_skill("my_policy", u)
            return True
        ctx.say(self.policy_fact(ctx, t))
        return True

    def policy_fact(self, ctx, t: str) -> Line:
        p = self.policy(ctx)
        if p is None:
            return Line.plain("I couldn't find your policy details.")
        cov, ded = p.get("coverages", {}), p.get("deductibles", {})
        say_m = lambda n: Term("amount", money(n), say_money(n), str(n))
        if "deductible" in t:
            if p["kind"] == "auto":
                return Line.of("Your collision deductible is ", say_m(ded["collision"]),
                               ", and your comprehensive deductible is ",
                               Term("amount2", money(ded["comprehensive"]),
                                    say_money(ded["comprehensive"]),
                                    str(ded["comprehensive"])), ".")
            return Line.of("Your home deductible is ", say_m(ded["all_perils"]), ".")
        if "rental" in t:
            r = cov.get("rental")
            if not r:
                return Line.plain("Your policy doesn't include rental reimbursement. Your "
                                  "agent can add it for the future.")
            return Line.of("Your policy includes rental reimbursement, up to ",
                           say_m(r["per_day"]), f" a day for up to {words(r['max_days'])} "
                           "days, while your car is being repaired after a claim.")
        if "roadside" in t or "tow" in t:
            return Line.plain("Your policy includes roadside assistance, at any hour."
                              if cov.get("roadside") else
                              "Your policy doesn't include roadside assistance.")
        if "glass" in t or "windshield" in t:
            if cov.get("full_glass"):
                return Line.plain("Your policy has full glass, so a windshield repair or "
                                  "replacement has no deductible.")
            return Line.of("Glass damage falls under your comprehensive coverage, with a ",
                           say_m(ded.get("glass", ded.get("comprehensive", 0))),
                           " deductible.")
        if "flood" in t:
            return Line.plain("Your home policy doesn't include flood. Flood insurance is a "
                              "separate policy.")
        if "living" in t:
            return Line.of("Your policy includes additional living expenses, up to ",
                           say_m(cov.get("additional_living_expenses", 0)), ".")
        if "liability" in t or "limit" in t:
            if p["kind"] == "auto":
                return Line.plain(f"Your liability limits are {cov.get('liability')}, in "
                                  "thousands of dollars. Your declarations page has the "
                                  "details.")
        kinds = "collision, comprehensive" if p["kind"] == "auto" else "dwelling, belongings"
        return Line.plain(f"Your {p['kind']} policy is active and includes {kinds} coverage. "
                          "Whether a particular claim is covered is decided by your "
                          "adjuster.")

    # ------------------------------------------------------------ other channels
    async def on_external(self, ctx, event: dict) -> None:
        if event.get("type") == "photos" and event.get("claim") in (
                ctx.state.facts.get("claim"), *ctx.state.facts.get("claims_seen", [])):
            n = event.get("count", 1)
            ctx.say(Line.of(f"I can see {words(n)} new photo{'s' if n != 1 else ''} on claim ",
                            Term("claim", event["claim"], say_code(event["claim"]),
                                 event["claim"]), ". Thank you, that helps your adjuster."))
            ctx.card("photos", claim=event["claim"], count=n, total=event.get("total", n))

    # ------------------------------------------------------------ the skills
    def _skills(self) -> dict[str, Skill]:
        return {s.name: s for s in [
            self._verify(), self._report_claim(), ClaimStatus(self), MyPolicy(self),
            self._send_documents(), self._callback(), Photos(self)]}

    def _verify(self) -> FormSkill:
        async def done(ctx, _: OpResult) -> None:
            s = ctx.state
            policy, claim = self.desk.resolve(s.slots.get("reference", ""))
            dob = s.slots.get("dob")
            if policy and policy["holder"]["dob"] == dob:
                s.identity = {"level": "verified", "policy": policy["number"],
                              "first": policy["holder"]["first"], "kind": policy["kind"]}
                if claim:
                    s.facts.setdefault("claims_seen", []).append(claim["number"])
                    s.facts["asked_claim"] = claim["number"]
                ctx.say(f"Thanks, {policy['holder']['first']}.")
                await ctx.agent.complete_skill(closing=False)
                return
            n = s.fails["no_match"] = s.fails.get("no_match", 0) + 1
            if n >= 2:
                ctx.say("Those details still don't match what I have, so I'll get you to a "
                        "person who can help.")
                await ctx.agent.person(None, failover=True)
                return
            ctx.say("I couldn't match those details. Let's try once more.")
            s.slots, s.asked = {}, {}
            await ctx.agent.next_step()

        return FormSkill(
            name="verify", description="Confirm who the caller is.",
            slots=[
                Slot("reference", "First I need to confirm who I'm speaking with. What's "
                     "your policy number? A claim number works too.", "id", "identifier",
                     id_digits=6, keypad=True,
                     reask="Please say the six digits of your policy or claim number, a few "
                           "at a time.",
                     read_back=lambda ctx, v: Line.of("That's ", Term(
                         "reference", v, say_code(v), v), ". Is that right?")),
                Slot("dob", "And your date of birth?", "birthdate",
                     reask="What's your date of birth? For example, March fourth, nineteen "
                           "eighty five."),
            ],
            done=done)

    def _report_claim(self) -> FormSkill:
        pack = self

        def kind(ctx) -> str:
            return ctx.state.identity.get("kind", "auto")

        def is_auto(v): return v.get("_kind", "auto") == "auto"

        async def prefill(ctx) -> None:
            ctx.state.slots["_kind"] = kind(ctx)
            p = pack.policy(ctx)
            if p and p["kind"] == "home" and p.get("property"):
                ctx.state.slots.setdefault("location", p["property"])

        async def injured(ctx, v) -> None:
            if v and not ctx.state.facts.get("safety_said"):
                ctx.state.facts["safety_said"] = True
                ctx.say("I'm sorry. If anyone needs medical help, please call emergency "
                        "services first. Your claim can wait.", register="distress")

        def check_type(ctx, v):
            allowed = AUTO_TYPES if kind(ctx) == "auto" else HOME_TYPES
            if v not in allowed:
                return ("That doesn't sound like something for a "
                        f"{kind(ctx)} policy. What happened, in a few words?")
            return None

        def check_date(ctx, v):
            d = dt.date.fromisoformat(v)
            if d > ctx.today:
                return "That date hasn't happened yet on my side. What day did it happen?"
            if (ctx.today - d).days > 365:
                return ("That's more than a year ago. A claims specialist handles older "
                        "claims. What day did it happen?")
            return None

        def check_place(ctx, v):
            if re.fullmatch(r"(?:a |the )?(?:parking lot|parking garage|garage|street|road|"
                            r"highway|driveway|lot|store)", v.lower()):
                return f"Which {v.lower().replace('a ', '').replace('the ', '')}? The " \
                       "nearest street or business name is fine."
            return None

        def text_ask(ctx) -> Line:
            p = pack.policy(ctx)
            tail = say_phone_tail(p["holder"]["phone"]) if p else ""
            shown = p["holder"]["phone"][-4:] if p else ""
            if ctx.state.channel in ("web", "webrtc", "app"):
                return Line.of("Photos help your adjuster. You can use the camera button on "
                               "your screen, and I can also text a link to the mobile ending ",
                               Term("phone", shown, tail, shown), ". Shall I text it?")
            return Line.of("Photos help your adjuster. Can I text you a link to upload them? "
                           "It goes to the mobile ending ", Term("phone", shown, tail, shown),
                           ".")

        def terms(ctx):
            s = ctx.state.slots
            d = dt.date.fromisoformat(s["loss_date"])
            p = Proposal.make("file_claim", ctx.state.identity.get("policy", ""),
                              loss_type=s["loss_type"], loss_date=s["loss_date"],
                              location=s["location"])
            shown_d, spoken_d = on_date(d, ctx.today)
            parts = ["Here's what I have: ",
                     Term("loss_type", LOSS_WORDS[s["loss_type"]], LOSS_WORDS[s["loss_type"]],
                          s["loss_type"]), " ",
                     Term("loss_date", shown_d, spoken_d, s["loss_date"])]
            if s.get("loss_time") and ":" in str(s["loss_time"]):
                parts += [", at about ", Term("loss_time", show_time(s["loss_time"]),
                                              say_time(s["loss_time"]), s["loss_time"])]
            elif s.get("loss_time"):
                parts += [f", in the {s['loss_time']}"]
            parts += [", at ", Term("location", s["location"], say_address(s["location"]),
                                    s["location"]),
                      ". Shall I file the claim?"]
            return p, Line.of(*parts)

        async def act(ctx, op_id: str):
            p = pack.policy(ctx)
            claim = pack.desk.file(op_id, p, ctx.state.slots, ctx.today, ctx.state.channel)
            return {"claim": claim["number"]}

        async def reconcile(ctx, op_id: str):
            c = pack.desk.by_operation(op_id)
            return {"claim": c["number"]} if c else None

        async def done(ctx, r: OpResult) -> None:
            s = ctx.state
            if r.state != "committed":
                ctx.say(r.line or "I couldn't file the claim.")
                await ctx.agent.person(None, failover=True)
                return
            number = r.data["claim"]
            s.facts["claim"] = number
            s.facts.setdefault("claims_seen", []).append(number)
            claim = pack.desk.claim(number)
            ctx.say(Line.of("Your claim is filed. The claim number is ",
                            Term("claim", number, say_code(number), number), ".",
                            backed_by=r.op_id))
            ctx.card("claim", claim=_public_claim(claim))
            link = ctx.rt.links.url("upload", number)
            if ctx.state.channel in ("web", "webrtc", "app"):
                ctx.card("upload", claim=number, url=link)
            if s.slots.get("text_ok"):
                await pack.send_link(ctx, number, link, "upload")
            if s.slots.get("injured"):
                ctx.say("Because someone was hurt, an injury specialist will call you today.")
            when = dt.date.fromisoformat(claim["next"]["date"])
            ctx.say(Line.of(f"{claim['adjuster']} is your adjuster and will call you by ",
                            Term("date", show_date(when, ctx.today), say_date(when, ctx.today),
                                 when.isoformat()), "."))
            p = pack.policy(ctx)
            rental = (p or {}).get("coverages", {}).get("rental")
            if claim["kind"] == "auto" and s.slots.get("drivable") is False and rental:
                ctx.say(Line.of("Your policy includes a rental car, up to ",
                                Term("amount", money(rental["per_day"]),
                                     say_money(rental["per_day"]), str(rental["per_day"])),
                                " a day. Your adjuster can set that up."))
            await ctx.agent.complete_skill()

        auto = lambda v: v.get("_kind") == "auto"
        return FormSkill(
            name="report_claim", intents=("report_claim",), needs_identity=True,
            description="Report a new claim (first notice of loss).",
            intro="I'm sorry that happened. I'll take the details; it takes about three "
                  "minutes.",
            prefill=prefill,
            slots=[
                Slot("injured", "First, is anyone hurt?", "yesno", on_fill=injured),
                Slot("loss_type", "What happened? For example, a collision, a theft, storm "
                     "or water damage, or broken glass.", "choice", choices=LOSS_CHOICES,
                     check=check_type, reask="In a few words, what kind of damage is it?"),
                Slot("loss_date", "When did it happen?", "date_past", check=check_date,
                     reask="What day did it happen? Today, yesterday, or a date is fine."),
                Slot("loss_time", "About what time?", "time", optional=True,
                     reask="Roughly what time of day? It's fine if you're not sure."),
                Slot("location", "Where did it happen? A street and city, or the nearest "
                     "business, is fine.", "place", check=check_place),
                Slot("description", "In a sentence or two, what happened?", "text"),
                Slot("other_party", "Was another vehicle involved?", "yesno",
                     when=lambda v: auto(v) and v.get("loss_type") == "collision"),
                Slot("police", "Was a police report made?", "yesno", optional=True,
                     when=lambda v: v.get("loss_type") in ("collision", "theft",
                                                            "vandalism")),
                Slot("drivable", "Can the car be driven safely?", "yesno",
                     when=lambda v: auto(v) and v.get("loss_type") in (
                         "collision", "animal", "storm", "vandalism", "fire")),
                Slot("text_ok", text_ask, "yesno"),
            ],
            terms=terms, act=act, reconcile=reconcile, done=done)

    def _send_documents(self) -> FormSkill:
        pack = self
        docs = {"id_card": ["id card", "insurance card", "proof of insurance", "proof"],
                "policy": ["policy documents", "declarations", "policy booklet", "policy",
                           "copy of my policy"]}
        names = {"id_card": "proof of insurance", "policy": "policy documents"}

        async def done(ctx, _r) -> None:
            s = ctx.state
            p = pack.policy(ctx)
            doc = names[s.slots["doc"]]
            via = s.slots["via"]
            to = p["holder"]["email"] if via == "email" else p["holder"]["phone"]
            proposal = Proposal.make("send_document", p["number"], doc=doc, via=via)
            link = ctx.rt.links.url("docs", p["number"], extra={"doc": s.slots["doc"]})

            async def run(op_id):
                if via == "email":
                    m = await ctx.rt.channels.send_email(
                        s.call_id, to, f"Your Quillmere Mutual {doc}",
                        f"Hello {p['holder']['first']},\n\nHere is your {doc}: {link}\n\n"
                        "This link expires in three days.\nQuillmere Mutual (demonstration)")
                else:
                    m = await ctx.rt.channels.send_text(
                        s.call_id, to, f"Quillmere Mutual: your {doc}: {link}")
                if m.status == "failed":
                    from ova.operations import ToolError
                    raise ToolError("unavailable", "document delivery failed")
                return {"message": m.id, "status": m.status}

            r = await ctx.execute(proposal, run)
            if r.state == "committed":
                where = (f"the address on the policy, {_mask_email(to)}" if via == "email"
                         else "the mobile ending " + to[-4:])
                spoken_where = ("the email address on the policy" if via == "email"
                                else "the mobile ending " + say_phone_tail(to))
                ctx.say(Line.of(f"I've {'emailed' if via == 'email' else 'texted'} your "
                                f"{doc} to ", Term("to", where, spoken_where, to), ".",
                                backed_by=r.op_id))
            else:
                ctx.say(r.line)
            await ctx.agent.complete_skill()

        return FormSkill(
            name="send_documents", intents=("send_documents",), needs_identity=True,
            description="Send proof of insurance or policy documents.",
            slots=[Slot("doc", "Which would you like: your proof of insurance, or your "
                        "policy documents?", "choice", choices=docs),
                   Slot("via", "Shall I send it by email or by text?", "choice",
                        choices={"email": ["email", "e-mail", "mail"],
                                 "text": ["text", "sms", "message", "phone"]})],
            done=done)

    def _callback(self) -> FormSkill:
        pack = self

        def terms(ctx):
            route = pack.person_route(ctx)
            p = pack.policy(ctx)
            phone = (p or {}).get("holder", {}).get("phone") or ctx.state.caller or ""
            prop = Proposal.make("schedule_callback", ctx.state.identity.get("policy", "caller"),
                                 by=route.callback_by, phone=phone)
            shown_phone = phone[-4:] if phone else "your number"
            return prop, Line.of("I can have a claims specialist call you ",
                                 Term("by", route.callback_by, route.callback_by,
                                      route.callback_by),
                                 ", at the number ending ",
                                 Term("phone", shown_phone, say_phone_tail(phone) if phone
                                      else "your number", phone), ". Shall I set that up?")

        async def act(ctx, op_id):
            route = pack.person_route(ctx)
            p = pack.policy(ctx)
            phone = (p or {}).get("holder", {}).get("phone") or ctx.state.caller
            pr = ctx.rt.promises.make(ctx.state.call_id, "callback", 16 * 3600,
                                      {"to": phone, "by": route.callback_by,
                                       "summary": pack.summary(ctx)["whisper"]})
            return {"promise": pr.id}

        async def done(ctx, r):
            if r.state == "committed":
                ctx.say(Line.of("Done. A claims specialist will call you, and they'll have "
                                "what you've told me.", backed_by=r.op_id))
            else:
                ctx.say(r.line or "I couldn't set that up.")
            await ctx.agent.complete_skill(closing=False)
            if not ctx.state.skill:
                await ctx.agent.goodbye()

        return FormSkill(name="callback", description="Book a callback from a person.",
                         slots=[], terms=terms, act=act, done=done, quick=False)

    async def send_link(self, ctx, claim_no: str, link: str, purpose: str) -> None:
        p = self.policy(ctx)
        if not p:
            return
        phone = p["holder"]["phone"]
        tool = "send_upload_link" if purpose == "upload" else "send_status_link"
        proposal = Proposal.make(tool, claim_no, to=phone)
        body = (f"Quillmere Mutual: add photos to claim {claim_no} here: {link} "
                "(expires in 3 days)" if purpose == "upload" else
                f"Quillmere Mutual: follow claim {claim_no} here: {link}")

        async def run(op_id):
            m = await ctx.rt.channels.send_text(ctx.state.call_id, phone, body)
            if m.status == "failed":
                from ova.operations import ToolError
                raise ToolError("unavailable", "text failed")
            return {"message": m.id}

        r = await ctx.execute(proposal, run)
        if r.state == "committed":
            what = "the link" if purpose == "upload" else "a link to follow the claim"
            ctx.say(Line.of(f"I've texted {what} to the mobile ending ",
                            Term("phone", phone[-4:], say_phone_tail(phone), phone), ".",
                            backed_by=r.op_id))
        else:
            ctx.say("The text didn't go through. I'll try again in five minutes, and your "
                    "adjuster can send it too.")
            ctx.rt.promises.make(ctx.state.call_id, "text", 30 * 60,
                                 {"to": phone, "body": body})


def _public_claim(c: dict) -> dict:
    keep = ("number", "policy", "kind", "loss_type", "loss_date", "loss_time", "location",
            "status", "adjuster", "next", "photos", "history")
    out = {k: c.get(k) for k in keep}
    out["photos"] = len(c.get("photos") or [])
    return out


class ClaimStatus(Skill):
    def __init__(self, pack: ClaimsPack):
        super().__init__("claim_status", ("claim_status",), True,
                         "Read a claim's status, next step, and date.")
        self.pack = pack

    async def start(self, ctx) -> None:
        s = ctx.state
        policy_no = s.identity.get("policy")
        claims = self.pack.desk.claims_for(policy_no) if policy_no else []
        asked = s.facts.get("asked_claim")
        if asked:
            claims = [c for c in claims if c["number"] == asked] or claims
        open_claims = [c for c in claims if c["status"] != "closed"]
        if not claims:
            ctx.offer("I don't see a claim on your policy. Would you like to report one?",
                      "report_instead", self._report, self._no_report)
            return
        if len(open_claims) > 1:
            s.facts["choose_claim"] = [c["number"] for c in open_claims]
            names = " or ".join(
                f"the {LOSS_WORDS[c['loss_type']].replace('a ', '')} from "
                f"{show_date(c['loss_date'], ctx.today)}" for c in open_claims)
            ctx.say(f"I see {words(len(open_claims))} open claims: {names}. Which one?")
            return
        await self.read(ctx, (open_claims or claims)[0])

    async def handle(self, ctx, u) -> bool:
        s = ctx.state
        options = s.facts.get("choose_claim")
        if not options:
            return False
        t = u.text.lower()
        for n in options:
            c = self.pack.desk.claim(n)
            words_for = [c["loss_type"]] + LOSS_CHOICES.get(c["loss_type"], [])
            if n[-6:] in re.sub(r"\D", "", t) or any(w in t for w in words_for):
                s.facts.pop("choose_claim")
                await self.read(ctx, c)
                return True
        return False

    async def read(self, ctx, c: dict) -> None:
        s = ctx.state
        s.facts.setdefault("claims_seen", []).append(c["number"])
        ctx.say(self.pack.desk.status_line(c, ctx.today))
        ctx.card("claim", claim=_public_claim(c))
        if c["status"] == "reported" and not c.get("photos"):
            s.facts["link_claim"] = c["number"]
            ctx.offer("Shall I text you the link to add photos?", "photo_link",
                      self._text_upload, self._done)
            return
        s.facts["link_claim"] = c["number"]
        ctx.offer("Would you like a text with a link to follow the claim?", "status_link",
                  self._text_status, self._done)

    async def _text_upload(self, ctx) -> None:
        n = ctx.state.facts["link_claim"]
        link = ctx.rt.links.url("upload", n)
        if ctx.state.channel in ("web", "webrtc", "app"):
            ctx.card("upload", claim=n, url=link)
        await self.pack.send_link(ctx, n, link, "upload")
        await ctx.agent.complete_skill()

    async def _text_status(self, ctx) -> None:
        n = ctx.state.facts["link_claim"]
        await self.pack.send_link(ctx, n, ctx.rt.links.url("status", n), "status")
        await ctx.agent.complete_skill()

    async def _done(self, ctx) -> None:
        await ctx.agent.complete_skill()

    async def _report(self, ctx) -> None:
        ctx.state.skill = None
        await ctx.agent.start_skill("report_claim")

    async def _no_report(self, ctx) -> None:
        await ctx.agent.complete_skill()


class MyPolicy(Skill):
    """A question about the caller's own policy, asked before they were verified: verify,
    then answer the question they asked."""

    def __init__(self, pack: ClaimsPack):
        super().__init__("my_policy", ("my_policy",), True,
                         "Answer a question about the caller's own policy.")
        self.pack = pack

    async def start(self, ctx) -> None:
        question = ctx.state.facts.get("request:my_policy") or ""
        ctx.say(self.pack.policy_fact(ctx, question.lower()))
        await ctx.agent.complete_skill()


class Photos(Skill):
    def __init__(self, pack: ClaimsPack):
        super().__init__("photos", ("photos",), True, "Send photos for a claim.")
        self.pack = pack

    async def start(self, ctx) -> None:
        s = ctx.state
        claims = self.pack.desk.claims_for(s.identity.get("policy", ""))
        target = s.facts.get("claim") or s.facts.get("asked_claim") or (
            max(claims, key=lambda c: c["reported_at"])["number"] if claims else None)
        if not target:
            ctx.offer("I don't see a claim to add photos to. Would you like to report one?",
                      "report_instead", self._report, self._no)
            return
        s.facts.setdefault("claims_seen", []).append(target)
        link = ctx.rt.links.url("upload", target)
        if s.channel in ("web", "webrtc", "app"):
            ctx.card("upload", claim=target, url=link)
            ctx.say(Line.of("You can add photos to claim ", Term("claim", target,
                                                                   say_code(target), target),
                            " with the camera button on your screen."))
        await self.pack.send_link(ctx, target, link, "upload")
        await ctx.agent.complete_skill()

    async def _report(self, ctx) -> None:
        ctx.state.skill = None
        await ctx.agent.start_skill("report_claim")

    async def _no(self, ctx) -> None:
        await ctx.agent.complete_skill()
