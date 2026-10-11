"""WebRTC for real, in one process: an aiortc client with a synthetic microphone calls the
server's WebRTC transport. Opus both ways, ICE on loopback, the data channel for events."""
from __future__ import annotations

import asyncio
import fractions
import json
import time

import pytest

aiortc = pytest.importorskip("aiortc")
av = pytest.importorskip("av")

from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription  # noqa: E402

from conftest import make_runtime  # noqa: E402
from ova.audio import rms, silence, tone  # noqa: E402
from ova.providers.stt import ScriptSTT  # noqa: E402
from ova.providers.tts import ToneTTS  # noqa: E402
from ova.transports.webrtc import WebRTCCall  # noqa: E402
from ova.voice import VoiceSession  # noqa: E402


class Mic(MediaStreamTrack):
    """A microphone that plays a script of 48 kHz PCM, in real time, then silence."""
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.script = bytearray()
        self.t0 = None
        self.n = 0

    def say(self, pcm48: bytes) -> None:
        self.script += pcm48

    async def recv(self):
        if self.t0 is None:
            self.t0 = time.time()
        self.n += 1
        wait = self.t0 + self.n * 0.02 - time.time()
        if wait > 0:
            await asyncio.sleep(wait)
        chunk = bytes(self.script[:1920]).ljust(1920, b"\0")
        del self.script[:1920]
        f = av.AudioFrame(format="s16", layout="mono", samples=960)
        f.planes[0].update(chunk)
        f.pts, f.sample_rate, f.time_base = self.n * 960, 48000, fractions.Fraction(1, 48000)
        return f


async def wait_for(pred, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        await asyncio.sleep(0.05)
    return False


async def test_a_call_over_webrtc_with_barge_in():
    rt = make_runtime()
    agent = rt.new_call("river", "webrtc")
    stt = ScriptSTT(["my kitchen drain is blocked"])
    call = WebRTCCall(lambda send: VoiceSession(agent, stt, ToneTTS(ms_per_char=40), 48000,
                                                send))
    client = RTCPeerConnection()
    mic = Mic()
    client.addTrack(mic)
    channel = client.createDataChannel("events")
    events: list[dict] = []
    channel.on("message", lambda m: events.append(json.loads(m)))
    heard_audio: list[float] = []

    @client.on("track")
    def on_track(track):
        async def read():
            while True:
                try:
                    f = await track.recv()
                except Exception:
                    return
                heard_audio.append(rms(bytes(f.planes[0])[: f.samples * 2 * len(f.layout.channels)]))
        asyncio.ensure_future(read())

    await client.setLocalDescription(await client.createOffer())
    ans = await call.answer(client.localDescription.sdp, client.localDescription.type)
    await client.setRemoteDescription(RTCSessionDescription(ans["sdp"], ans["type"]))

    # the greeting arrives as an event and as sound
    assert await wait_for(lambda: any(e["type"] == "say" for e in events))
    assert await wait_for(lambda: any(level > 500 for level in heard_audio)), \
        "agent audio reached the caller"
    # the caller talks over the greeting: the server cuts the line and says how much was heard
    mic.say(tone(1000, 300, 48000, 0.3) + silence(900, 48000))
    assert await wait_for(lambda: any(e["type"] == "interrupted" for e in events)), events[-3:]
    cut = next(e for e in events if e["type"] == "interrupted")
    assert agent.lines[cut["id"]].status == "interrupted"
    assert 0 <= cut["chars"] < len(agent.lines[cut["id"]].line.speech)
    # the turn is heard and answered
    assert await wait_for(lambda: any(e["type"] == "caller" for e in events))
    assert await wait_for(lambda: any(e.get("text") == "What's the address for the visit?"
                                      for e in events))
    assert stt.heard and stt.heard[0] > 16000 * 2 * 0.8      # about a second of speech
    await call.close()
    await client.close()
