"""ova: run the server, or talk to a pack in the terminal.

  ova serve [--host 0.0.0.0] [--port 8080]
  ova talk [--pack river|claims]    type as the caller; the agent answers in text
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def serve(host: str, port: int) -> None:
    import uvicorn
    from .app import create_app
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


async def talk(pack: str) -> None:
    from ova.runtime import Runtime
    from ova_apps import all_packs
    rt = Runtime(packs=all_packs())
    agent = rt.new_call(pack, "web", "+13125550142")

    def show(events):
        for e in events:
            if e["type"] == "say":
                print(f"  agent: {e['text']}")
            elif e["type"] == "card":
                print(f"  [card: {e['kind']}]")
            elif e["type"] == "transfer":
                print(f"  [transfer to {e['to']}: {e['summary'].get('whisper', '')}]")
            elif e["type"] == "end":
                print("  [call ended]")
    show(await agent.begin())
    while not agent.state.ended:
        try:
            line = input("you: ")
        except EOFError:
            break
        show(await agent.hear(line))
    for m in rt.store.messages():
        print(f"  [{m['channel']} to {m['to_addr']}: {m['body']}]")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="ova")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--profile", choices=["browser", "local", "configured"], default="browser")
    s.add_argument("--models", type=Path, default=Path("models"))
    s.add_argument("--env-file", type=Path)
    t = sub.add_parser("talk")
    t.add_argument("--pack", default="river")
    a = ap.parse_args(argv)
    if a.cmd == "serve":
        if a.env_file:
            from dotenv import load_dotenv
            load_dotenv(a.env_file, override=False)
        from .profiles import apply_profile
        try:
            apply_profile(a.profile, a.models)
        except ValueError as exc:
            ap.error(str(exc))
        serve(a.host, a.port)
    else:
        asyncio.run(talk(a.pack))


if __name__ == "__main__":
    main(sys.argv[1:])
