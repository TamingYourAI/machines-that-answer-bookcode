# Delivery contract: 0.3.2

**VERIFIABLE, high confidence:** the source and tests implement the delivered rows below.
Untested deployment behavior remains unknown.

| Capability | Delivered | Boundary |
| --- | --- | --- |
| River Plumbing, the Knowledge Line (default) | Appointment and fee confirmation, booking, knowledge, the gas safety script, transfer/callback paths, as the book's Appointment Line | Local calendar, no external scheduling vendor |
| Claims, second showcase | Policy questions, synthetic verification, first notice of loss, photos, status, document outbox, transfer/callback records | Local systems of record; no insurer integration |
| Kill switch | Per line or every line, from the console; new calls, and calls in progress at their next turn, hear one fixed line and go to the line's person: River Plumbing's owner at any hour. A confirmed write the switch finds not yet started is refused, as in the book's emergency stop | Switch state in the local store; carrier-level forwarding untested |
| Loop detection | When the agent's whole turn is the same three times running, it says so and offers a person (builders' Chapter 18) | Exact repeats only; a loop that varies its words is not caught |
| Test suite (`evals/`) | Appendix M scenarios run against any system on the text or audio protocol: noise, the phone codec and lost packets on the caller's audio; outcomes read from the system's records; task and experience families apart, with Wilson intervals | Records read through the companion's console API; no phone runner yet; synthetic caller, never field evidence |
| Per-turn stage timings | Server voice records the wait for end of turn, hearing, thinking, first audio and voice to voice for each turn, the stages Chapter 1's lab times | Server-side estimate, not the caller's handset; browser voice is not timed this way |
| Web/mobile UI | Responsive PWA, typing, browser and server voice, uploads, status, admin timeline | Chromium exercised; no physical-phone or screen-reader audit |
| Local speech | Actual Whisper/Kokoro inference and a WebRTC audio exchange | Synthetic caller; physical listening unverified; segment STT |
| Browser speech | Listening, speaking, interruption control and completion acknowledgments | Automated test replaces speech APIs; actual recognition service and microphone unverified |
| Business writes | UUID operation IDs, subject/terms/pack binding, durable replay, bounded reconciliation, same-process retry serialization | Caller must retain operation ID; no authenticated call-resume UI; one process |
| Confirmation | Terms checked against proposal, epoch, age and available playback evidence | WebRTC/PCM completion is a server playout estimate, not device playback or comprehension |
| Twilio Media Streams | Audio then mark; returned marks acknowledge playout; cleared marks cannot count as heard | Simulated messages; no carrier call |
| ConversationRelay | Setup, turns, interruption and transfer adapter | Simulated messages; no carrier call |
| SMS/email | Default outbox, Twilio SMS and SMTP adapters | Fake SMS provider tests; live delivery unverified |
| Images | Signed upload links, file checks, claim association, mid-call acknowledgment | No tested damage assessment; optional vision adapter uses fakes |
| Identity | Synthetic policy verification and demo sign-in | Not the full Chapter 20 token exchange, SSO or workload identity chain |
| Handoff | Routing/context records, transfer events, callback deadline tracking | No real contact-center acceptance receipt; event is not a person answering |
| Persistence | SQLite, transcripts, operations, files, messages and promises | No multi-process ledger lock, Postgres, retention job or complete recovery workflow |
| Service Line / Disruption Desk | Isolated lab scenarios, and Interlude B's assembled slice as a lab | No integrated application packs |
| Native speech-to-speech | Chapter 13 simulation | No integrated S2S adapter |
| Machine callers / A2A | Chapter 22 simulation | No public delegated-agent endpoint |
| Load / production operations | Relevant lab mechanisms and original plan | No capacity, SLA, field-effectiveness or production-readiness claim |

## Chapter availability

Builders' **Chapters 1 to 29, Interludes A and B, and Appendix M** have separate runnable
labs, synced from the book with `scripts/sync_labs.py`. The [manifest](../chapters/manifest.json)
maps each to related application files. Related does not mean the application implements
every mechanism taught by a lab. Leaders' chapters are prose and worksheets, not an
executable code track.

`full-app/PLAN.md` and `REQUIREMENTS.md` preserve the broader M1-M3 ambition. This table and
the [validation record](validation.md) describe the actual release.
