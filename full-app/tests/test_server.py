"""The server end to end: every surface a caller can use, with no network and no keys.

Server voice (WebRTC, Twilio Media Streams, raw PCM) runs with a scripted recognizer and the
tone voice, so these tests exercise the transports, turn-taking, barge-in, and the event
timeline, not the providers (those are tested against fakes in test_providers.py)."""
from __future__ import annotations

import base64
import json
import struct
import time
import zlib

import pytest
from fastapi.testclient import TestClient

from conftest import MONDAY_MORNING
from ova.audio import pcm_to_ulaw, silence, tone
from ova.providers import Providers
from ova.providers.stt import ScriptSTT
from ova.providers.tts import ToneTTS
from ova.runtime import Clock
from ova.store import Store
from ova.transports import twilio as tw
from ova_server.app import build_runtime, create_app
from ova_server.settings import Settings


def png_bytes() -> bytes:
    """A real 1x1 PNG."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


def make(tmp_path, providers: Providers | None = None, **kw):
    settings = Settings(data_dir=tmp_path, secret="test-secret",
                        public_url="https://ova.test", **kw)
    providers = providers or Providers()
    rt = build_runtime(settings, providers, store=Store(), clock=Clock(fixed=MONDAY_MORNING))
    return TestClient(create_app(settings, providers, rt)), rt


def talk(ws, text):
    ws.send_text(json.dumps({"type": "caller", "text": text}))


def until(ws, pred, limit=60):
    seen = []
    for _ in range(limit):
        e = json.loads(ws.receive_text())
        seen.append(e)
        if pred(e):
            return e, seen
    raise AssertionError(f"not seen in {limit} events: {seen[-5:]}")


def lines(seen):
    return [e["text"] for e in seen if e["type"] == "say"]


def test_config_says_what_can_talk(tmp_path):
    client, _ = make(tmp_path)
    c = client.get("/api/config").json()
    assert {p["id"] for p in c["packs"]} == {"claims", "river"}
    assert c["default_pack"] == "river" and c["packs"][0]["id"] == "river"  # the Knowledge Line
    assert c["voice"] == {"browser": True, "webrtc": False, "server": False}
    assert len(c["demo_signin"]) == 3
    page = client.get("/")
    assert page.status_code == 200 and "Start the call" in page.text
    assert client.get("/manifest.webmanifest").json()["short_name"] == "Knowledge Line"


def test_a_claim_by_text_with_a_photo_mid_call(tmp_path):
    client, rt = make(tmp_path, admin_token="letmein")
    with client.websocket_connect("/ws/talk") as ws:
        ws.send_text(json.dumps({"type": "start", "pack": "claims", "mode": "text"}))
        call, _ = until(ws, lambda e: e["type"] == "call")
        until(ws, lambda e: e["type"] == "state")
        for t in ["my windshield cracked this morning", "481273", "yes", "march 4 1985",
                  "no", "about 8 am", "on Lake Shore Drive", "a stone hit it", "yes"]:
            talk(ws, t)
            until(ws, lambda e: e["type"] == "state")
        talk(ws, "yes")
        _, seen = until(ws, lambda e: e["type"] == "state")
        assert any(l.startswith("Your claim is filed.") for l in lines(seen))
        upload = next(e for e in seen if e["type"] == "card" and e["kind"] == "upload")
        # say it, then send it: the text event reaches the page during the same turn
        msg = next(e for e in seen if e["type"] == "message")
        assert msg["channel"] == "sms" and msg["to"] == "0142" and "/u/" in msg["body"]
        token = upload["url"].rsplit("/", 1)[1]
        r = client.post(f"/api/links/{token}/photos",
                        files=[("files", ("a.png", png_bytes(), "image/png")),
                               ("files", ("b.png", png_bytes(), "image/png"))])
        assert r.status_code == 200 and r.json()["total"] == 2
        ack, _ = until(ws, lambda e: e["type"] == "say" and "photos" in e["text"])
        assert ack["text"].startswith("I can see two new photos on claim CL-")
        # the status page's link works, and the photo is served only to the right token
        status_tok = rt.links.token("status", upload["claim"])
        j = client.get(f"/api/links/{status_tok}").json()
        assert j["claim"]["status"] == "photos_received"
        fid = j["claim"]["photo_ids"][0]
        assert client.get(f"/api/files/{fid}?t={status_tok}").status_code == 200
        other = rt.links.token("status", "CL-198342")          # another claim's link
        assert client.get(f"/api/files/{fid}?t={other}").status_code == 403


def test_uploads_are_checked(tmp_path):
    client, rt = make(tmp_path)
    tok = rt.links.token("upload", "CL-207455")
    r = client.post(f"/api/links/{tok}/photos",
                    files=[("files", ("x.png", b"not an image at all", "image/png"))])
    assert r.status_code == 415
    assert client.get("/api/links/garbage").status_code == 404
    expired = rt.links.token("upload", "CL-207455", ttl_s=-10)
    assert client.get(f"/api/links/{expired}").status_code == 404


def test_browser_yes_before_speech_finishes_cannot_book(tmp_path):
    client, rt = make(tmp_path)
    with client.websocket_connect("/ws/talk") as ws:
        ws.send_text(json.dumps({"type": "start", "pack": "river", "mode": "browser"}))
        until(ws, lambda e: e["type"] == "state")
        for t in ["my drain is blocked", "12 Maple Street", "Jordan", "3125550142", "yes", "Wednesday"]:
            talk(ws, t)
            until(ws, lambda e: e["type"] == "state")
        talk(ws, "yes")
        _, seen = until(ws, lambda e: e["type"] == "state")
        assert any("let me read that back in full" in line for line in lines(seen))
        assert not rt.store.ops()


def test_console_and_kill_switch(tmp_path):
    client, rt = make(tmp_path, admin_token="letmein")
    assert client.get("/api/admin/overview").status_code == 401
    h = {"x-admin-token": "letmein"}
    assert client.post("/api/admin/kill", json={"pack": "claims", "on": True},
                       headers=h).json()["on"] is True
    with client.websocket_connect("/ws/talk") as ws:
        ws.send_text(json.dumps({"type": "start", "pack": "claims", "mode": "text"}))
        _, seen = until(ws, lambda e: e["type"] == "end")
        assert any("paused" in l for l in lines(seen))
    ov = client.get("/api/admin/overview", headers=h).json()
    assert ov["kill"]["claims"] is True and ov["calls"]
    d = client.get(f"/api/admin/calls/{ov['calls'][0]['id']}", headers=h).json()
    assert d["transcript"][0]["who"] == "agent"


def test_signed_in_demo_session(tmp_path):
    client, _ = make(tmp_path)
    tok = client.post("/api/demo/signin", json={"policy": "QM-730914"}).json()["token"]
    with client.websocket_connect("/ws/talk") as ws:
        ws.send_text(json.dumps({"type": "start", "pack": "claims", "mode": "text",
                                 "signin": tok}))
        until(ws, lambda e: e["type"] == "state")
        talk(ws, "where is my payment")
        _, seen = until(ws, lambda e: e["type"] == "state")
        assert any("payment of $4,850" in l for l in lines(seen))


# ---------------------------------------------------------------- the phone

def test_twilio_webhook_signature_and_twiml(tmp_path):
    client, _ = make(tmp_path, twilio_sid="AC1", twilio_token="tok")
    form = {"From": "+13125550142", "CallSid": "CA1"}
    url = "https://ova.test/twilio/voice"
    bad = client.post("/twilio/voice", data=form, headers={"x-twilio-signature": "nope"})
    assert bad.status_code == 403
    ok = client.post("/twilio/voice", data=form,
                     headers={"x-twilio-signature": tw.signature("tok", url, form)})
    assert ok.status_code == 200 and "<ConversationRelay url=\"wss://ova.test/twilio/relay\"" \
        in ok.text and "welcomeGreeting=\"River Plumbing, this is the automated" in ok.text


def test_the_phone_can_answer_as_the_claims_line(tmp_path):
    client, _ = make(tmp_path, twilio_sid="AC1", twilio_token="tok", phone_pack="claims")
    form = {"From": "+13125550142", "CallSid": "CA2"}
    ok = client.post("/twilio/voice", data=form, headers={
        "x-twilio-signature": tw.signature("tok", "https://ova.test/twilio/voice", form)})
    assert ok.status_code == 200 and "welcomeGreeting=\"This is Quillmere Mutual" in ok.text


def test_signature_is_order_free_and_tamper_evident():
    # The algorithm on Twilio's "Secure webhooks" page: HMAC-SHA1 over the URL plus the
    # sorted parameters, base64. We check its properties rather than a remembered vector.
    url = "https://ova.test/twilio/voice?pack=claims"
    a = {"CallSid": "CA1", "From": "+13125550142", "To": "+13125550100"}
    b = dict(reversed(list(a.items())))
    sig = tw.signature("tok", url, a)
    assert sig == tw.signature("tok", url, b)
    assert tw.valid_signature("tok", url, b, sig)
    assert not tw.valid_signature("tok", url, {**a, "From": "+1999"}, sig)
    assert not tw.valid_signature("other", url, a, sig)
    assert not tw.valid_signature("tok", url + "&x=1", a, sig)


def test_conversation_relay_call(tmp_path):
    client, rt = make(tmp_path)
    with client.websocket_connect("/twilio/relay") as ws:
        ws.send_text(json.dumps({"type": "setup", "callSid": "CA9", "from": "+13125550142",
                                 "customParameters": {"pack": "claims"}}))
        ws.send_text(json.dumps({"type": "prompt", "voicePrompt": "check on my claim",
                                 "last": True}))
        m = json.loads(ws.receive_text())
        assert m["type"] == "text" and m["last"] is True
        assert "policy number" in m["token"]
        ws.send_text(json.dumps({"type": "prompt", "voicePrompt": "agent", "last": True}))
        reply = json.loads(ws.receive_text())
        assert "Putting you through" in reply["token"]
        end = json.loads(ws.receive_text())
        assert end["type"] == "end" and json.loads(end["handoffData"])["reason"] == "transfer"
    r = client.post("/twilio/relay-action", data={"HandoffData": json.dumps(
        {"reason": "transfer", "number": "+13125550110"})})
    assert "<Dial>+13125550110</Dial>" in r.text


def test_relay_interrupt_marks_what_was_heard(tmp_path):
    client, rt = make(tmp_path)
    with client.websocket_connect("/twilio/relay") as ws:
        ws.send_text(json.dumps({"type": "setup", "callSid": "CA10", "from": "+1",
                                 "customParameters": {"pack": "river"}}))
        ws.send_text(json.dumps({"type": "prompt", "voicePrompt": "my drain is blocked",
                                 "last": True}))
        json.loads(ws.receive_text())
        agent = rt.calls["call-CA10"]
        last = agent.state.last_line
        ws.send_text(json.dumps({"type": "interrupt", "utteranceUntilInterrupt": "What's"}))
        ws.send_text(json.dumps({"type": "prompt", "voicePrompt": "12 Maple Street",
                                 "last": True}))
        json.loads(ws.receive_text())
        assert agent.lines[last].status == "interrupted"
        assert agent.lines[last].heard_chars == len("What's")


def ulaw_frames(pcm: bytes) -> list[str]:
    u = pcm_to_ulaw(pcm)
    return [base64.b64encode(u[i:i + 160]).decode() for i in range(0, len(u), 160)]


def test_media_streams_call_with_barge_in(tmp_path):
    stt = ScriptSTT(["my drain is blocked"])
    client, rt = make(tmp_path, Providers(stt=stt, tts=ToneTTS()), phone_mode="media")
    xml = client.post("/twilio/voice", data={"From": "+13125550142"}).text
    assert "<Stream url=\"wss://ova.test/twilio/media\"" in xml
    with client.websocket_connect("/twilio/media") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({"event": "start", "streamSid": "MZ1", "start": {
            "callSid": "CA2", "streamSid": "MZ1",
            "customParameters": {"pack": "river", "from": "+13125550142"}}}))
        # the greeting plays as media, with a mark naming its line
        m, _ = until(ws, lambda e: e.get("event") == "media", 200)
        assert m["streamSid"] == "MZ1" and base64.b64decode(m["media"]["payload"])
        # the caller talks over the greeting: a clear, then their turn is heard
        speech = tone(900, 300, 8000, 0.3) + silence(800, 8000)
        for f in ulaw_frames(speech):
            ws.send_text(json.dumps({"event": "media", "media": {"payload": f}}))
        clear, _ = until(ws, lambda e: e.get("event") == "clear", 400)
        assert clear["streamSid"] == "MZ1"
        agent = next(iter(rt.calls.values()))
        deadline = time.time() + 5
        while agent.state.turn < 1 and time.time() < deadline:
            time.sleep(0.05)
        assert agent.state.turn == 1 and stt.heard, "the turn reached the recognizer"
        greeting = [r for r in agent.lines.values()][0]
        assert greeting.status == "interrupted"
        ws.send_text(json.dumps({"event": "stop"}))


def test_webrtc_needs_server_voice(tmp_path):
    client, _ = make(tmp_path)
    r = client.post("/api/rtc/offer", json={"sdp": "x", "type": "offer", "pack": "claims"})
    assert r.status_code == 409
