"""Audio plumbing: 16-bit PCM, G.711 mu-law, resampling, frames, WAV. Standard library.

Inside the runtime every sound is 16-bit little-endian mono PCM at 16 kHz. Transports convert
at the edge: a phone line is 8 kHz mu-law (G.711), WebRTC is 48 kHz Opus (decoded by aiortc).
"""
from __future__ import annotations

import array
import io
import math
import struct
import sys
import wave

RATE = 16000
FRAME_MS = 20
BYTES_PER_MS = RATE * 2 // 1000            # 32 bytes of 16 kHz PCM per millisecond

_BIAS, _CLIP = 0x84, 32635


def _ulaw_encode_sample(s: int) -> int:
    sign = 0x80 if s < 0 else 0
    if s < 0:
        s = -s
    s = min(s, _CLIP) + _BIAS
    exponent, mask = 7, 0x4000
    while exponent > 0 and not (s & mask):
        exponent -= 1
        mask >>= 1
    mantissa = (s >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def _ulaw_decode_sample(u: int) -> int:
    u = ~u & 0xFF
    sign, exponent, mantissa = u & 0x80, (u >> 4) & 0x07, u & 0x0F
    s = ((mantissa << 3) + _BIAS) << exponent
    s -= _BIAS
    return -s if sign else s


_DECODE = [_ulaw_decode_sample(i) for i in range(256)]
_ENCODE = bytes(_ulaw_encode_sample(i - 32768) for i in range(65536))


def pcm_array(pcm: bytes) -> array.array:
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def array_pcm(a: array.array) -> bytes:
    if sys.byteorder == "big":
        a = array.array("h", a)
        a.byteswap()
    return a.tobytes()


def ulaw_to_pcm(data: bytes) -> bytes:
    return array_pcm(array.array("h", (_DECODE[b] for b in data)))


def pcm_to_ulaw(pcm: bytes) -> bytes:
    return bytes(_ENCODE[s + 32768] for s in pcm_array(pcm))


def resample(pcm: bytes, src: int, dst: int) -> bytes:
    """Linear interpolation. Good enough for speech between 8, 16, 24, and 48 kHz; a
    polyphase filter would be kinder to the top octave (M3)."""
    if src == dst or not pcm:
        return pcm
    a = pcm_array(pcm)
    n = len(a)
    m = max(1, int(n * dst / src))
    out = array.array("h", bytes(2 * m))
    step = (n - 1) / max(1, m - 1) if m > 1 else 0
    for i in range(m):
        x = i * step
        j = int(x)
        f = x - j
        v = a[j] if j + 1 >= n else a[j] + (a[j + 1] - a[j]) * f
        out[i] = int(max(-32768, min(32767, v)))
    return array_pcm(out)


def rms(pcm: bytes) -> float:
    a = pcm_array(pcm)
    if not a:
        return 0.0
    return math.sqrt(sum(s * s for s in a) / len(a))


def dbfs(pcm: bytes) -> float:
    r = rms(pcm)
    return -120.0 if r <= 0 else 20 * math.log10(r / 32768)


def frames(pcm: bytes, ms: int = FRAME_MS, rate: int = RATE) -> list[bytes]:
    size = rate * 2 * ms // 1000
    return [pcm[i:i + size] for i in range(0, len(pcm), size)]


def silence(ms: int, rate: int = RATE) -> bytes:
    return bytes(rate * 2 * ms // 1000)


def tone(ms: int, hz: float = 440.0, rate: int = RATE, level: float = 0.2) -> bytes:
    n = rate * ms // 1000
    a = array.array("h", (int(level * 32767 * math.sin(2 * math.pi * hz * i / rate))
                          for i in range(n)))
    return array_pcm(a)


def wav_bytes(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def read_wav(data: bytes) -> tuple[bytes, int]:
    """(mono 16-bit PCM, rate). Stereo is mixed down."""
    with wave.open(io.BytesIO(data), "rb") as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError("16-bit WAV only")
    if ch == 2:
        a = pcm_array(raw)
        raw = array_pcm(array.array("h", ((a[i] + a[i + 1]) // 2
                                          for i in range(0, len(a) - 1, 2))))
    return raw, rate


def duration_ms(pcm: bytes, rate: int = RATE) -> float:
    return len(pcm) / (rate * 2) * 1000
