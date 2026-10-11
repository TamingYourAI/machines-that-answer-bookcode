"""Local speech to action to speech, using synthetic caller audio, without network access.

This is a batch laboratory check, not a microphone, WebRTC, latency or human listening test.
"""
import argparse
import asyncio
import datetime as dt
import json
import os
from pathlib import Path
import time


async def check(models, out, pack):
    from ova.audio import wav_bytes
    from ova.providers import from_env
    from ova.runtime import Clock, Runtime
    from ova_apps import all_packs
    from ova_server.profiles import apply_profile
    apply_profile("local", models)
    # Fail if any dependency attempts outbound networking during inference.
    import socket
    original_connect = socket.socket.connect

    def offline(*args, **kwargs):
        raise RuntimeError("Network attempted during local inference")

    socket.socket.connect = offline
    try:
        p = from_env()
        rt = Runtime(packs=all_packs(), clock=Clock(fixed=dt.datetime(2026, 9, 28, 10, 15)))
        agent = rt.new_call(pack, "local-laboratory", "+13125550142")
        await agent.begin()
        rows = []
        scenarios = {
            "river": ["My kitchen drain is blocked.", "12 Maple Street.",
                      "Jordan.", "Wednesday.", "Yes.", "No."],
            "claims": ["My windshield cracked this morning.", "Four eight one two seven three.",
                       "Yes.", "March fourth nineteen eighty five.", "No.",
                       "Around eight in the morning.", "On Lake Shore Drive.",
                       "A stone hit the windshield.", "Yes.", "Yes."],
        }
        for n, utterance in enumerate(scenarios[pack]):
            started = time.perf_counter()
            pcm = b"".join([chunk async for chunk in p.tts.stream(utterance)])
            recognized = await p.stt.transcribe(pcm, p.tts.rate)
            events = await agent.hear(recognized.text)
            replies = [e["speech"] for e in events if e["type"] == "say"]
            reply_audio = b"".join([chunk for line in replies async for chunk in p.tts.stream(line)])
            (out / f"caller-{n+1}.wav").write_bytes(wav_bytes(pcm, p.tts.rate))
            (out / f"agent-{n+1}.wav").write_bytes(wav_bytes(reply_audio, p.tts.rate))
            row = {"input": utterance, "recognized": recognized.text, "reply": replies,
                   "batch_seconds": round(time.perf_counter() - started, 3)}
            rows.append(row)
            print(json.dumps(row), flush=True)
        bookings = [s for s in rt.store.all("rp_slot") if s["state"] == "booked"
                    and s["booking"].get("op") != "seed"]
        passed = (len(bookings) == 1 and bookings[0]["booking"]["name"].strip(" .").lower() == "jordan"
                  if pack == "river" else rt.store.count("claim") == 4
                  and any("Your claim is filed" in line for row in rows for line in row["reply"]))
        report = {"evidence_class": "live laboratory", "pack": pack, "input": "Kokoro synthetic speech",
                  "measurement_boundary": "batch STT, core, TTS; no browser or microphone",
                  "network": "socket.connect blocked during inference", "passed": passed,
                  "bookings": len(bookings), "claim_count_including_three_seeds": rt.store.count("claim"),
                  "turns": rows,
                  "booking_records": bookings,
                  "providers": p.describe()}
        (out / "local-voice.json").write_text(json.dumps(report, indent=2) + "\n")
        if not passed:
            raise SystemExit(f"Local voice round trip did not complete the {pack} action")
    finally:
        socket.socket.connect = original_connect


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=Path("models"))
    parser.add_argument("--pack", choices=["claims", "river"], default="river")
    parser.add_argument("--output", type=Path, default=Path("test-results/local-voice"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HUB_OFFLINE"] = "1"
    asyncio.run(check(args.models, args.output, args.pack))
