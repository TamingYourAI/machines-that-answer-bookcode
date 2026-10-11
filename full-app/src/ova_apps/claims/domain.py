"""The claims desk: Quillmere Mutual's system of record, as the agent's tools see it.

Policies are read-only. Claims are written once, under the operation id that filed them, so a
retried or replayed "yes" can never file two claims (the conditional write). Photos move a claim
from waiting for photos to with the adjuster. Everything is synthetic.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from ova.speech import (Line, Term, on_date, say_code, say_date, say_money, say_time,
                        show_date)
from ova.store import Store

DATA = Path(__file__).resolve().parent / "data" / "policies.json"

LOSS_WORDS = {"collision": "a collision", "glass": "glass damage", "theft": "a theft",
              "vandalism": "vandalism", "storm": "storm damage", "water": "water damage",
              "fire": "fire damage", "animal": "hitting an animal", "other": "damage"}


def business_day_after(d: dt.date, n: int = 1) -> dt.date:
    while n:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def money(n: float) -> str:
    return f"${n:,.0f}" if float(n).is_integer() else f"${n:,.2f}"


class ClaimsDesk:
    def __init__(self, store: Store):
        self.store = store
        data = json.loads(DATA.read_text())
        self.adjusters = data["adjusters"]
        self._policies = {p["number"]: p for p in data["policies"]}

    # ------------------------------------------------------------ reads
    def policy(self, number: str | None) -> dict | None:
        return self._policies.get(number or "")

    def policies(self) -> list[dict]:
        return list(self._policies.values())

    def claim(self, number: str | None) -> dict | None:
        return self.store.get("claim", number or "")

    def claims_for(self, policy_no: str) -> list[dict]:
        return [c for c in self.store.all("claim") if c["policy"] == policy_no]

    def by_operation(self, op_id: str) -> dict | None:
        return next((c for c in self.store.all("claim") if c.get("operation") == op_id), None)

    def resolve(self, digits: str) -> tuple[dict | None, dict | None]:
        """A six-digit reference: a policy number, or a claim number. (policy, claim)."""
        d = digits[-6:]
        claim = self.claim(f"CL-{d}")
        if claim:
            return self.policy(claim["policy"]), claim
        return self.policy(f"QM-{d}"), None

    # ------------------------------------------------------------ writes
    def adjuster_for(self, claim_no: str) -> dict:
        h = int(hashlib.sha256(claim_no.encode()).hexdigest(), 16)
        return self.adjusters[h % len(self.adjusters)]

    def number_for(self, op_id: str) -> str:
        h = int(hashlib.sha256(op_id.encode()).hexdigest(), 16)
        n = 200000 + h % 700000
        while self.claim(f"CL-{n}") and self.claim(f"CL-{n}").get("operation") != op_id:
            n += 1
        return f"CL-{n}"

    def file(self, op_id: str, policy: dict, slots: dict, today: dt.date,
             channel: str) -> dict:
        existing = self.by_operation(op_id)
        if existing:
            return existing
        number = self.number_for(op_id)
        adj = self.adjuster_for(number)
        call_by = business_day_after(today)
        claim = {
            "number": number, "policy": policy["number"], "kind": policy["kind"],
            "loss_type": slots.get("loss_type"), "loss_date": slots.get("loss_date"),
            "loss_time": slots.get("loss_time"), "location": slots.get("location"),
            "description": slots.get("description"), "injured": slots.get("injured"),
            "other_party": slots.get("other_party"), "police": slots.get("police"),
            "drivable": slots.get("drivable"), "status": "reported",
            "adjuster": adj["name"], "next": {"what": "adjuster call",
                                              "date": call_by.isoformat()},
            "photos": [], "operation": op_id, "channel": channel,
            "reported_at": today.isoformat(),
            "history": [{"date": today.isoformat(), "status": "reported",
                         "note": f"Reported by {channel}."}],
        }
        if not self.store.insert("claim", number, claim):     # the conditional write
            return self.claim(number)
        self.store.event("claim", number, {"status": "reported", "operation": op_id})
        return claim

    def add_photos(self, number: str, file_ids: list[str], today: dt.date) -> dict | None:
        c = self.claim(number)
        if c is None:
            return None
        c["photos"] = c.get("photos", []) + file_ids
        n = len(file_ids)
        if c["status"] == "reported":
            c["status"] = "photos_received"
        c["history"].append({"date": today.isoformat(), "status": c["status"],
                             "note": f"{n} photo{'s' if n != 1 else ''} received."})
        self.store.put("claim", number, c)
        self.store.event("claim", number, {"status": c["status"], "photos": len(c["photos"])})
        return c

    # ------------------------------------------------------------ words
    def loss_words(self, loss_type: str | None) -> str:
        return LOSS_WORDS.get(loss_type or "other", "damage")

    def status_line(self, c: dict, today: dt.date) -> Line:
        line = self._status_line(c, today)
        line.backed_by = f"record:claim:{c['number']}"
        return line

    def _status_line(self, c: dict, today: dt.date) -> Line:
        num = Term("claim", c["number"], say_code(c["number"]), c["number"])
        st = c["status"]
        adj = c.get("adjuster", "your adjuster")
        nxt = c.get("next") or {}
        when = dt.date.fromisoformat(nxt["date"]) if nxt.get("date") else None
        date_term = Term("date", show_date(when, today), say_date(when, today),
                         nxt.get("date", "")) if when else None
        if st == "reported":
            return Line.of("Claim ", num, " is open, and we're waiting for photos of the "
                           f"damage. {adj}, your adjuster, will call you by ", date_term, ".")
        if st == "photos_received":
            return Line.of("Your photos for claim ", num, f" are in. {adj} has the claim "
                           "and will call you by ", date_term, ".")
        if st == "inspection_scheduled":
            a, b = nxt.get("window", ["10:00", "12:00"])
            return Line.of("For claim ", num, ", an inspection is booked for ", date_term,
                           f", between {say_time(a)} and {say_time(b)}. "
                           f"Your adjuster is {adj}.")
        if st == "estimate_ready":
            amt = c.get("estimate", 0)
            ded = c.get("deductible", 0)
            return Line.of("For claim ", num, ", the repair estimate is ready: ",
                           Term("amount", money(amt), say_money(amt), str(amt)),
                           ", before your ", Term("deductible", money(ded), say_money(ded),
                                                  str(ded)), " deductible.")
        if st == "payment_issued":
            p = c.get("payment") or {}
            paid = dt.date.fromisoformat(p.get("date", today.isoformat()))
            return Line.of("For claim ", num, ", a payment of ",
                           Term("amount", money(p.get("amount", 0)),
                                say_money(p.get("amount", 0)), str(p.get("amount", 0))),
                           " was issued ", Term("date", *on_date(paid, today),
                                                paid.isoformat()),
                           ". It usually arrives within three business days.")
        return Line.of("Claim ", num, " is closed.")

    # ------------------------------------------------------------ the demonstration's history
    def seed(self, today: dt.date) -> None:
        if self.store.count("claim"):
            return
        d = lambda n: (today + dt.timedelta(days=n)).isoformat()
        seeds = [
            {"number": "CL-204817", "policy": "QM-481273", "kind": "auto",
             "loss_type": "collision", "loss_date": d(-12), "loss_time": "17:40",
             "location": "Clark Street Parking Garage", "description":
             "Another car backed into the rear bumper while parked.", "injured": False,
             "other_party": True, "police": False, "drivable": True,
             "status": "inspection_scheduled", "adjuster": "Dana Reyes",
             "next": {"what": "inspection", "date": business_day_after(today, 2).isoformat(),
                      "window": ["10:00", "12:00"]},
             "photos": ["seed-1", "seed-2"], "operation": "seed", "channel": "phone",
             "reported_at": d(-12), "history": [
                 {"date": d(-12), "status": "reported", "note": "Reported by phone."},
                 {"date": d(-11), "status": "photos_received", "note": "2 photos."},
                 {"date": d(-5), "status": "inspection_scheduled",
                  "note": "Inspection booked."}]},
            {"number": "CL-198342", "policy": "QM-730914", "kind": "home",
             "loss_type": "water", "loss_date": d(-40), "loss_time": None,
             "location": "42 Linden Ave, Evanston", "description":
             "A pipe under the kitchen sink burst overnight.", "injured": False,
             "status": "payment_issued", "adjuster": "Morgan Lee",
             "payment": {"amount": 4850, "date": d(-3)}, "next": {},
             "photos": ["seed-3"], "operation": "seed", "channel": "app",
             "reported_at": d(-40), "history": [
                 {"date": d(-40), "status": "reported", "note": "Reported in the app."},
                 {"date": d(-3), "status": "payment_issued", "note": "$4,850 paid."}]},
            {"number": "CL-207455", "policy": "QM-552806", "kind": "auto",
             "loss_type": "theft", "loss_date": d(-2), "loss_time": None,
             "location": "Outside 1500 W Belmont Ave", "description":
             "Catalytic converter stolen overnight.", "injured": False, "police": True,
             "status": "reported", "adjuster": "Chris Patel",
             "next": {"what": "adjuster call", "date": business_day_after(today).isoformat()},
             "photos": [], "operation": "seed", "channel": "web", "reported_at": d(-2),
             "history": [{"date": d(-2), "status": "reported", "note": "Reported online."}]},
        ]
        for c in seeds:
            self.store.put("claim", c["number"], c)
