"""The web app in a real browser: a claim by typing with a photo from the camera, the
texted link opened on the "phone", server voice over WebRTC with a fake microphone, and the
console. Not part of `pytest` (it needs a running server and Chromium). Run:

  tests/browser/run.sh            # starts a server with scripted hearing, then this

Screenshots land in the output folder given as the first argument.
"""
import math
import os
import struct
import sys
import wave
import zlib

from playwright.sync_api import sync_playwright

BASE = os.environ.get("OVA_BASE", "http://127.0.0.1:8089")
CHROME = os.environ.get("OVA_CHROME") or None
out = sys.argv[1] if len(sys.argv) > 1 else "."


def fixtures() -> None:
    """A fake microphone (0.8 s of a speech-level tone, then 6 s of silence, looped by
    Chrome) and a small PNG to upload."""
    rate, frames = 48000, bytearray()
    for i in range(int(rate * 0.8)):
        frames += struct.pack("<h", int(0.3 * 32767 * math.sin(2 * math.pi * 300 * i / rate)))
    frames += bytes(2 * int(rate * 6.0))
    with wave.open(f"{out}/mic.wav", "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes([200, 80, 40] * 64) for _ in range(64))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    open(f"{out}/dent.png", "wb").write(png)


fixtures()

FAKE_SPEECH = """
window.__script = ["Someone backed into my car yesterday, I need to report it",
  "four eight one two seven three", "yes", "March 4 1985", "no", "around 5 pm",
  "on Clark Street near Diversey", "a van reversed into my bumper", "yes", "no", "no", "no",
  "yes"];
window.__spoken = [];
class FakeRecognition {
  start() {
    const text = window.__script.shift();
    setTimeout(() => {
      if (text === undefined) { this.onerror && this.onerror({ error: "no-speech" }); }
      else {
        const alt = [{ transcript: text }];
        alt.isFinal = true;
        this.onresult && this.onresult({ resultIndex: 0, results: [alt] });
      }
      this.onend && this.onend();
    }, 120);
  }
  abort() {}
  stop() {}
}
window.SpeechRecognition = FakeRecognition;
window.webkitSpeechRecognition = FakeRecognition;
window.SpeechSynthesisUtterance = function (text) { this.text = text; };
const synth = {
  current: null,
  getVoices() { return []; },
  speak(u) {
    this.current = u;
    setTimeout(() => {
      u.onstart && u.onstart();
      u.onboundary && u.onboundary({ charIndex: Math.min(8, u.text.length), charLength: 1 });
      setTimeout(() => { if (!u.cancelled) { window.__spoken.push(u.text); u.onend && u.onend(); } }, 60);
    }, 10);
  },
  cancel() { if (this.current) this.current.cancelled = true; },
};
Object.defineProperty(window, "speechSynthesis", { value: synth });
"""

def agent_lines(page):
    return page.locator(".turn.agent").all_inner_texts()

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=[
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-audio-capture={out}/mic.wav", "--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(BASE + "/")
    page.wait_for_selector("#pack option", state="attached")
    page.screenshot(path=f"{out}/01-home.png", full_page=False)
    # the Knowledge Line opens on River Plumbing; the claims line is one setting away
    assert page.locator("#pack").input_value() == "river", page.locator("#pack").input_value()
    assert page.title() == "Knowledge Line", page.title()
    page.goto(BASE + "/?pack=claims")
    page.wait_for_selector("#pack option", state="attached")
    # ---- a claim by typing, with a photo from the "camera"
    page.click('#modes .chip[data-mode="text"]')
    page.click("#talk")
    page.wait_for_selector(".turn.agent")
    def say(t, wait_for=None):
        n = page.locator(".turn.agent").count()
        page.fill("#typed", t); page.press("#typed", "Enter")
        page.wait_for_function(f"document.querySelectorAll('.turn.agent').length > {n}")
        if wait_for:
            page.wait_for_function("(w) => [...document.querySelectorAll('.turn.agent')].some(n => n.innerText.includes(w))", arg=wait_for)
    for t in ["Someone backed into my car yesterday, I need to report it", "four eight one two seven three", "yes",
              "March 4 1985", "no", "around 5 pm", "on Clark Street near Diversey",
              "I was parked and a van reversed into my bumper", "yes", "no", "yes", "yes"]:
        say(t)
    say("yes", "Your claim is filed.")
    page.wait_for_selector("#upload-card")
    page.screenshot(path=f"{out}/02-claim-filed.png", full_page=False)
    page.set_input_files("#file", f"{out}/dent.png")
    page.wait_for_function("[...document.querySelectorAll('.turn.agent')].some(n => n.innerText.includes('new photo'))", timeout=10000)
    page.click("#phone-btn")
    page.wait_for_selector(".sms")
    page.screenshot(path=f"{out}/03-photo-and-texts.png", full_page=False)
    link = page.locator(".sms a").first.get_attribute("href")
    page.click("#phone-btn")
    page.click("#talk")
    # ---- the texted link, opened on the "phone"
    up = ctx.new_page()
    up.goto(link)
    up.wait_for_selector("#form:not([hidden])")
    up.screenshot(path=f"{out}/04-upload-page.png")
    up.set_input_files("#files", [f"{out}/dent.png", f"{out}/dent.png"])
    up.click("#send")
    up.wait_for_selector("#done:not([hidden])")
    up.screenshot(path=f"{out}/05-upload-done.png")
    up.click("#status-link")
    up.wait_for_selector("#body:not([hidden])")
    up.screenshot(path=f"{out}/06-status.png", full_page=True)
    # ---- server voice over WebRTC with the fake microphone (River Plumbing)
    page.goto(BASE + "/?pack=river")
    page.wait_for_selector("#pack option", state="attached")
    page.click('#modes .chip[data-mode="webrtc"]')
    page.click("#talk")
    page.wait_for_selector(".turn.agent", timeout=15000)
    page.wait_for_function("[...document.querySelectorAll('.turn.agent')].some(n => n.innerText.includes('address'))", timeout=30000)
    page.wait_for_selector(".latency", timeout=15000)
    page.screenshot(path=f"{out}/07-webrtc.png", full_page=False)
    print("agent said:", [l.replace("agent\n", "") for l in agent_lines(page)][:4])
    print("caller:", page.locator(".turn.caller").all_inner_texts()[:3])
    print("latency:", page.locator(".latency").first.inner_text().replace("\n", " | "))
    page.click("#talk")
    # ---- browser voice, with the Web Speech API replaced by scripted stand-ins (headless
    # Chromium has no recognizer). This runs the app's own listen, speak, and heard logic.
    bv = ctx.new_page()
    bv.add_init_script(FAKE_SPEECH)
    bv.goto(BASE + "/?pack=claims")
    bv.wait_for_selector("#pack option", state="attached")
    bv.click('#modes .chip[data-mode="browser"]')
    bv.click("#talk")
    bv.wait_for_function("[...document.querySelectorAll('.turn.agent')].some(n => n.innerText.includes('Your claim is filed'))", timeout=60000)
    heard = bv.evaluate("window.__spoken.length")
    print("browser voice: lines spoken", heard, "| caller turns", bv.locator(".turn.caller").count())
    bv.screenshot(path=f"{out}/09-browser-voice.png")
    bv.click("#talk")
    # ---- the console
    adm = ctx.new_page()
    adm.set_viewport_size({"width": 1280, "height": 900})
    adm.goto(BASE + "/admin")
    adm.wait_for_selector("table tr.pick")
    adm.locator("table tr.pick").first.click()
    adm.wait_for_selector("#detail:not([hidden])")
    adm.screenshot(path=f"{out}/08-console.png", full_page=True)
    print("errors:", errors)
    assert not errors, errors
    b.close()
