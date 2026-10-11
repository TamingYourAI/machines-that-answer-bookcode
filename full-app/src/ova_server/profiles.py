"""Explicit profiles prevent accidental selection of a hosted provider from shell keys."""
from pathlib import Path
import os


def apply_profile(name: str, models: Path) -> None:
    if name == "configured":
        return
    os.environ.update(OVA_STT="none", OVA_TTS="none", OVA_LLM="", OVA_VISION="off")
    if name == "local":
        models = models.resolve()
        required = [models / "kokoro-v1.0.onnx", models / "voices-v1.0.bin",
                    models / "whisper/model.bin"]
        if any(not p.is_file() for p in required):
            raise ValueError("Local models missing. Run scripts/setup_local.py first.")
        os.environ.update(OVA_STT="whisper", OVA_TTS="kokoro",
                          OVA_WHISPER_MODEL=str(models / "whisper"),
                          OVA_KOKORO_MODEL=str(models / "kokoro-v1.0.onnx"),
                          OVA_KOKORO_VOICES=str(models / "voices-v1.0.bin"),
                          HF_HUB_OFFLINE="1")
    # These profiles deliberately keep external messages in the demo outbox.
    for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER",
                "SMTP_HOST", "SMTP_FROM"):
        os.environ.pop(key, None)
