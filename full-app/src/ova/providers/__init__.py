"""Providers: hearing (STT), speaking (TTS), and the language model, behind small contracts.

Each adapter is labeled in docs/providers.md as tested here, tested against a fake, or written
to the docs. Choose them with environment variables (see `from_env`); nothing is required. With
no keys the web app uses the browser's own recognition and voice, and the phone uses Twilio
ConversationRelay, so the agent still talks.

Contracts, all 16-bit mono PCM:

  STT.transcribe(pcm, rate) -> Transcript          one finished turn
  TTS.stream(text) -> async iterator of PCM chunks  at TTS.rate, first chunk as early as possible
  ChatModel.complete(system, user) -> str            used only by ova.brain.ModelBrain
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass
class Transcript:
    text: str
    confidence: float | None = None
    ms: float = 0.0
    language: str | None = None


class STT(Protocol):
    name: str

    async def transcribe(self, pcm: bytes, rate: int = 16000) -> Transcript:
        ...


class TTS(Protocol):
    name: str
    rate: int

    def stream(self, text: str) -> AsyncIterator[bytes]:
        ...


@dataclass
class Providers:
    stt: STT | None = None
    tts: TTS | None = None
    chat: object | None = None
    vision: object | None = None
    notes: list[str] = field(default_factory=list)

    def describe(self) -> dict:
        return {"stt": getattr(self.stt, "name", None), "tts": getattr(self.tts, "name", None),
                "llm": getattr(self.chat, "name", None),
                "vision": getattr(self.vision, "name", None), "notes": self.notes}


def from_env(env: dict | None = None) -> Providers:
    """Build providers from environment variables. Unknown or missing keys leave a layer
    empty; the notes say why, for the console."""
    e = dict(os.environ if env is None else env)
    p = Providers()
    stt = e.get("OVA_STT", "").lower()
    if not stt:
        stt = "deepgram" if e.get("DEEPGRAM_API_KEY") else \
            "openai" if e.get("OPENAI_API_KEY") else ""
    if stt == "deepgram" and e.get("DEEPGRAM_API_KEY"):
        from .stt import DeepgramSTT
        p.stt = DeepgramSTT(e["DEEPGRAM_API_KEY"], e.get("OVA_DEEPGRAM_MODEL", "nova-3"))
    elif stt == "openai" and e.get("OPENAI_API_KEY"):
        from .stt import OpenAISTT
        p.stt = OpenAISTT(e["OPENAI_API_KEY"], e.get("OVA_OPENAI_STT_MODEL",
                                                     "gpt-4o-mini-transcribe"),
                          e.get("OPENAI_BASE_URL", "https://api.openai.com"))
    elif stt == "script":                   # demos and browser tests only: simulated
        from .stt import ScriptSTT
        p.stt = ScriptSTT([x.strip() for x in e.get("OVA_STT_SCRIPT", "").split("|")
                           if x.strip()])
        p.notes.append("hearing is scripted (simulated), not recognition")
    elif stt == "whisper":
        from .stt import WhisperLocalSTT
        p.stt = WhisperLocalSTT(e.get("OVA_WHISPER_MODEL", "base.en"))
    elif stt and stt != "none":
        p.notes.append(f"hearing: {stt} needs its key")

    tts = e.get("OVA_TTS", "").lower()
    if not tts:
        tts = "elevenlabs" if e.get("ELEVENLABS_API_KEY") else \
            "deepgram" if e.get("DEEPGRAM_API_KEY") else \
            "openai" if e.get("OPENAI_API_KEY") else ""
    if tts == "elevenlabs" and e.get("ELEVENLABS_API_KEY"):
        from .tts import ElevenLabsTTS
        p.tts = ElevenLabsTTS(e["ELEVENLABS_API_KEY"],
                              e.get("OVA_ELEVENLABS_VOICE", "21m00Tcm4TlvDq8ikWAM"),
                              e.get("OVA_ELEVENLABS_MODEL", "eleven_flash_v2_5"))
    elif tts == "deepgram" and e.get("DEEPGRAM_API_KEY"):
        from .tts import DeepgramTTS
        p.tts = DeepgramTTS(e["DEEPGRAM_API_KEY"], e.get("OVA_DEEPGRAM_VOICE",
                                                         "aura-2-thalia-en"))
    elif tts == "openai" and e.get("OPENAI_API_KEY"):
        from .tts import OpenAITTS
        p.tts = OpenAITTS(e["OPENAI_API_KEY"], e.get("OVA_OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
                          e.get("OVA_OPENAI_VOICE", "alloy"),
                          e.get("OPENAI_BASE_URL", "https://api.openai.com"))
    elif tts == "kokoro":
        from .tts import KokoroTTS
        p.tts = KokoroTTS(e.get("OVA_KOKORO_MODEL", "kokoro-v1.0.onnx"),
                          e.get("OVA_KOKORO_VOICES", "voices-v1.0.bin"),
                          e.get("OVA_KOKORO_VOICE", "af_heart"))
    elif tts == "piper" and e.get("OVA_PIPER_URL"):
        from .tts import PiperHttpTTS
        p.tts = PiperHttpTTS(e["OVA_PIPER_URL"])
    elif tts == "tones":
        from .tts import ToneTTS
        p.tts = ToneTTS()
    elif tts and tts != "none":
        p.notes.append(f"speaking: {tts} needs its key or URL")

    llm = e.get("OVA_LLM", "").lower()
    model = e.get("OVA_LLM_MODEL", "")
    if llm and not model:
        p.notes.append("language model: set OVA_LLM_MODEL to a current, fast model id")
    elif llm == "anthropic" and e.get("ANTHROPIC_API_KEY"):
        from .llm import AnthropicChat
        p.chat = AnthropicChat(e["ANTHROPIC_API_KEY"], model,
                               e.get("OVA_ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    elif llm in ("openai", "ollama", "openai-compatible"):
        from .llm import OpenAIChat
        base = e.get("OVA_LLM_BASE_URL") or ("http://localhost:11434" if llm == "ollama"
                                             else "https://api.openai.com")
        p.chat = OpenAIChat(e.get("OPENAI_API_KEY", "none"), model, base)
    elif llm:
        p.notes.append(f"language model: {llm} needs its key")
    if p.chat is not None and e.get("OVA_VISION", "on") != "off":
        p.vision = p.chat
    return p
