"""The text runner: the caller's words arrive as text over a WebSocket. Fast and cheap, it tests the
agent's decisions and records, never its ears or its voice. Evidence class: simulated.

The protocol (the companion app's ``/ws/talk``; any system can expose the same):

    caller -> {"type": "start", "mode": "text", "pack": "<line>"}
    agent  -> {"type": "call", "id": "<call id>"}
    agent  -> {"type": "say", "id": "<line id>", "text": "...", "terms": [...]}   (one per line)
    caller -> {"type": "heard", "id": "<line id>"}       (each line read, so it counts as heard)
    caller -> {"type": "caller", "text": "..."}
    agent  -> {"type": "end" | "transfer", ...}           (the call is over)
    caller -> {"type": "hangup"}
"""
from __future__ import annotations

import asyncio
import json
import time

import websockets

from ..scenarios import Caller, Scenario
from . import RunResult

QUIET = 0.35          # seconds without an event that end the agent's turn in text


def ws_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://") + path


async def _agent_turn(ws, out: RunResult, first_wait: float) -> tuple[list[str], bool]:
    """Collect the agent's turn: every event until it goes quiet. Each line is acknowledged as
    heard. Returns the lines said and whether the call has ended."""
    lines, ended, wait = [], False, first_wait
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=wait)
        except asyncio.TimeoutError:
            return lines, ended
        except websockets.ConnectionClosed:
            return lines, True
        e = json.loads(raw)
        e["_t"] = time.time()
        out.events.append(e)
        t = e.get("type")
        if t == "call":
            out.call_id = e.get("id", "")
        elif t == "say":
            lines.append(e.get("text", ""))
            out.say_terms[e.get("id")] = e.get("terms", [])
            await ws.send(json.dumps({"type": "heard", "id": e.get("id")}))
        elif t in ("end", "transfer"):
            ended = True
        wait = QUIET


async def run(base_url: str, sc: Scenario, max_turns: int = 20, timeout: float = 120) -> RunResult:
    out = RunResult(sc.id, "text")
    caller = Caller(sc)

    async def talk():
        async with websockets.connect(ws_url(base_url, "/ws/talk")) as ws:
            await ws.send(json.dumps({"type": "start", "mode": "text", "pack": sc.pack}))
            lines, ended = await _agent_turn(ws, out, first_wait=10)
            for _ in range(max_turns):
                if ended:
                    break
                turn = caller.reply(lines)
                if turn is None:
                    break
                out.caller_turns.append(turn.text)
                await ws.send(json.dumps({"type": "caller", "text": turn.text}))
                lines, ended = await _agent_turn(ws, out, first_wait=10)
            try:
                await ws.send(json.dumps({"type": "hangup"}))
            except websockets.ConnectionClosed:
                pass

    try:
        await asyncio.wait_for(talk(), timeout=timeout)
    except Exception as e:                   # noqa: BLE001 - a failed run is a result
        out.error = f"{type(e).__name__}: {e}"
    await asyncio.sleep(0.3)                 # let the system write the call's outcome
    return out
