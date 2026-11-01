# Delivery contract: 0.3.3

*Machines That Answer* is a blueprint with working parts, and this contract says which parts
work. The book's Chapter 1 summarizes it in Table 1.7; this file is the full delivery matrix,
kept current with each release. Each capability the book promises is marked one of four ways.
**Implemented** means the Knowledge Line app does it. **Simulated** means a chapter's lab shows
the mechanism on stand-ins. **Documented** means the book teaches it and nothing here runs it
yet, and **out of scope** means neither does.

Implemented never means proven on a business's own line. The evidence column says what was run,
and when; the [validation record](validation.md) gives each run in full.

**VERIFIABLE, high confidence:** the source and tests implement the rows marked implemented, and
the labs the rows marked simulated. Untested deployment behavior remains unknown.

## Install the Knowledge Line app

The app runs on Python 3.12, because its local speech libraries stop there. It installs from a
clone of this repository, at its root:

```sh
git clone https://github.com/TamingYourAI/machines-that-answer-bookcode
cd machines-that-answer-bookcode
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e './full-app[all]' -c full-app/requirements.lock
ova serve --profile browser
```

The app is at http://127.0.0.1:8080. It opens on River Plumbing's Appointment Line, and its
second line, an insurance-claims demonstration, is at `/?pack=claims`. The
[README](../README.md#start-the-knowledge-line) gives a first call to try, and
[local voice](local-voice.md) the setup for local speech. The labs need no installation (the
book's Appendix A).

## The delivery matrix

*Table 1. What the book and this repository deliver, as of release 0.3.3.*

| Capability | Status | Delivered | Boundary | Evidence, and date |
| --- | --- | --- | --- | --- |
| **River Plumbing's Appointment Line**, the Knowledge Line's default (Interlude A) | Implemented | The Appointment Line end to end: the fee read and confirmed before booking, booking, a confirmation text, knowledge, the gas safety script, transfer to the owner and callback paths | Local calendar, no external scheduling vendor | The app's tests and a browser run; a six-turn call through real local speech, 2026-10-04 |
| **Claims**, the second showcase | Implemented | Policy questions, synthetic verification, first notice of loss, photos, status, document outbox, transfer/callback records | Local systems of record; no insurer integration | A typed claim in Chromium, and ten caller turns through real local speech, 2026-10-04 |
| **The kill switch** (Chapter 27; Interlude A) | Implemented | Per line or every line, from the console. New calls switch at once, and calls in progress at their next turn; they hear one fixed line and go to the line's person: River Plumbing's owner at any hour. A confirmed write the switch finds not yet started is refused, as in Chapter 27's emergency stop, and one already running completes and is read back | Switch state in the local store; carrier-level forwarding untested | The app's tests, 2026-10-04 |
| **Loop detection** (Chapter 18) | Implemented | When the agent's whole turn is the same three times running, it says so and offers a person | Exact repeats only; a loop that varies its words is not caught | A regression test and scenario `or-03`, 2026-10-11 |
| **The test suite**, [`evals/`](../evals/README.md) (Chapter 25; the book's Appendix K) | Implemented | The book's Appendix K scenarios run against any system on the text or audio protocol: noise, the phone codec and lost packets on the caller's audio; outcomes read from the system's records; task and experience families apart, with Wilson intervals | Records read through the companion's console API; no phone runner yet; synthetic caller, never field evidence | The suite's 14 tests, and text and audio runs on the app, 2026-10-11 |
| **Per-turn stage timings** (Chapter 1) | Implemented | Server voice records the wait for end of turn, hearing, thinking, first audio and voice to voice for each turn, the stages Chapter 1's lab times | Server-side estimate, not the caller's handset; browser voice is not timed this way | One synthetic WebRTC run, 2026-10-04 |
| **Three launch options**: browser, local, configured (Chapter 6) | Implemented | `ova serve --profile`. `local` is Chapter 6's local profile with the rules thinking; `configured` builds a managed cascade from the providers named | Chapter 6's third profile, speech-to-speech, has no adapter (below) | The app's tests, 2026-10-04 |
| **Web and mobile UI, with browser talk** (Chapters 8 and 9) | Implemented | Responsive PWA: typing, browser voice, and server voice over WebRTC; uploads, status, admin timeline | Chromium exercised; no physical-phone or screen-reader audit | Chromium with scripted speech and a fake microphone, 2026-10-04; no physical microphone |
| **Browser speech** | Implemented | Listening, speaking, interruption control and completion acknowledgments | Automated test replaces speech APIs; actual recognition service and microphone unverified | Scripted speech stand-ins in Chromium, 2026-10-04 |
| **Local speech, with no service** (Chapters 10 and 12) | Implemented | Actual Whisper/Kokoro inference (faster-whisper and Kokoro ONNX) and a WebRTC audio exchange | Synthetic caller; physical listening unverified; segment STT | Live laboratory with a synthetic caller, 2026-10-04; the test suite's audio runs, 2026-10-11 |
| **Business writes**: one operation id per yes, stored with each calendar booking (Chapter 17) | Implemented | UUID operation IDs, subject/terms/pack binding, durable replay, bounded reconciliation, same-process retry serialization | Caller must retain operation ID; no authenticated call-resume UI; one process | The app's tests, including replay and reconciliation, 2026-10-04 |
| **Confirmation** | Implemented | Terms checked against proposal, epoch, age and available playback evidence | WebRTC/PCM completion is a server playout estimate, not device playback or comprehension | The app's tests, 2026-10-04 |
| **Card digits redacted** before a transcript is written (Chapter 23) | Implemented, in part | The app masks a card-length run within one turn; Chapter 23's redactor, which follows a number across turns, is in its lab | A number spread across turns is masked only in the lab | The app's tests, 2026-10-04 |
| **Persistence, spans, and a timeline for every call** (Chapter 26) | Implemented | SQLite: transcripts, operations, files, messages and promises; spans and a timeline for every call, in the store and the console | No multi-process ledger lock, Postgres, retention job or complete recovery workflow | The app's tests, 2026-10-04 |
| **One phone number**: Twilio Media Streams (Chapters 7 and 8) | Implemented, not proven live | Audio then mark; returned marks acknowledge playout; cleared marks cannot count as heard | Simulated messages; no carrier call | Tested against simulated messages |
| **One phone number**: ConversationRelay (Chapters 7 and 8) | Implemented, not proven live | Setup, turns, interruption and transfer adapter | Simulated messages; no carrier call | Tested against simulated messages |
| **Texts and email** | Implemented, not proven live | Default outbox, Twilio SMS and SMTP adapters | Fake SMS provider tests; live delivery unverified | Tested against a fake; written to the docs (Table 2) |
| **Images** | Implemented | Signed upload links, file checks, claim association, mid-call acknowledgment | No tested damage assessment; optional vision adapter uses fakes | A photo uploaded during a call in Chromium, 2026-10-04 |
| **Identity** (Chapter 20) | Implemented in part; the chain simulated | Synthetic policy verification and demo sign-in in the app; the identity chain and token exchange in Chapter 20's lab | Not the full Chapter 20 token exchange, SSO or workload identity chain in the app | The app's tests; lab tests, 2026-10-04 |
| **Handoff** | Implemented | Routing/context records, transfer events, callback deadline tracking | No real contact-center acceptance receipt; event is not a person answering | The app's tests, 2026-10-04 |
| **The isolated card path and the marker test** (Chapter 23) | Simulated | Chapter 23's lab | Stand-ins only | 515 lab tests on Python 3.12 to 3.14, 2026-10-04 |
| **Native speech-to-speech** (Chapter 13) | Simulated | Chapter 13's lab | No integrated S2S adapter | Lab tests, 2026-10-04 |
| **Machine callers and an agent-protocol endpoint** (Chapter 22) | Simulated | Chapter 22's lab | No public delegated-agent endpoint (Table 3) | Lab tests, 2026-10-04 |
| **The metrics record, the suite, the review, release, recovery, and care** (Chapters 24 to 29) | Simulated | The labs of Chapters 24 to 29 | Stand-ins only | Lab tests, 2026-10-04 |
| **The Service Line slice** (Interlude B) | Simulated | Isolated lab scenarios, and Interlude B's lab, assembled from Parts III to V | No integrated application pack | Lab tests, 2026-10-04 |
| **The scenario format and acceptance scenarios** (the book's Appendices K and M) | Simulated | The [`chapters/appendix-k`](../chapters/appendix-k/README.md) lab | Stand-ins only | Lab tests, 2026-10-04 |
| **The model's live timing on an endpoint** (Chapter 15) | Simulated, with a live mode | Chapter 15's lab, given an endpoint | Simulated until run on a team's own endpoint | Live laboratory when run on a team's own |
| **The internal lines**: the Colleague Line, the Van Line, Crew Recovery (Chapters 2, 20, and 21) | Documented | Blueprints in the chapters | Nothing here runs them | None |
| **The Disruption Desk at storm scale** (Chapters 27 and 28) | Documented, and simulated in parts | Chapters 27 and 28's labs model its capacity, failover, and recovery | No integrated application pack | Lab tests, 2026-10-04 |
| **A contact-center suite connector** (Chapter 8) | Documented | Chapter 8, and the adapter matrix (the book's Appendix E) | Waits until a suite is chosen (Table 3) | None |
| **Outbound calls and texts end to end** (Chapters 5 and 7) | Documented, and simulated in parts | Chapter 7's lab fences outbound calls and texts | The app places no outbound calls; its texts follow a caller's own call (Table 3) | Lab tests, 2026-10-04 |
| **Load and production operations**: several processes, a second region, field outcomes (Chapters 27 and 28) | Out of scope | Relevant lab mechanisms and the original plan; not in the book's code | No capacity, SLA, field-effectiveness or production-readiness claim | None |

The application suite ran again for 0.3.3 on 2026-10-31, with 91 tests passing, as for 0.3.2;
the container, the wheel smoke test, and the browser checks were last run for 0.3.1. The
[validation record](validation.md) gives each release's runs.

## The providers the app supports

The app's layers are swappable, and none is required: with no provider set, its rules answer
and the browser speaks. Table 2 lists each adapter with the evidence behind it. *Tested here*
means the repository's tests run it on real code. *Tested against a fake* means the requests and
the parsing are tested against a stand-in of the provider's documented interface, and never
against the service. *Written to the docs* means not run at all.

*Table 2. The app's provider adapters (release 0.3.1; adapters checked 2026-10-03).*

| Layer | Adapter | Evidence | Note |
| --- | --- | --- | --- |
| Hearing | The browser's speech recognition | Scripted speech in Chromium | The browser may send audio to an online recognizer |
| Hearing | faster-whisper 1.2.1, local | Live laboratory, synthetic caller | Recognizes a segment after the turn ends |
| Hearing | Deepgram; OpenAI transcription | Tested against a fake | Selected in the configured profile |
| Speaking | The browser's speech synthesis | Tested here, in part | Voices vary by browser |
| Speaking | Kokoro ONNX 0.6.1, local | Live laboratory, synthetic caller | No key |
| Speaking | ElevenLabs; Deepgram Aura; OpenAI speech | Tested against a fake | Selected in the configured profile |
| Speaking | A Piper sidecar | Written to the docs | Not bundled |
| Thinking | Rules only, the default | Tested here | The agent works with no model |
| Thinking | Anthropic Messages; any OpenAI-compatible server, Ollama and vLLM included | Tested against a fake | Only for what the rules cannot place, within 1.5 s |
| Transport | WebRTC, aiortc 1.15.0 | Tested here | Loopback, and Chromium with a fake microphone |
| Transport | Twilio Media Streams; ConversationRelay | Tested against simulated messages | No carrier call |
| Texts and email | Twilio SMS; SMTP | Tested against a fake; written to the docs | Without them, messages go to the demonstration outbox |

Moving a row up this table takes a test, never a sentence. A provider tested against a fake
becomes *tested here* when a test calls the service, and an implemented capability becomes field
evidence only on a business's own line, with its [evidence manifest](evidence-manifest.md). The
wider market, dated, is on the book's vendors page at tamingyourai.com (its Appendix B points
there).

## Builds left to the deploying team

Three rows of Table 1 are builds the book teaches and this repository does not ship, because
each needs something only the deploying team has: a list of customers who agreed to calls, a
partner's agent, or a contact-center suite. Table 3 says where each starts and what it must pass
before it takes a call. None of them names a provider. The app's adapters are in Table 2, and
the market, dated, is on the book's vendors page at tamingyourai.com.

*Table 3. Builds this repository leaves to the deploying team, as of release 0.3.1.*

| Build | Start from | What it must pass | Ch. |
| --- | --- | --- | --- |
| The outbound program, end to end: River Plumbing's reminders and the Service Line's promised callbacks | Chapter 5's gate, asked before every call, and Chapter 7's limits on the trunk, both in their labs. The app places no outbound calls; its texts follow a caller's own call | TRU-5: no call without consent, after an opt-out, or outside 8 am to 9 pm at the called party's location; no emergency number ever dialed; every refusal reported by reason | 5, 7, 23 |
| An agent-protocol endpoint for a booking line | Chapter 22's lab, given the team's delegation records, its calendar, and a partner's endpoint in its test environment | Machines held to proof (the book's Table E.1): a request outside its delegation refused, holds capped per customer and per platform, and a booking that waits for the customer's own yes | 17, 22 |
| A contact-center suite connector, once a suite is chosen | Chapter 8's adapter, with the adapter matrix (the book's Table E.3) filled in for that suite | The seat's contracts in the book's Table E.1: five fields on every transfer, the agent off the call when a person answers, and a disposition back, signed and applied once | 2, 8, 21 |

## Chapter availability

Builders' **Chapters 1 to 29, Interludes A and B, and Appendix K** have separate runnable
labs, synced from the book with `scripts/sync_labs.py`. The [manifest](../chapters/manifest.json)
maps each to related application files. Related does not mean the application implements
every mechanism taught by a lab. Leaders' chapters are prose and worksheets, not an
executable code track. The [traced framework](capability-framework-traced.md) maps the
capability framework's 86 checkpoints to the chapters that build them and the lab tests that
prove them.

`full-app/PLAN.md` and `REQUIREMENTS.md` preserve the broader M1-M3 ambition. This contract and
the [validation record](validation.md) describe the actual release.
