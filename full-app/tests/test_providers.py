"""Provider adapters against fakes of the providers' documented APIs (httpx MockTransport).
These check the requests we send and the parsing of what comes back. They are not a live
test: see docs/providers.md for each adapter's evidence class."""
from __future__ import annotations

import json

import httpx
import pytest

from ova.brain import ModelBrain, grounded
from ova.channels import Channels, Message, TwilioSms
from ova.knowledge import Passage
from ova.nlu import Frame, SlotSpec, Understanding
from ova.providers import from_env
from ova.providers.llm import AnthropicChat, OpenAIChat
from ova.providers.stt import DeepgramSTT, OpenAISTT
from ova.providers.tts import DeepgramTTS, ElevenLabsTTS, OpenAITTS
from ova.store import Store


def fake(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_deepgram_stt_request_and_parse():
    seen = {}

    def h(req: httpx.Request):
        seen["url"], seen["auth"] = str(req.url), req.headers["authorization"]
        seen["wav"] = req.content[:4]
        return httpx.Response(200, json={"results": {"channels": [{"alternatives": [
            {"transcript": "report a claim", "confidence": 0.93}]}]}})

    t = await DeepgramSTT("k", client=fake(h)).transcribe(b"\0\0" * 1600)
    assert t.text == "report a claim" and t.confidence == 0.93
    assert seen["auth"] == "Token k" and "model=nova-3" in seen["url"] and seen["wav"] == b"RIFF"


async def test_openai_stt_multipart():
    def h(req):
        assert req.url.path == "/v1/audio/transcriptions"
        assert b'name="model"' in req.content and b"RIFF" in req.content
        return httpx.Response(200, json={"text": "yes"})
    assert (await OpenAISTT("k", client=fake(h)).transcribe(b"\0\0" * 800)).text == "yes"


@pytest.mark.parametrize("make,path,check", [
    (lambda f: ElevenLabsTTS("k", "voice1", client_factory=f), "/v1/text-to-speech/voice1/stream",
     lambda r: r.headers["xi-api-key"] == "k" and "output_format=pcm_16000" in str(r.url)),
    (lambda f: OpenAITTS("k", client_factory=f), "/v1/audio/speech",
     lambda r: json.loads(r.content)["response_format"] == "pcm"),
    (lambda f: DeepgramTTS("k", client_factory=f), "/v1/speak",
     lambda r: "encoding=linear16" in str(r.url) and "container=none" in str(r.url)),
])
async def test_tts_adapters_stream_pcm(make, path, check):
    def h(req):
        assert req.url.path == path and check(req)
        return httpx.Response(200, content=b"\1\0" * 5000)
    tts = make(lambda: fake(h))
    chunks = [c async for c in tts.stream("Hello there.")]
    assert sum(len(c) for c in chunks) == 10000 and all(len(c) % 2 == 0 for c in chunks)


async def test_anthropic_and_openai_chat():
    def ha(req):
        body = json.loads(req.content)
        assert req.headers["anthropic-version"] == "2023-06-01" and body["model"] == "m"
        return httpx.Response(200, json={"content": [{"type": "text", "text": "{}"}]})

    def ho(req):
        assert req.headers["authorization"] == "Bearer k"
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})
    assert await AnthropicChat("k", "m", client=fake(ha)).complete("s", "u") == "{}"
    assert await OpenAIChat("k", "m", client=fake(ho)).complete("s", "u") == "hi"


class ScriptedModel:
    name = "scripted"

    def __init__(self, reply: str):
        self.reply = reply

    async def complete(self, system, user, max_tokens=300):
        return self.reply


async def test_model_output_is_checked_by_the_rules():
    frame = Frame(expecting=SlotSpec("loss_date", "date_past"),
                  intents=[("report_claim", [])])
    rules = Understanding("unclear", text="the day before my birthday")
    m = ModelBrain(ScriptedModel('{"act": "value", "intent": "report_claim", "slots": '
                                 '{"loss_date": "2026-09-20", "made_up": "x"}}'))
    u = await m.understand("the day before my birthday", frame, rules)
    assert u.slots == {"loss_date": "2026-09-20"} and u.source == "model"
    bad = ModelBrain(ScriptedModel('{"act": "value", "slots": {"loss_date": "someday"}}'))
    assert (await bad.understand("x", frame, rules)).act == "unclear"


async def test_an_answer_that_states_a_number_its_source_lacks_is_rejected():
    p = [Passage("faq", "FAQ", "Call-out", "The call-out charge is sixty dollars.",
                 "The call-out charge is sixty dollars. It is taken off the bill.", 0.9)]
    assert grounded("It's sixty dollars.", p)
    assert not grounded("It's $75.", p)
    m = ModelBrain(ScriptedModel('{"answer": "It costs $75.", "sources": ["faq"]}'))
    a = await m.answer("how much", p)
    assert a.how == "model-rejected" and a.text == "The call-out charge is sixty dollars."


async def test_twilio_sms_request():
    def h(req):
        assert req.url.path == "/2010-04-01/Accounts/AC1/Messages.json"
        form = dict(x.split("=") for x in req.content.decode().split("&"))
        assert form["From"] == "%2B13125550100" and "Body" in form
        return httpx.Response(201, json={"sid": "SM1"})
    ch = Channels(Store(), sms=TwilioSms("AC1", "tok", "+13125550100", client=fake(h)))
    m = await ch.send_text("c1", "+13125550142", "hello")
    assert (m.status, m.provider_id) == ("sent", "SM1")


def test_from_env_builds_only_what_has_keys():
    assert from_env({}).describe()["stt"] is None
    p = from_env({"DEEPGRAM_API_KEY": "x", "OVA_LLM": "anthropic", "ANTHROPIC_API_KEY": "y"})
    assert p.stt.name == "deepgram" and p.tts.name == "deepgram-tts" and p.chat is None
    assert "OVA_LLM_MODEL" in " ".join(p.notes)
    p = from_env({"OVA_STT": "script", "OVA_STT_SCRIPT": "a|b", "OVA_TTS": "tones"})
    assert p.stt.name == "script" and p.stt.lines == ["a", "b"] and p.tts.name == "tones"
