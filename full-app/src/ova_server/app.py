"""The HTTP and WebSocket server: one process, every surface.

  /                 the web and mobile app (a PWA): talk by browser voice, WebRTC, or typing
  /admin            the console: calls, traces, claims, texts sent, promises, kill switch
  /u/<token>        the photo upload page a text links to
  /s/<token>        a claim's status page
  /ws/talk          text and browser-voice sessions (JSON)
  /ws/audio         raw PCM sessions (the WebRTC fallback)
  /api/rtc/offer    WebRTC signaling
  /twilio/...       the phone: TwiML webhook, ConversationRelay and Media Streams sockets
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (FastAPI, File, HTTPException, Request, UploadFile, WebSocket,
                     WebSocketDisconnect)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from ova.agent import Agent
from ova.brain import ModelBrain
from ova.channels import Channels, SmtpEmail, TwilioSms
from ova.links import Links
from ova.providers import Providers, from_env
from ova.providers.llm import PHOTO_PROMPT
from ova.runtime import Runtime
from ova.store import Store
from ova.transports import twilio as tw
from ova.voice import VoiceSession
from ova_apps import all_packs

from .settings import Settings

def _web_dir() -> Path:
    """Assets ship inside the wheel and work from any current directory."""
    for cand in (os.environ.get("OVA_WEB_DIR"), Path(__file__).resolve().parent / "web"):
        if cand and (Path(cand) / "index.html").exists():
            return Path(cand)
    raise RuntimeError("Web assets are missing; reinstall open-voice-agents")


WEB = _web_dir()
IMAGE_TYPES = {b"\xff\xd8\xff": ("image/jpeg", "jpg"), b"\x89PNG": ("image/png", "png")}


def sniff_image(head: bytes) -> tuple[str, str] | None:
    for magic, kind in IMAGE_TYPES.items():
        if head.startswith(magic):
            return kind
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    if head[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftyphevc"):
        return "image/heic", "heic"
    return None


class Live:
    """A call that is up right now, and how to send it events."""

    def __init__(self, agent: Agent, send, dispatch=None):
        self.agent, self.send = agent, send
        self.dispatch = dispatch or send


class Hub:
    """Routes things that happen elsewhere (a photo uploaded, a text sent, the kill switch)
    to the live calls they concern."""

    def __init__(self, rt: Runtime):
        self.rt = rt
        self.live: dict[str, Live] = {}
        rt.channels.subscribe(self._message)

    def add(self, live: Live) -> None:
        self.live[live.agent.call_id] = live

    def remove(self, call_id: str) -> None:
        self.live.pop(call_id, None)

    async def _message(self, m) -> None:
        live = self.live.get(m.call_id or "")
        if live:
            await live.send({"type": "message", "channel": m.channel,
                             "to": m.to[-4:] if m.channel == "sms" else m.to,
                             "body": m.body, "status": m.status})

    async def external(self, pack: str, event: dict) -> int:
        n = 0
        for live in list(self.live.values()):
            if live.agent.pack.id != pack or live.agent.state.ended:
                continue
            events = await live.agent.external(event)
            if events:
                n += 1
                for e in events:
                    await live.dispatch(e)
        return n

    async def kill(self, pack: str, on: bool) -> None:
        for live in list(self.live.values()):
            if live.agent.pack.id == pack:
                await live.send({"type": "kill", "on": on})


def build_runtime(settings: Settings, providers: Providers, store: Store | None = None,
                  clock=None) -> Runtime:
    store = store or Store(settings.data_dir / "ova.sqlite3")
    sms = TwilioSms(settings.twilio_sid, settings.twilio_token, settings.twilio_from) \
        if settings.twilio_sid and settings.twilio_from else None
    email = SmtpEmail(settings.smtp_host, settings.smtp_port, settings.smtp_user,
                      settings.smtp_password, settings.smtp_from) \
        if settings.smtp_host and settings.smtp_from else None
    brain = ModelBrain(providers.chat) if providers.chat else None
    rt = Runtime(store=store, packs=all_packs(), brain=brain,
                 channels=Channels(store, sms, email),
                 links=Links(settings.secret, settings.public_url), clock=clock,
                 public_url=settings.public_url)
    for pack_id, number in settings.transfer_numbers.items():
        if number:
            key = "claims:transfer_number" if pack_id == "claims" else "river:owner_number"
            store.set_setting(key, number)
    return rt


def create_app(settings: Settings | None = None, providers: Providers | None = None,
               rt: Runtime | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    providers = providers or from_env()
    rt = rt or build_runtime(settings, providers)
    # the Knowledge Line opens on River Plumbing; any pack can be the default by setting
    default_pack = settings.default_pack if settings.default_pack in rt.packs \
        else next(iter(rt.packs))
    hub = Hub(rt)
    rtc_calls: set = set()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(rt.run_promises())
        yield
        task.cancel()
        for c in list(rtc_calls):
            await c.close()

    app = FastAPI(title="Open Voice Agents", version="0.1.0", lifespan=lifespan)
    app.state.rt, app.state.hub, app.state.settings, app.state.providers = \
        rt, hub, settings, providers
    if (WEB / "static").exists():
        app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")

    def page(name: str) -> HTMLResponse:
        return HTMLResponse((WEB / name).read_text(encoding="utf-8"),
                            headers={"Cache-Control": "no-cache"})

    # ------------------------------------------------------------ pages
    @app.get("/", response_class=HTMLResponse)
    async def index():
        return page("index.html")

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page():
        return page("admin.html")

    @app.get("/u/{token}", response_class=HTMLResponse)
    async def upload_page(token: str):
        return page("upload.html")

    @app.get("/s/{token}", response_class=HTMLResponse)
    async def status_page(token: str):
        return page("status.html")

    @app.get("/d/{token}", response_class=HTMLResponse)
    async def doc_page(token: str):
        return page("document.html")

    @app.get("/manifest.webmanifest")
    async def manifest():
        return FileResponse(WEB / "manifest.webmanifest",
                            media_type="application/manifest+json")

    @app.get("/sw.js")
    async def service_worker():
        return FileResponse(WEB / "sw.js", media_type="text/javascript",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.get("/readyz")
    async def readyz():
        return {"ok": True, "packs": list(rt.packs), "providers": providers.describe()}

    # ------------------------------------------------------------ configuration
    def webrtc_ok() -> bool:
        try:
            import aiortc  # noqa: F401
        except ImportError:
            return False
        return providers.stt is not None and providers.tts is not None

    @app.get("/api/config")
    async def config():
        demo = []
        if settings.demo_signin and "claims" in rt.packs:
            demo = [{"policy": p["number"], "name": p["holder"]["name"], "kind": p["kind"]}
                    for p in rt.packs["claims"].desk.policies()]
        return {"packs": [p.public_info() for p in rt.packs.values()],
                "default_pack": default_pack,
                "providers": providers.describe(),
                "voice": {"browser": True, "webrtc": webrtc_ok(),
                          "server": providers.stt is not None and providers.tts is not None},
                "phone": {"twilio": bool(settings.twilio_sid), "mode": settings.phone_mode},
                "ice_servers": json.loads(os.environ.get("OVA_ICE_SERVERS", "[]") or "[]"),
                "demo_signin": demo,
                "kill": {p: rt.killed(p) for p in rt.packs}}

    @app.post("/api/demo/signin")
    async def demo_signin(body: dict):
        if not settings.demo_signin:
            raise HTTPException(403, "demo sign-in is off")
        pol = rt.packs["claims"].desk.policy(body.get("policy"))
        if not pol:
            raise HTTPException(404, "no such demo policy")
        return {"token": rt.links.token("signin", pol["number"], ttl_s=12 * 3600),
                "name": pol["holder"]["name"]}

    def identity_from(token: str | None, pack: str) -> dict | None:
        if not token or pack != "claims":
            return None
        claim = rt.links.verify(token, "signin")
        if not claim:
            return None
        pol = rt.packs["claims"].desk.policy(claim["s"])
        return {"level": "signed-in", "policy": pol["number"], "first": pol["holder"]["first"],
                "kind": pol["kind"]} if pol else None

    # ------------------------------------------------------------ text and browser voice
    @app.websocket("/ws/talk")
    async def ws_talk(ws: WebSocket):
        await ws.accept()
        agent: Agent | None = None

        async def send(e: dict) -> None:
            try:
                await ws.send_text(json.dumps(e))
            except Exception:                    # noqa: BLE001 - the socket went away
                pass
        try:
            while True:
                m = json.loads(await ws.receive_text())
                t = m.get("type")
                if t == "start" and agent is None:
                    pack = m.get("pack", default_pack)
                    if pack not in rt.packs:
                        await send({"type": "error", "detail": "unknown pack"})
                        continue
                    channel = "web" if m.get("mode") == "text" else "app"
                    agent = rt.new_call(pack, channel, identity=identity_from(
                        m.get("signin"), pack))
                    if m.get("mode") == "browser":
                        agent.heard_of = lambda lid: None if (
                            lid in agent.lines and agent.lines[lid].status == "heard") else 0
                    hub.add(Live(agent, send))
                    await send({"type": "call", "id": agent.call_id, "pack": pack,
                                "mode": m.get("mode", "text")})
                    for e in await agent.begin():
                        await send(e)
                elif agent is None:
                    continue
                elif t == "caller" and m.get("text"):
                    for e in await agent.hear(m["text"], {"mode": m.get("mode")}):
                        await send(e)
                elif t == "heard":
                    agent.mark(m.get("id", ""), "heard")
                elif t == "interrupted":
                    agent.mark(m.get("id", ""), "interrupted", int(m.get("chars", 0)))
                elif t == "silence":
                    for e in await agent.silence():
                        await send(e)
                elif t == "dtmf":
                    for e in await agent.dtmf(str(m.get("digits", ""))):
                        await send(e)
                elif t == "hangup":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            if agent:
                hub.remove(agent.call_id)
                await agent.end("caller hung up" if not agent.state.ended else
                                agent.state.outcome)

    # ------------------------------------------------------------ server voice: WebRTC
    def voice_session(agent: Agent, send, out_rate: int) -> VoiceSession:
        live = Live(agent, send)
        vs = VoiceSession(agent, providers.stt, providers.tts, out_rate, send)
        live.dispatch = lambda e: vs._dispatch([e])
        hub.add(live)
        return vs

    @app.post("/api/rtc/offer")
    async def rtc_offer(body: dict):
        if not webrtc_ok():
            raise HTTPException(409, "server voice needs a hearing and a speaking provider "
                                     "(see docs/providers.md); use browser voice instead")
        from ova.transports.webrtc import OUT_RATE, WebRTCCall
        pack = body.get("pack", default_pack)
        if pack not in rt.packs:
            raise HTTPException(404, "unknown pack")
        agent = rt.new_call(pack, "webrtc", identity=identity_from(body.get("signin"), pack))
        call: WebRTCCall

        async def closed():
            hub.remove(agent.call_id)
            rtc_calls.discard(call)

        call = WebRTCCall(lambda send: voice_session(agent, send, OUT_RATE), closed)
        rtc_calls.add(call)
        ans = await call.answer(body["sdp"], body.get("type", "offer"))
        return {**ans, "call": agent.call_id}

    # ------------------------------------------------------------ server voice: raw PCM
    @app.websocket("/ws/audio")
    async def ws_audio(ws: WebSocket):
        """Binary frames: 16 kHz 16-bit mono PCM both ways. Text frames: JSON events."""
        await ws.accept()
        if providers.stt is None or providers.tts is None:
            await ws.send_text(json.dumps({"type": "error", "detail": "no server voice"}))
            await ws.close()
            return
        q = ws.query_params
        pack = q.get("pack", default_pack)
        agent = rt.new_call(pack, "app", identity=identity_from(q.get("signin"), pack))

        async def send(e: dict) -> None:
            try:
                await ws.send_text(json.dumps(e))
            except Exception:                    # noqa: BLE001
                pass

        vs = voice_session(agent, send, 16000)

        async def pump():
            import time
            t0, n = time.monotonic(), 0
            while not vs.closed:
                n += 1
                if vs.playout.busy():
                    try:
                        await ws.send_bytes(vs.read_out(20))
                    except Exception:            # noqa: BLE001
                        return
                await asyncio.sleep(max(0.0, t0 + n * 0.02 - time.monotonic()))

        async def clear():
            await send({"type": "clear"})

        vs.on_clear = clear
        await send({"type": "call", "id": agent.call_id, "pack": pack})
        await vs.start()
        pump_task = asyncio.create_task(pump())
        try:
            while True:
                m = await ws.receive()
                if m.get("bytes"):
                    await vs.feed(m["bytes"], 16000)
                elif m.get("text"):
                    c = json.loads(m["text"])
                    if c.get("type") == "hangup":
                        break
                elif m.get("type") == "websocket.disconnect":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            pump_task.cancel()
            hub.remove(agent.call_id)
            await vs.close()

    # ------------------------------------------------------------ links: photos and status
    def link_or_404(token: str, purposes: tuple[str, ...]) -> dict:
        for p in purposes:
            claim = rt.links.verify(token, p)
            if claim:
                claim["purpose"] = p
                return claim
        raise HTTPException(404, "This link has expired or is not valid.")

    def public_claim(number: str) -> dict:
        desk = rt.packs["claims"].desk
        c = desk.claim(number)
        if not c:
            raise HTTPException(404, "no such claim")
        today = rt.clock.today()
        line = desk.status_line(c, today)
        files = rt.store.files(owner=number, kind="photo")
        return {"number": c["number"], "kind": c["kind"], "loss_type": c["loss_type"],
                "loss_date": c["loss_date"], "status": c["status"],
                "status_text": line.text, "adjuster": c.get("adjuster"),
                "next": c.get("next"), "history": c.get("history", []),
                "photos": len(c.get("photos") or []),
                "photo_ids": [f["id"] for f in files]}

    @app.get("/api/links/{token}")
    async def link_info(token: str):
        claim = link_or_404(token, ("upload", "status", "docs"))
        if claim["purpose"] == "docs":
            pol = rt.packs["claims"].desk.policy(claim["s"])
            if not pol:
                raise HTTPException(404, "no such policy")
            return {"purpose": "docs", "doc": claim.get("doc", "id_card"),
                    "policy": pol["number"], "name": pol["holder"]["name"],
                    "kind": pol["kind"], "vehicle": pol.get("vehicle"),
                    "property": pol.get("property"),
                    "effective": "2026-01-01", "expires": "2027-01-01"}
        return {"purpose": claim["purpose"], "claim": public_claim(claim["s"]),
                "max_photos": settings.max_photos}

    @app.post("/api/links/{token}/photos")
    async def upload_photos(token: str, files: list[UploadFile] = File(...)):
        claim = link_or_404(token, ("upload",))
        number = claim["s"]
        desk = rt.packs["claims"].desk
        c = desk.claim(number)
        if not c:
            raise HTTPException(404, "no such claim")
        have = len(c.get("photos") or [])
        if have + len(files) > settings.max_photos:
            raise HTTPException(413, f"A claim can have up to {settings.max_photos} photos.")
        saved = []
        folder = settings.data_dir / "uploads" / number
        folder.mkdir(parents=True, exist_ok=True)
        for f in files:
            data = await f.read(settings.max_photo_bytes + 1)
            if len(data) > settings.max_photo_bytes:
                raise HTTPException(413, "Each photo can be up to 10 MB.")
            kind = sniff_image(data[:16])
            if not kind:
                raise HTTPException(415, "Photos must be JPEG, PNG, WebP, or HEIC.")
            fid = "ph-" + uuid.uuid4().hex[:12]
            path = folder / f"{fid}.{kind[1]}"
            path.write_bytes(data)
            rt.store.add_file(fid, "photo", number, str(path), kind[0], len(data),
                              {"name": f.filename or "", "source": "link"})
            saved.append((fid, data, kind[0]))
        c = desk.add_photos(number, [s[0] for s in saved], rt.clock.today())
        await hub.external("claims", {"type": "photos", "claim": number, "count": len(saved),
                                      "total": len(c["photos"])})
        if providers.vision is not None:
            for fid, data, mime in saved:
                asyncio.create_task(photo_note(fid, data, mime))
        return {"count": len(saved), "total": len(c["photos"]), "status": c["status"],
                "claim": public_claim(number)}

    async def photo_note(fid: str, data: bytes, mime: str) -> None:
        try:
            note = await providers.vision.describe_image(data, mime, PHOTO_PROMPT)
        except Exception as e:                   # noqa: BLE001 - a note is optional
            note = f"(no note: {type(e).__name__})"
        f = rt.store.file(fid)
        if f:
            rt.store.update_file_meta(fid, {**f["meta"], "note": note.strip(),
                                            "note_by": providers.vision.name,
                                            "label": "model suggestion for the adjuster"})

    @app.get("/api/files/{fid}")
    async def get_file(fid: str, request: Request, t: str = ""):
        f = rt.store.file(fid)
        if not f:
            raise HTTPException(404)
        ok = admin_ok(request)
        if not ok and t:
            claim = rt.links.verify(t, "upload") or rt.links.verify(t, "status")
            ok = bool(claim and claim["s"] == f["owner"])
        if not ok:
            raise HTTPException(403)
        return FileResponse(f["path"], media_type=f["mime"])

    # ------------------------------------------------------------ the console
    def admin_ok(request: Request) -> bool:
        if not settings.admin_token:
            return True
        got = request.headers.get("x-admin-token") or request.cookies.get("ova_admin") or \
            request.query_params.get("token", "")
        return got == settings.admin_token

    def need_admin(request: Request) -> None:
        if not admin_ok(request):
            raise HTTPException(401, "admin token required")

    @app.get("/api/admin/overview")
    async def overview(request: Request):
        need_admin(request)
        calls = rt.store.calls(40)
        return {"calls": calls, "claims": rt.store.all("claim"),
                "messages": rt.store.messages(limit=40),
                "promises": rt.store.promises(), "keep_rate": rt.promises.keep_rate(),
                "kill": {p: rt.killed(p) for p in rt.packs},
                "live": list(hub.live), "providers": providers.describe(),
                "open_console": not settings.admin_token}

    @app.get("/api/admin/calls/{call_id}")
    async def call_detail(call_id: str, request: Request):
        need_admin(request)
        c = rt.store.call(call_id)
        if not c:
            raise HTTPException(404)
        c.pop("state_json", None)
        return {"call": c, "transcript": rt.store.transcript(call_id),
                "spans": rt.store.spans(call_id), "operations": rt.store.ops(call_id),
                "messages": rt.store.messages(call_id=call_id),
                "promises": rt.store.promises(call_id=call_id)}

    @app.get("/api/admin/claims/{number}")
    async def claim_detail(number: str, request: Request):
        need_admin(request)
        c = rt.packs["claims"].desk.claim(number)
        if not c:
            raise HTTPException(404)
        return {"claim": c, "files": rt.store.files(owner=number)}

    @app.post("/api/admin/kill")
    async def kill(body: dict, request: Request):
        need_admin(request)
        pack, on = body.get("pack", default_pack), bool(body.get("on"))
        await rt.set_kill(pack, on)
        await hub.kill(pack, on)
        return {"pack": pack, "on": rt.killed(pack)}

    @app.post("/api/admin/reset")
    async def reset(request: Request):
        """Records back to the seeds, for test runs. Off unless OVA_ALLOW_RESET=on, and refused
        while a call is live, so a public demo can never be reset under a caller."""
        need_admin(request)
        if not settings.allow_reset:
            raise HTTPException(403, "reset is off; start a test server with OVA_ALLOW_RESET=on")
        if hub.live:
            raise HTTPException(409, "a call is live")
        return {"cleared": rt.reset_records()}

    @app.post("/api/admin/promises/{pid}/keep")
    async def keep(pid: str, request: Request):
        need_admin(request)
        rt.promises.keep(pid)
        return {"ok": True}

    # ------------------------------------------------------------ the phone (Twilio)
    async def twilio_form(request: Request) -> dict:
        form = dict((await request.form()).items())
        if settings.twilio_token:
            url = settings.public_url + request.url.path + (
                "?" + request.url.query if request.url.query else "")
            if not tw.valid_signature(settings.twilio_token, url, form,
                                      request.headers.get("x-twilio-signature", "")):
                raise HTTPException(403, "bad signature")
        return form

    def ws_base() -> str:
        return settings.public_url.replace("https://", "wss://").replace("http://", "ws://")

    @app.post("/twilio/voice")
    async def twilio_voice(request: Request, pack: str = ""):
        form = await twilio_form(request)
        pack = pack or settings.phone_pack
        if pack not in rt.packs:
            raise HTTPException(404)
        params = {"pack": pack, "from": form.get("From", "")}
        mode = settings.phone_mode
        if mode == "media" and (providers.stt is None or providers.tts is None):
            mode = "relay"
        if mode == "media":
            xml = tw.twiml_stream(f"{ws_base()}/twilio/media", params)
        else:
            xml = tw.twiml_relay(f"{ws_base()}/twilio/relay", rt.packs[pack].brief.greeting,
                                 f"{settings.public_url}/twilio/relay-action", params)
        return Response(xml, media_type="application/xml")

    @app.post("/twilio/relay-action")
    async def twilio_relay_action(request: Request):
        form = await twilio_form(request)
        try:
            data = json.loads(form.get("HandoffData") or "{}")
        except json.JSONDecodeError:
            data = {}
        if data.get("reason") == "transfer" and data.get("number"):
            return Response(tw.twiml_dial(data["number"]), media_type="application/xml")
        if data.get("reason") == "transfer":
            return Response(tw.twiml_say_hangup(
                "No one can take the call on this line right now. Please call back during "
                "opening hours."), media_type="application/xml")
        return Response(tw.twiml_say_hangup(""), media_type="application/xml")

    @app.websocket("/twilio/relay")
    async def twilio_relay(ws: WebSocket):
        await ws.accept()
        state: dict = {}

        async def send(m: dict) -> None:
            await ws.send_text(json.dumps(m))

        def make_agent(setup: dict) -> Agent:
            custom = setup.get("customParameters") or {}
            pack = custom.get("pack", settings.phone_pack)
            a = rt.new_call(pack if pack in rt.packs else default_pack, "phone",
                            setup.get("from", ""), call_id=f"call-{setup.get('callSid', '')}"
                            if setup.get("callSid") else None)
            state["agent"] = a
            hub.add(Live(a, lambda e: asyncio.sleep(0), relay_dispatch))
            return a

        async def relay_dispatch(e: dict) -> None:
            await call._emit([e])

        call = tw.RelayCall(make_agent, send)
        try:
            while True:
                await call.handle(json.loads(await ws.receive_text()))
        except WebSocketDisconnect:
            pass
        finally:
            a = state.get("agent")
            if a:
                hub.remove(a.call_id)
                await a.end("caller hung up" if not a.state.ended else a.state.outcome)

    @app.websocket("/twilio/media")
    async def twilio_media(ws: WebSocket):
        await ws.accept()

        async def send(m: dict) -> None:
            await ws.send_text(json.dumps(m))

        def make_session(start: dict, send_event) -> VoiceSession:
            custom = start.get("customParameters") or {}
            pack = custom.get("pack", settings.phone_pack)
            agent = rt.new_call(pack if pack in rt.packs else default_pack, "phone",
                                custom.get("from", ""))
            return voice_session(agent, send_event, 8000)

        async def transfer(call_sid: str, e: dict) -> None:
            if settings.twilio_sid and e.get("number") and call_sid:
                await tw.redirect_call(settings.twilio_sid, settings.twilio_token, call_sid,
                                       tw.twiml_dial(e["number"]))

        call = tw.MediaStreamCall(make_session, send, transfer)
        try:
            while True:
                await call.handle(json.loads(await ws.receive_text()))
        except WebSocketDisconnect:
            pass
        finally:
            if call.session:
                hub.remove(call.session.agent.call_id)
            await call.close()

    return app


def dev_app() -> FastAPI:
    """For `uvicorn ova_server.app:dev_app --factory`."""
    return create_app()
