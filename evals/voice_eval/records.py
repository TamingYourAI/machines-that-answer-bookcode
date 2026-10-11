"""The end state of a call, read from the system's own records (Chapter 17: the system of record
says what happened, not the transcript).

Every reader returns one shape:

    {"call": {"id", "outcome"},
     "turns": [{"who": "agent" | "caller", "text", "speech", "t", "terms": [...]}],
     "operations": [{"tool", "state", "terms", "created_at", "updated_at"}],
     "messages": [{"to", "body", "status", "t"}]}

Times are the system's own clock, in seconds, so an operation's commit and a line's time compare.
"""
from __future__ import annotations

import httpx


def from_ova(base_url: str, call_id: str, admin_token: str = "", say_terms: dict | None = None,
             client: httpx.Client | None = None) -> dict:
    """The companion app's records for one call, through its console API. ``say_terms`` maps a
    line id to the terms the runner saw on that line's event."""
    headers = {"x-admin-token": admin_token} if admin_token else {}
    c = client or httpx.Client(timeout=10)
    try:
        r = c.get(f"{base_url.rstrip('/')}/api/admin/calls/{call_id}", headers=headers)
        r.raise_for_status()
        d = r.json()
    finally:
        if client is None:
            c.close()
    say_terms = say_terms or {}
    turns = []
    for t in d.get("transcript", []):
        meta = t.get("meta") or {}
        turns.append({"who": t["who"], "text": t["text"], "speech": t.get("speech") or "",
                      "t": t["t"], "terms": say_terms.get(meta.get("id"), [])})
    ops = [{"tool": o["tool"], "state": o["state"], "terms": o.get("terms") or {},
            "created_at": o["created_at"], "updated_at": o["updated_at"]}
           for o in d.get("operations", [])]
    msgs = [{"to": m.get("to_addr"), "body": m.get("body"), "status": m.get("status"),
             "t": m.get("created_at")} for m in d.get("messages", [])]
    call = d.get("call") or {}
    return {"call": {"id": call_id, "outcome": call.get("outcome") or ""}, "turns": turns,
            "operations": ops, "messages": msgs}


def reset_ova(base_url: str, admin_token: str = "") -> None:
    """Back to the seeded records before a run: the scenario's ``before`` for the companion app.
    The server must allow it (OVA_ALLOW_RESET=on)."""
    headers = {"x-admin-token": admin_token} if admin_token else {}
    r = httpx.post(f"{base_url.rstrip('/')}/api/admin/reset", headers=headers, timeout=10)
    r.raise_for_status()

