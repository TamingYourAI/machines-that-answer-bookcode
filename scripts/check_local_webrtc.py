"""Browser WebRTC + real local models with a synthetic microphone file.

Requires scripts/check_local_voice.py to have generated caller-1.wav. This checks
received audio packets, recognition, and the reply; it does not test physical devices.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import wave

from ova.audio import resample, silence, wav_bytes
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=Path("models"))
    parser.add_argument("--caller", type=Path,
                        default=Path("test-results/local-voice/caller-1.wav"))
    parser.add_argument("--output", type=Path, default=Path("test-results/local-webrtc"))
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.caller), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        pcm = resample(w.readframes(w.getnframes()), w.getframerate(), 48000)
    # Let the opening line finish; keep the fake microphone quiet after the request.
    mic = out / "mic.wav"
    mic.write_bytes(wav_bytes(silence(14000, 48000) + pcm + silence(30000, 48000), 48000))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as data, (out / "server.log").open("w") as log:
        env = {**os.environ, "OVA_DATA_DIR": data, "OVA_PUBLIC_URL": base,
               "OVA_ICE_SERVERS": "[]"}
        server = subprocess.Popen([sys.executable, "-m", "ova_server.cli", "serve",
                                   "--profile", "local", "--models", str(args.models.resolve()),
                                   "--port", str(port)], env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError(f"Server exited; inspect {out / 'server.log'}")
                try:
                    with urllib.request.urlopen(base + "/healthz", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Server did not become healthy")
            with sync_playwright() as p:
                browser = p.chromium.launch(args=["--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                    f"--use-file-for-fake-audio-capture={mic}",
                    "--autoplay-policy=no-user-gesture-required"])
                page = browser.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                # Collect actual RTP receive statistics, independently of displayed text.
                page.add_init_script("""
                window.__peers = [];
                const Peer = window.RTCPeerConnection;
                window.RTCPeerConnection = class extends Peer {
                  constructor(...args) { super(...args); window.__peers.push(this); }
                };
                """)
                page.goto(base + "/?pack=river")
                page.wait_for_selector("#pack option", state="attached")
                page.click('#modes .chip[data-mode="webrtc"]')
                page.click("#talk")
                page.wait_for_function("[...document.querySelectorAll('.turn.agent')]"
                    ".some(n => n.innerText.includes('address'))", timeout=60000)
                page.wait_for_function("document.querySelector('.latency')", timeout=15000)
                inbound = page.evaluate("""async () => {
                  const stats = await window.__peers[0].getStats();
                  return [...stats.values()].filter(s => s.type === 'inbound-rtp'
                    && s.kind === 'audio').map(s => ({packetsReceived: s.packetsReceived,
                      bytesReceived: s.bytesReceived}));
                }""")
                callers = page.locator(".turn.caller").all_inner_texts()
                report = {"evidence_class": "live laboratory", "passed": True,
                    "boundary": "Chromium fake microphone -> WebRTC -> Whisper -> core -> Kokoro -> RTP",
                    "physical_microphone": False, "human_listening": False,
                    "caller": callers, "agent": page.locator(".turn.agent").all_inner_texts(),
                    "inbound_audio": inbound, "page_errors": errors}
                assert any("drain" in line.lower() for line in callers), callers
                assert inbound and inbound[0]["packetsReceived"] > 0, inbound
                assert not errors, errors
                page.screenshot(path=str(out / "local-webrtc.png"))
                page.click("#talk")
                browser.close()
                (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps(report, indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
