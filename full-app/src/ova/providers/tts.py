"""Speaking adapters. Each streams 16-bit mono PCM at its own rate, first chunk as early as
the provider allows; the audio pipeline resamples for the transport. The text they receive is
already written for the ear (ova.speech): numbers, dates, and codes are words by then.
"""
from __future__ import annotations

import asyncio
import math
from typing import AsyncIterator

from ..audio import array_pcm, read_wav, resample


class ToneTTS:
    """A mock voice: soft tones, one per syllable-ish chunk of text, so the pipeline, barge-in,
    and WebRTC can be tested with no provider. It does not say words. Evidence class:
    simulated."""
    name = "tones"
    rate = 16000

    def __init__(self, ms_per_char: float = 55.0, chunk_ms: int = 100):
        self.ms_per_char, self.chunk_ms = ms_per_char, chunk_ms

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        import array
        total = max(200, int(len(text) * self.ms_per_char))
        n_chunk = self.rate * self.chunk_ms // 1000
        done = 0
        k = 0
        while done < total:
            hz = 220 + 60 * ((k * 7) % 5)
            a = array.array("h", (int(2400 * math.sin(2 * math.pi * hz * i / self.rate)
                                      * math.sin(math.pi * i / n_chunk))
                                  for i in range(n_chunk)))
            yield array_pcm(a)
            done += self.chunk_ms
            k += 1
            await asyncio.sleep(0)


async def _stream_http(client_factory, method: str, url: str, chunk: int = 3200,
                       **kw) -> AsyncIterator[bytes]:
    import httpx
    client = client_factory() if client_factory else httpx.AsyncClient(timeout=20)
    try:
        async with client.stream(method, url, **kw) as r:
            r.raise_for_status()
            carry = b""
            async for b in r.aiter_bytes():
                carry += b
                while len(carry) >= chunk:
                    yield carry[:chunk]
                    carry = carry[chunk:]
            if carry:
                yield carry[: len(carry) - len(carry) % 2]
    finally:
        if not client_factory:
            await client.aclose()


class OpenAITTS:
    """OpenAI speech (REST, response_format pcm: 24 kHz 16-bit mono). Written to the docs
    (checked 2026-09); tested against a fake."""
    name = "openai-tts"
    rate = 24000

    def __init__(self, key: str, model: str = "gpt-4o-mini-tts", voice: str = "alloy",
                 base_url: str = "https://api.openai.com", client_factory=None):
        self.key, self.model, self.voice, self.base_url = key, model, voice, base_url
        self.client_factory = client_factory

    def stream(self, text: str) -> AsyncIterator[bytes]:
        return _stream_http(self.client_factory, "POST", f"{self.base_url}/v1/audio/speech",
                            headers={"Authorization": f"Bearer {self.key}"},
                            json={"model": self.model, "voice": self.voice, "input": text,
                                  "response_format": "pcm"})


class ElevenLabsTTS:
    """ElevenLabs streaming speech, output_format pcm_16000. Written to the docs (checked
    2026-09); tested against a fake."""
    name = "elevenlabs"
    rate = 16000

    def __init__(self, key: str, voice_id: str, model: str = "eleven_flash_v2_5",
                 base_url: str = "https://api.elevenlabs.io", client_factory=None):
        self.key, self.voice_id, self.model, self.base_url = key, voice_id, model, base_url
        self.client_factory = client_factory

    def stream(self, text: str) -> AsyncIterator[bytes]:
        return _stream_http(
            self.client_factory, "POST",
            f"{self.base_url}/v1/text-to-speech/{self.voice_id}/stream",
            params={"output_format": "pcm_16000"}, headers={"xi-api-key": self.key},
            json={"text": text, "model_id": self.model})


class DeepgramTTS:
    """Deepgram Aura speech (REST), linear16 at 16 kHz without a container. Written to the
    docs (checked 2026-09); tested against a fake."""
    name = "deepgram-tts"
    rate = 16000

    def __init__(self, key: str, voice: str = "aura-2-thalia-en",
                 base_url: str = "https://api.deepgram.com", client_factory=None):
        self.key, self.voice, self.base_url = key, voice, base_url
        self.client_factory = client_factory

    def stream(self, text: str) -> AsyncIterator[bytes]:
        return _stream_http(self.client_factory, "POST", f"{self.base_url}/v1/speak",
                            params={"model": self.voice, "encoding": "linear16",
                                    "sample_rate": "16000", "container": "none"},
                            headers={"Authorization": f"Token {self.key}"},
                            json={"text": text})


class PiperHttpTTS:
    """A Piper HTTP server beside the app (a sidecar, so Piper's GPL stays out of this
    image). It returns a WAV file. Written to the docs; not run here."""
    name = "piper-http"
    rate = 16000

    def __init__(self, url: str, client_factory=None):
        self.url, self.client_factory = url, client_factory

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        import httpx
        client = self.client_factory() if self.client_factory else httpx.AsyncClient(
            timeout=20)
        try:
            r = await client.post(self.url, content=text.encode(),
                                  headers={"Content-Type": "text/plain"})
            r.raise_for_status()
            pcm, rate = read_wav(r.content)
            yield resample(pcm, rate, self.rate)
        finally:
            if not self.client_factory:
                await client.aclose()


class KokoroTTS:
    """Kokoro (ONNX) on this machine: Apache-licensed, no key, no network after the model
    files are downloaded. Written to the library's docs; not run here (the model host was
    unreachable)."""
    name = "kokoro-local"
    rate = 24000

    def __init__(self, model_path: str, voices_path: str, voice: str = "af_heart",
                 speed: float = 1.0):
        self.model_path, self.voices_path, self.voice, self.speed = \
            model_path, voices_path, voice, speed
        self._k = None

    def _synth(self, text: str) -> bytes:
        import numpy as np
        if self._k is None:
            from kokoro_onnx import Kokoro
            self._k = Kokoro(self.model_path, self.voices_path)
        samples, sr = self._k.create(text, voice=self.voice, speed=self.speed, lang="en-us")
        pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes()
        return resample(pcm, sr, self.rate)

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        yield await asyncio.to_thread(self._synth, text)
