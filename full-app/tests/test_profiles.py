from pathlib import Path
from unittest.mock import patch

import pytest

from ova.providers import from_env
from ova_server.profiles import apply_profile


@pytest.fixture(autouse=True)
def isolated_environment():
    with patch.dict("os.environ", {}, clear=True):
        yield


def test_browser_profile_cannot_accidentally_use_a_shell_provider_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "not-a-real-key")
    monkeypatch.setenv("OVA_LLM", "openai")
    monkeypatch.setenv("OVA_LLM_MODEL", "not-a-real-model")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "not-a-real-account")
    apply_profile("browser", Path("unused"))
    p = from_env()
    assert p.stt is p.tts is p.chat is p.vision is None


def test_local_profile_fails_before_serving_if_models_are_missing(tmp_path):
    with pytest.raises(ValueError, match="Local models missing"):
        apply_profile("local", tmp_path)


def test_local_profile_selects_local_models_even_with_hosted_keys(tmp_path, monkeypatch):
    for key in ("OVA_STT", "OVA_TTS", "OVA_LLM", "OVA_VISION", "HF_HUB_OFFLINE",
                "OVA_WHISPER_MODEL", "OVA_KOKORO_MODEL", "OVA_KOKORO_VOICES"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / "whisper").mkdir()
    for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin", "whisper/model.bin"):
        (tmp_path / name).touch()
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    apply_profile("local", tmp_path)
    p = from_env()
    assert p.stt.name == "whisper-local" and p.tts.name == "kokoro-local"
    assert p.chat is None and p.vision is None
