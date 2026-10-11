"""WebRTC in the server process (aiortc): the browser's microphone in, the agent's voice out,
and a data channel for events (transcript lines, cards, latency).

Signaling is one HTTP exchange: the browser posts its offer, the server answers with ICE
candidates gathered (no trickle). Behind strict NAT the browser needs a TURN server; set
OVA_ICE_SERVERS (JSON list of RTCIceServer dicts) for both sides.
"""
from __future__ import annotations

import asyncio
import fractions
import json
import os
import time
from typing import Awaitable, Callable

from ..audio import FRAME_MS
from ..voice import VoiceSession

OUT_RATE = 48000
SAMPLES = OUT_RATE * FRAME_MS // 1000       # 960 samples per 20 ms frame


def ice_servers() -> list:
    from aiortc import RTCIceServer
    raw = os.environ.get("OVA_ICE_SERVERS", "")
    if not raw:
        return []
    return [RTCIceServer(**s) for s in json.loads(raw)]


def make_agent_track(session_ref: Callable[[], VoiceSession | None]):
    from aiortc import MediaStreamTrack
    import av

    class AgentTrack(MediaStreamTrack):
        kind = "audio"

        def __init__(self) -> None:
            super().__init__()
            self._start: float | None = None
            self._ts = 0

        async def recv(self):
            if self._start is None:
                self._start = time.time()
            else:
                self._ts += SAMPLES
                wait = self._start + self._ts / OUT_RATE - time.time()
                if wait > 0:
                    await asyncio.sleep(wait)
            s = session_ref()
            pcm = s.read_out(FRAME_MS) if s else bytes(SAMPLES * 2)
            frame = av.AudioFrame(format="s16", layout="mono", samples=SAMPLES)
            frame.planes[0].update(pcm)
            frame.pts = self._ts
            frame.sample_rate = OUT_RATE
            frame.time_base = fractions.Fraction(1, OUT_RATE)
            return frame

    return AgentTrack()


class WebRTCCall:
    """One browser call. `answer(offer)` returns the SDP answer; the session starts when the
    browser's audio track arrives."""

    def __init__(self, make_session: Callable[[Callable[[dict], Awaitable[None]]],
                                              VoiceSession],
                 on_closed: Callable[[], Awaitable[None]] | None = None):
        from aiortc import RTCConfiguration, RTCPeerConnection
        self.pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers()))
        self.make_session = make_session
        self.session: VoiceSession | None = None
        self.channel = None
        self.outbox: list[str] = []
        self.on_closed = on_closed
        self.reader: asyncio.Task | None = None
        self.track = make_agent_track(lambda: self.session)
        self.pc.addTrack(self.track)
        self._closed = False

        @self.pc.on("datachannel")
        def on_datachannel(ch):
            self.channel = ch
            for m in self.outbox:
                ch.send(m)
            self.outbox.clear()

            @ch.on("message")
            def on_message(msg):
                asyncio.ensure_future(self._control(msg))

        @self.pc.on("track")
        def on_track(track):
            if track.kind == "audio" and self.reader is None:
                self.reader = asyncio.ensure_future(self._read(track))

        @self.pc.on("connectionstatechange")
        async def on_state():
            if self.pc.connectionState in ("failed", "closed", "disconnected"):
                await self.close()

    async def send(self, event: dict) -> None:
        msg = json.dumps(event)
        if self.channel is not None and self.channel.readyState == "open":
            self.channel.send(msg)
        else:
            self.outbox.append(msg)

    async def _control(self, msg: str) -> None:
        try:
            m = json.loads(msg)
        except json.JSONDecodeError:
            return
        if self.session is None:
            return
        if m.get("type") == "hangup":
            await self.close()
        elif m.get("type") == "text" and m.get("text"):
            await self.session.send_event({"type": "caller", "text": m["text"],
                                           "final": True, "typed": True})
            await self.session._dispatch(await self.session.agent.hear(m["text"],
                                                                        {"typed": True}))
        elif m.get("type") == "dtmf":
            await self.session._dispatch(await self.session.agent.dtmf(m.get("digits", "")))

    async def answer(self, sdp: str, kind: str = "offer") -> dict:
        from aiortc import RTCSessionDescription
        await self.pc.setRemoteDescription(RTCSessionDescription(sdp, kind))
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        self.session = self.make_session(self.send)
        await self.session.start()
        return {"sdp": self.pc.localDescription.sdp, "type": self.pc.localDescription.type}

    async def _read(self, track) -> None:
        import av
        from aiortc.mediastreams import MediaStreamError
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        while True:
            try:
                frame = await track.recv()
            except MediaStreamError:
                break
            if self.session is None:
                continue
            for f in resampler.resample(frame):
                await self.session.feed(bytes(f.planes[0])[: f.samples * 2], 16000)
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.session:
            await self.session.close()
        if self.reader:
            self.reader.cancel()
        await self.pc.close()
        if self.on_closed:
            await self.on_closed()
