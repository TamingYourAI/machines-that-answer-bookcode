"""The line's conditions, applied to the caller's audio before the agent hears it (Chapter 25:
audio, and the phone line).

A scenario's ``conditions`` may hold:

- ``noise``: words, as in the book's format. "quiet" adds nothing; anything else adds noise at a
  signal-to-noise ratio of 15 dB, or 10 dB when it says loud, street, car, or wind.
- ``snr_db``: a number, which overrides the words.
- ``codec``: "g711" sends the audio through the phone codec, 8 kHz mu-law, both ways. The phone
  surface implies it.
- ``loss``: the share of 20 ms packets lost, from 0 to 1, each replaced by silence.

The noise is generated, not recorded: pink noise, which falls off at higher frequencies as most
room noise does. Recorded noise corpora (MUSAN, DEMAND; Chapter 25) are closer to life, and a
system's own call recordings are closer still.
"""
from __future__ import annotations

import numpy as np

RATE = 16000
FRAME = RATE // 50                      # 20 ms of samples
LOUD = ("loud", "street", "car", "wind")


def snr_db(cond: dict) -> float | None:
    if "snr_db" in cond:
        return float(cond["snr_db"])
    words = str(cond.get("noise", "quiet")).lower()
    if words in ("", "quiet", "none"):
        return None
    return 10.0 if any(w in words for w in LOUD) else 15.0


def pink(n: int, rng: np.random.Generator) -> np.ndarray:
    """Pink noise by shaping white noise's spectrum to fall at 3 dB an octave."""
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    f = np.arange(len(spec))
    f[0] = 1
    spec /= np.sqrt(f)
    out = np.fft.irfft(spec, n)
    return out / (np.std(out) or 1.0)


def _g711(x: np.ndarray) -> np.ndarray:
    """Through the phone codec and back: down to 8 kHz, mu-law at 8 bits, and up again."""
    mu = 255.0
    lo = np.interp(np.arange(0, len(x), 2), np.arange(len(x)), x)
    y = np.clip(lo / 32768.0, -1, 1)
    comp = np.sign(y) * np.log1p(mu * np.abs(y)) / np.log1p(mu)
    q = np.round((comp + 1) / 2 * 255) / 255 * 2 - 1
    back = np.sign(q) * ((1 + mu) ** np.abs(q) - 1) / mu * 32768.0
    return np.interp(np.arange(len(x)) / 2, np.arange(len(back)), back)


def apply(pcm: bytes, cond: dict, rng: np.random.Generator) -> bytes:
    """The caller's speech, as the agent would receive it over this line."""
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    if len(x) == 0:
        return pcm
    if cond.get("codec") == "g711" or cond.get("surface") == "phone":
        x = _g711(x)
    snr = snr_db(cond)
    if snr is not None:
        speech = np.sqrt(np.mean(x ** 2)) or 1.0
        x = x + pink(len(x), rng) * speech / (10 ** (snr / 20))
    loss = float(cond.get("loss", 0) or 0)
    if loss > 0:
        for i in range(0, len(x), FRAME):
            if rng.random() < loss:
                x[i:i + FRAME] = 0
    return np.clip(x, -32768, 32767).astype(np.int16).tobytes()


def background(ms: int, cond: dict, rng: np.random.Generator, speech_rms: float = 3000.0) -> bytes:
    """What the line carries between the caller's words: silence when quiet, else the same noise
    at the level it has under speech."""
    n = RATE * ms // 1000
    snr = snr_db(cond)
    if snr is None:
        return bytes(2 * n)
    x = pink(n, rng) * speech_rms / (10 ** (snr / 20))
    return np.clip(x, -32768, 32767).astype(np.int16).tobytes()
