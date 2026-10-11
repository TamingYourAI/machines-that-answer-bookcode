"""Hearing adapters. Each takes one finished turn of 16-bit PCM and returns its text.

Streaming recognition with partials (and the recognizer's own endpointing) is M2; these
adapters are segment recognizers behind the turn detector, which costs the recognition time
after the caller stops (builders' Chapter 10 explains the trade).
"""
from __future__ import annotations

import asyncio
import time

from ..audio import resample, wav_bytes
from . import Transcript


class ScriptSTT:
    """Tests and demos: returns the next scripted line for each turn, whatever was said.
    Evidence class: simulated."""
    name = "script"

    def __init__(self, lines: list[str] | None = None):
        self.lines = list(lines or [])
        self.heard: list[int] = []            # bytes per turn, for assertions

    async def transcribe(self, pcm: bytes, rate: int = 16000) -> Transcript:
        self.heard.append(len(pcm))
        return Transcript(self.lines.pop(0) if self.lines else "", 1.0)


class DeepgramSTT:
    """Deepgram pre-recorded transcription (REST). Written to the docs (checked 2026-09);
    tested against a fake."""
    name = "deepgram"

    def __init__(self, key: str, model: str = "nova-3", client=None,
                 base_url: str = "https://api.deepgram.com"):
        self.key, self.model, self.client, self.base_url = key, model, client, base_url

    async def transcribe(self, pcm: bytes, rate: int = 16000) -> Transcript:
        import httpx
        t0 = time.perf_counter()
        client = self.client or httpx.AsyncClient(timeout=10)
        try:
            r = await client.post(
                f"{self.base_url}/v1/listen",
                params={"model": self.model, "smart_format": "true", "language": "en"},
                headers={"Authorization": f"Token {self.key}", "Content-Type": "audio/wav"},
                content=wav_bytes(pcm, rate))
            r.raise_for_status()
            alt = r.json()["results"]["channels"][0]["alternatives"][0]
            return Transcript(alt.get("transcript", ""), alt.get("confidence"),
                              (time.perf_counter() - t0) * 1000)
        finally:
            if self.client is None:
                await client.aclose()


class OpenAISTT:
    """OpenAI audio transcriptions (REST, multipart). Written to the docs (checked 2026-09);
    tested against a fake. Works with compatible servers through base_url."""
    name = "openai-stt"

    def __init__(self, key: str, model: str = "gpt-4o-mini-transcribe",
                 base_url: str = "https://api.openai.com", client=None):
        self.key, self.model, self.base_url, self.client = key, model, base_url, client

    async def transcribe(self, pcm: bytes, rate: int = 16000) -> Transcript:
        import httpx
        t0 = time.perf_counter()
        client = self.client or httpx.AsyncClient(timeout=15)
        try:
            r = await client.post(f"{self.base_url}/v1/audio/transcriptions",
                                  headers={"Authorization": f"Bearer {self.key}"},
                                  data={"model": self.model, "language": "en"},
                                  files={"file": ("turn.wav", wav_bytes(pcm, rate),
                                                  "audio/wav")})
            r.raise_for_status()
            return Transcript(r.json().get("text", ""), None,
                              (time.perf_counter() - t0) * 1000)
        finally:
            if self.client is None:
                await client.aclose()


class WhisperLocalSTT:
    """faster-whisper on this machine: no key, audio never leaves. The model downloads on
    first use. Batch recognition: it waits for the end of the turn. Written to the library's
    docs; not run in this repository's tests (the model host was unreachable)."""
    name = "whisper-local"

    def __init__(self, size: str = "base.en", device: str = "cpu",
                 compute_type: str = "int8"):
        self.size, self.device, self.compute_type = size, device, compute_type
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(self.size, device=self.device,
                                       compute_type=self.compute_type)
        return self._model

    def _run(self, pcm: bytes, rate: int) -> str:
        import numpy as np
        audio = np.frombuffer(resample(pcm, rate, 16000), dtype=np.int16)
        audio = audio.astype(np.float32) / 32768.0
        segments, _ = self._load().transcribe(audio, language="en", beam_size=1,
                                              vad_filter=False)
        return " ".join(s.text.strip() for s in segments).strip()

    async def transcribe(self, pcm: bytes, rate: int = 16000) -> Transcript:
        t0 = time.perf_counter()
        text = await asyncio.to_thread(self._run, pcm, rate)
        return Transcript(text, None, (time.perf_counter() - t0) * 1000)
