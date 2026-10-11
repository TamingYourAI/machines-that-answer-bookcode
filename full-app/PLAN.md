# Open Voice Agents: the build plan

Started 2026-09-27, after Jay asked for the full companion code (recorded in
`../guides/decisions.md`, 2026-09-27 evening). This file is the plan and the progress record for
the code phase. `REQUIREMENTS.md` is the product contract; where this plan changes it, the change
is listed under "Changes to the requirements" with its reason.

## What Jay asked for

A full working voice agent on the book's base framework, with **insurance claims** as the
showcase: questions about a policy, reporting a claim by voice (first notice of loss), photos
uploaded from a phone or the web to start the claim, and checking a claim's status. Callers reach
it from a web or mobile interface over WebRTC, or by phone. The code also carries the book's use
cases.

## The shape

```text
            web / mobile (PWA)                       phone
   browser voice | WebRTC voice | typing      Twilio ConversationRelay | Media Streams
                  \        |        /                     \          /
                   +--------------------------------------------+
                   |  transports: text WS, WebRTC (aiortc),     |
                   |  PCM WS, Twilio relay, Twilio media        |
                   +--------------------------------------------+
                   |  audio pipeline: VAD, endpointing,         |
                   |  barge-in (cancel at the transport)        |
                   |  hearing (STT)            speaking (TTS)   |
                   +--------------------------------------------+
                   |  agent core: understanding (rules, then a  |
                   |  model for leftovers), skills as data,     |
                   |  confirmation by risk, repair catalog,     |
                   |  policy gate, commitment check             |
                   +--------------------------------------------+
                   |  operations ledger (operation ids,         |
                   |  confirmation binding, reconciliation),    |
                   |  promises with deadlines, channels (text,  |
                   |  email, signed links), knowledge for the   |
                   |  ear, traces, kill switch                  |
                   +--------------------------------------------+
                     Claims Line   River Plumbing   Service Line   Disruption Desk
                     (showcase)    (complete)       (slice)        (simulation)
```

One runtime, many tenants. Each tenant is a pack: a voice brief, skills, tools, and knowledge.

## Milestones

| Milestone | Contents | Exit test | Status |
| --- | --- | --- | --- |
| M1: first working milestone | Framework core; the Claims Line (policy questions, first notice of loss, photo link and upload, status, handover, callback, documents by email); River Plumbing's Appointment Line on the same core; FastAPI server; web and mobile PWA (browser voice, WebRTC voice, typing, camera upload, status page, console); Twilio phone paths; provider adapters; tests | A caller completes a claim by voice in the browser with no keys; a photo sent through the texted link reaches the live call; the WebRTC path passes a loopback test and a browser test with a fake microphone; Twilio messages are simulated end to end | Done 2026-09-27 (see "M1 exit" below) |
| M2: the other use cases | The Knowledge Line's document upload and ingest in the console (Markdown and PDF), so an owner can ground the agent without code; Service Line slice (identity, one business action, contextual transfer with attached data, payment stub, the four acceptance scenarios); Disruption Desk (labeled simulation); the Colleague Line; streaming hearing with partials; a speech-to-speech adapter; the scenario runner and both metric families; deploy templates | Each pack's scenarios pass; the evaluation report prints both families | Planned |
| 0.4: live and public | Jay's server with HTTPS and a WebRTC relay; both lines by phone (ConversationRelay) and in the browser at line.tamingyourai.com; the claims photo described on the call; demo limits, spend cap, 24-hour deletion; Fly.io and Railway scripts. Design: `../docs/specs/2026-10-07-live-and-public-design.md` | Section 2 of the design | Designed 2026-10-07 |
| M3: hardening | Load and soak on one host; LiveKit and Pipecat adapters behind the same contracts; Telnyx twin; Postgres; OpenTelemetry export | Stated in M2's review | Planned |

The book resumes at batch 4 after M1.

## Decisions made in this phase (Jay delegated them; each can be reversed)

1. **Our own asyncio runtime on the call path, not Pipecat, for M1.** The contracts had to be ours
   anyway (REQUIREMENTS section 7), and a small runtime is testable here with no network. Counter:
   Pipecat brings dozens of provider adapters for free. Answer: each of our adapters is under 150
   lines, and a Pipecat adapter can sit behind the same contracts in M3.
2. **WebRTC terminates in the server process (aiortc), with no media server.** One process keeps
   "one click" true. The cost: strict networks need a TURN server (`OVA_ICE_SERVERS`), and one
   process holds tens of calls, not thousands. LiveKit is the M3 path for scale.
3. **Three ways to talk in the web app.** Browser voice (the browser's own recognition and voice,
   no keys, not in every browser), WebRTC voice (the server hears and speaks; needs a hearing and
   a speaking provider), and typing. The app shows which one is live.
4. **Two phone paths on one Twilio number.** ConversationRelay (Twilio hears and speaks; only a
   Twilio account is needed) and Media Streams (our hearing and speaking providers).
5. **A plain-JavaScript PWA with no build step**, instead of the TypeScript console the
   requirements proposed (section 21, still open in 26b). It installs on a phone, works offline
   for its shell, and needs no toolchain to fork.
6. **SQLite in M1**, Postgres in M3. The store is one module.
7. **Understanding is hybrid.** Rules answer first (yes, no, digits, dates, asking for a person);
   a model handles what the rules do not, when a key is set. The skills, confirmations, and
   policy gate are code and data, never a prompt. No model identifier is hard-coded for the
   language model; the operator sets `OVA_LLM_MODEL`.
8. **The insurer is invented:** Quillmere Mutual. Every policyholder, claim, and number in the
   pack is synthetic.

## Changes to the requirements

- Insurance claims joins the Knowledge Line as a flagship tenant (Jay, 2026-09-27). The
  Knowledge Line remains the Appointment Line's app.
- Photos are a channel beside the call: a signed, expiring link sent by text, or a camera button in
  the app. A photo that arrives during the call is acknowledged on the call.
- Chat is allowed as typing in the app (decision of 2026-09-27: typing and texting as a fallback
  are in scope).

## Evidence classes for the code

Every adapter is labeled in `docs/providers.md`:

- **tested here:** run in this repository's tests against real code paths;
- **tested against a fake:** the adapter's requests and parsing are tested against a local fake
  of the provider's documented API; not yet run against the live service;
- **written to the docs:** written from the provider's documentation, with the date checked.

The container this was built in could not reach Twilio, Deepgram, OpenAI, or Hugging Face, so no
live provider call has been made yet. Before print, each live adapter is run once and relabeled.

## Progress

- [x] Plan, decisions, requirements addendum
- [x] Framework core with unit tests
- [x] Claims Line pack with scenario tests
- [x] River Plumbing pack with scenario tests
- [x] Server, transports, providers
- [x] Web and mobile PWA, console
- [x] Phone paths (simulated Twilio messages; no live call yet)
- [x] Browser test with a fake microphone
- [x] Docker, compose, docs (the image was not built here: no Docker daemon; the same
  non-editable install was smoke-tested in a fresh virtualenv)

## M1 exit (2026-09-27)

What the exit test asked for, and what backs each item:

| Exit item | Result | Evidence |
| --- | --- | --- |
| A claim by voice in the browser with no keys | The whole first notice of loss runs in Chromium by typing, and by browser voice with the Web Speech API replaced by scripted stand-ins (13 caller turns, 15 lines spoken and reported heard). A real recognizer and microphone were not exercised: headless Chromium has none | `tests/browser/check_app.py`; `tests/test_claims.py` |
| A photo through the texted link reaches the live call | Yes: the agent says "I can see two new photos on claim CL-..." during the call | `tests/test_server.py`, browser check |
| WebRTC loopback and a browser with a fake microphone | Both pass, with barge-in cutting a line and reporting the characters heard | `tests/test_webrtc.py`, browser check |
| Twilio simulated end to end | ConversationRelay and Media Streams, both with barge-in, signature checks, and the transfer | `tests/test_server.py` |
| Tests | 69 pass with no network and no keys | `pytest` |

Known limits, carried to M2: segment recognition only (no streaming partials); latency
measured only for the pipeline itself (about 50 ms after the 600 ms end-of-turn wait, scripted
hearing and tone voice, one machine); no live provider or phone call made; the Service Line,
Disruption Desk, and internal lines are not built yet.
