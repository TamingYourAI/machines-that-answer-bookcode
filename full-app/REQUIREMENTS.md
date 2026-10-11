# Open Voice Agents requirements

**Status:** decisions locked 2026-09-20. Code started 2026-09-27; see `PLAN.md`.  
**Name:** Open Voice Agents  
**Slug:** `open-voice-agents`  
**License:** Apache-2.0  
**Date:** 2026-09-20  
**Authoring session:** Cursor Grok with Jay  
**Book spine this must honor:** `brainstorm/chapters-v6.md`  
**Related notes:** `brainstorm/use-cases-and-reference-stack.md`, `brainstorm/graded-use-cases.md`

This document is the product and engineering contract for the companion repository. The book remains a blueprint. This repository is the thing a reader can fork, run, and put a real phone number on.

---

## 1. Why this exists

The book teaches a swappable voice-agent stack: eight layers, three profiles (local, managed cascade, speech-to-speech), and three graded examples (Appointment Line, Service Line, Disruption Desk). Chapter labs stay small and mockable. That is the right teaching posture.

It is not enough as a product. A builder who finishes Chapter 9 still does not have something they can give to a plumber, a clinic, or a one-person shop on Monday. Managed platforms (Vapi, Retell, Bland, ElevenLabs Conversational AI) already sell that last mile, and they lock the stack. The gap this repository fills:

1. **A real application**, not only labs: upload documents, ground a voice agent in them, talk in the browser, optionally attach a phone number, optionally swap every layer.
2. **An open framework** under that application: the book's layer contracts as code, so the flagship app is one consumer among several, and later book examples plug into the same runtime.
3. **A companion website** that runs the same application as a public demo, so a printed QR code or a "Try it" button is not a slide. It is the product.

Jay's words, restated as acceptance criteria:

- People can fork the repo and use it.
- People can click one button and run it (local Compose, and a hosted one-click target).
- They can bring documents (and later other sources) and get RAG on top.
- The conversational voice agent comes up without writing a pipeline.
- They can plug in a phone number or any other connector (calendar, CRM, website, hours, persona).
- Local or embedded STT and TTS are first-class, and the same agent can swap to hosted STT/TTS/LLM/S2S without rewriting the dialogue.
- The companion website can showcase a live instance of the same app.

---

## 2. Relationship to the book

### 2.1 What stays true

From locked book decisions (`brainstorm/README.md`, `chapters-v6.md`):

- Every layer is **swappable**. Cascade (STT + LLM + TTS) is one profile. Speech-to-speech is another. The repository teaches the decision by making the swap a config change.
- Vendors appear as **dated examples of a layer**, never as the hero.
- Labs cover **code, mocks, fixtures, and live** providers. CI stays green on mocks and fixtures. Live paths are optional and banded.
- The three graded examples remain **blueprints**. The Appointment Line is the only one this repository promises as a complete small-scale vertical. The Service Line and Disruption Desk ship as scenario packs and contracts, not as deployable utilities or airlines.
- Never print the withheld employer name. Forbidden strings stay forbidden in this repo too.
- Voice only. Chat appears only for channel pivot (SMS/link mid-call) and after-call receipts.

### 2.2 What this document changes

The 2026-09-14 restatement said the book does not promise a shipped product. **This repository does.** That is a new product decision, not a silent override of the book.

| Artifact | Promise |
| --- | --- |
| Book chapters and labs | Blueprint + small runnable labs |
| This repository, framework | Owned layer contracts, adapters, policy, RAG-for-the-ear |
| This repository, flagship app | A complete, forkable, one-click Knowledge Line |
| Companion website | Hosted demo of that same app, plus audio gallery and deploy buttons |
| Scenario packs | Appointment Line (complete at small scale); Service Line and Disruption Desk as data and contracts |

If the two conflict, the book stays vendor-neutral in prose; the repository may pick **defaults** (see section 12) as long as the swap remains real and measured.

### 2.3 Chapter mapping (v6)

The flagship app is the object the later builder chapters talk about. Labs stay small. The app is the synthesis.

| Book part | What the repository must implement or demonstrate |
| --- | --- |
| Ch 1 atlas | Knowledge Line as the "first card"; Appointment Line as the complete simple vertical |
| Ch 2 eight layers + ruler | Contracts and metrics schema |
| Ch 4 seats | CPaaS-native first (own the number). CCaaS adapters later |
| Ch 6–8 design | Voice bible, dialogue objects, SOP compiler as data, not prose |
| Ch 9–13 stack | Transport, STT, turn-taking, TTS, all behind interfaces |
| Ch 14–18 agent | Hybrid turn loop, policy gate, RAG-for-the-ear, tools, guardrails |
| Ch 19 orchestration + swap | Adapter per provider; lock-in ledger in the repo |
| Ch 20–22 CX live | Fake CRM + optional live connectors; transfer; disclosure; PCI pause stub |
| Ch 23–24 prove | Both metric families; scenario library; traces |
| Ch 25 ship | Compose, one-click host, kill switch, cost controls |
| Ch 29 swappable future | S2S profile; A2A as a later interop, not the media path |

---

## 3. Problem, users, jobs

### 3.1 The problem

Standing up a production-shaped voice agent today forces a builder into one of three bad choices:

1. **Assemble Pipecat or LiveKit from scratch.** Powerful, weeks of glue, no document ingest, no admin, no phone wizard.
2. **Buy a managed voice-agent platform.** Fast demo, locked STT/TTS/LLM, weak local/offline story, exit cost.
3. **Run a local toy** (Whisper + Ollama + Piper in a notebook). Fine for a laptop demo, dies on barge-in, telephony, RAG freshness, and handoff.

Nobody ships the book's architecture as a product: local-first, swappable, document-grounded, phone-ready, one-click.

### 3.2 Primary users

| Persona | What they want on day one | What they want by week four |
| --- | --- | --- |
| **Solo builder / agency** (primary) | Fork, Compose up, talk in the browser, upload a PDF, hear grounded answers | Attach a Twilio/Telnyx number, swap to Deepgram + Cartesia, hand to a client |
| **Small business owner** (flagship user) | Click a website button or run a one-click deploy, drop in hours/FAQ/services, get a number that answers | Calendar booking, SMS confirmations, after-hours capture |
| **Book reader** | Run the chapter lab in mock mode with no keys | Flip the same dialogue onto the local or managed profile |
| **Companion-site visitor** | Press Talk, ask a question about the book or a sample business, hear a real agent | Click Deploy and land on their own instance |

Sponsors and contact-center leads are book readers, not v1 product users. CCaaS "front of the ACD" is a later seat.

### 3.3 Jobs to be done

1. **Stand up a voice agent from documents** in under 15 minutes on a laptop, no API keys.
2. **Attach a PSTN number** in under 30 minutes with one CPaaS account.
3. **Swap STT, TTS, or LLM** by editing config (or the admin UI), without rewriting prompts or tools.
4. **Keep the conversation on the 800 ms wall** as a design target (500 ms as the stretch), measured from the caller's device, p95, not the mean.
5. **Ground answers for the ear**: one speakable sentence plus a source id, never a paragraph dump.
6. **Escalate to a human** (owner's mobile) with context, and never loop on "agent."
7. **See what happened**: transcript, traces per layer, which document was cited, which tool ran, what the policy blocked.

### 3.4 How we know v1 is done

Observable, not vibes:

- `docker compose up` on a laptop with no cloud keys produces a browser Talk button that completes a 5-turn FAQ conversation grounded in a bundled sample corpus.
- The same compose file, with keys added, swaps STT and TTS to a hosted pair without code changes. A recorded fixture suite still passes.
- A documented Twilio or Telnyx path answers a real inbound call with the same agent.
- Uploading a 20-page PDF makes a new fact speakable within 2 minutes. Asking a question the corpus does not support produces a refusal plus an offer to take a message, not a hallucination.
- A companion-site staging deploy shows the same Talk path on a public URL.
- Chapter-lab mocks stay green in CI with no keys.

---

## 4. Goals and non-goals

### 4.1 Goals (v1)

- Own the **layer contracts** so the book, the flagship app, and later examples share one runtime.
- Ship **Knowledge Line**: document ingest → RAG-for-the-ear → voice agent on browser and phone.
- Ship **local/embedded STT + TTS + LLM** as the zero-key path.
- Ship **hosted provider swap** for STT, TTS, LLM, and (v1.1) speech-to-speech.
- Ship **one CPaaS phone path** (Twilio first, Telnyx as the documented twin).
- Ship **one-click local** (Compose) and **one-click hosted** on **both Fly and Railway**. Compose is the source of truth. Both templates are tested every release.
- Ship an **admin console**: documents, voice, providers, numbers, transcripts, kill switch.
- Ship a **companion website** that embeds or links the live demo.
- License is **Apache-2.0**. Do not statically link GPL TTS into the default image (see 12.4).

### 4.2 Non-goals (v1)

- Not a CCaaS. No ACD, no workforce management, no QM desktop replacement.
- Not a multi-tenant SaaS. Self-host is the product. The companion demo is a single showcase tenant, not a billing platform.
- Not a full contact-center overlay on Genesys / NICE / Amazon Connect.
- Not medical, payments-in-production, or collections. PCI pause is a stubbed contract so Chapter 22 labs can attach later. No card data in v1.
- Not the Service Line or Disruption Desk as running businesses.
- Not Google AX as the voice runtime (section 8).
- Not A2A on the media path (section 8).
- Not training or fine-tuning models.
- Not cloning a real person's voice without an explicit later consent feature.
- Not emergency-number routing. Never.
- Not outbound dialer / AMD / pacing in v1 (Appointment Line callback is a scheduled single call, not a campaign).
- Not "agents arguing on the call." Specialists share one persona and one voice (Chapter 14.6).

### 4.3 Explicitly later

CCaaS adapters, outbound programs, speech-to-speech as default, A2A agent-to-agent calls, multi-region, on-device mobile, voice biometrics, emotion detection, hosted multi-tenant.

---

## 5. Product shape: three artifacts, one runtime

```
+------------------+     +-------------------+     +----------------------+
| Companion website|     | Flagship app      |     | Book labs            |
| marketing, audio |---->| Knowledge Line    |     | ch06..ch25 small     |
| gallery, Deploy  |     | console + Talk +  |     | runners on the same  |
+------------------+     | phone + RAG       |     | contracts            |
                         +---------+---------+     +----------+-----------+
                                   |                          |
                                   v                          v
                         +-----------------------------------------+
                         | Open Voice Agents runtime               |
                         | contracts, turn loop, policy, RAG,      |
                         | tools, adapters (transport/STT/TTS/LLM) |
                         +-----------------------------------------+
```

The website must not grow a second agent. It hosts or iframes Knowledge Line. The labs must not grow a second pipeline. They construct the same runtime with mocks.

---

## 6. Flagship application: Knowledge Line

This is the comprehensive application people fork.

### 6.1 One-sentence pitch

Upload how your business works. Get a voice agent that answers the phone and the browser, cites your documents, books against your calendar when you connect one, and hands off to you when it should not guess.

### 6.2 Default story (the Monday path)

A two-van plumbing company (the book's Appointment Line) is the default bundled tenant. The empty-state wizard also works for any small business: clinic hours, restaurant FAQ, consultancy, internal IT helpdesk.

Monday path, no engineer required after deploy:

1. Deploy (Compose, or one-click host).
2. Create a workspace. Name, timezone, language, spoken disclosure line.
3. Drop in documents: PDF, Markdown, DOCX, TXT, or a URL to fetch.
4. Optionally paste structured facts: hours, address, service area, pricing notes, emergency rule.
5. Pick a voice (local Kokoro/Piper voice, or a hosted voice if keys exist).
6. Press Talk in the browser. Ask "Are you open Saturday?" and "What do you charge for a drain unblock?"
7. Optionally connect a phone number. Call it from a mobile.
8. Optionally connect a calendar. "Tuesday at 2" books a slot and texts a confirmation.
9. Optionally set the owner mobile. "I want a person" transfers.

### 6.3 Capabilities

**Must have (v1)**

- Workspace (one agent, one knowledge base, one persona, one number).
- Document ingest with status (queued, parsing, embedded, failed, stale).
- Structured facts store (hours, address, contact, emergency rule, never-say list).
- Voice bible: persona attributes, say/never-say, disclosure, pace.
- Browser Talk (WebRTC or a documented fallback WebSocket path for constrained hosts).
- Inbound PSTN via one CPaaS.
- RAG-for-the-ear (section 15).
- Hybrid dialogue: greet, identify lightly, capture intent, collect slots, confirm by risk, act, close, escalate.
- Repair catalog: misheard, out of scope, silence, "are you still there," anger → human.
- Always-on "person" / "agent" / "operator" escape. No loop.
- Cold transfer or callback-to-owner. Warm transfer when the transport supports it.
- Transcript, recording opt-in, redaction of obvious PII patterns at rest.
- Provider profile: `local` | `managed` | `s2s` (s2s can be disabled until keys exist).
- Kill switch: stop taking new calls; in-progress calls hear a short closing line and transfer or voicemail.
- Sample corpus and sample calls so a fresh install is not empty.
- **Local ICS calendar** (read/write slots for book, move, cancel). Google Calendar is v1.1.

**Should have (v1 if cheap, else v1.1)**

- URL crawl of a single site (depth-limited, robots-respecting).
- SMS confirmation (Twilio/Telnyx).
- Morning digest: spoken + written summary of overnight calls for the owner.
- Multi-document source citation in the console (not always spoken).
- Second language: graceful "we will call you back" if detection says the caller is not in the workspace language.
- DTMF fallback for "press 0 for a person."

**Later**

- Multi-workspace / multi-number.
- Outbound reminder campaigns.
- Payment turn with recorder pause.
- CCaaS seat.
- Agent-to-agent inbound.

### 6.4 Wizard fields (create-agent)

```
workspace.name
workspace.timezone
workspace.language
workspace.disclosure_text          # spoken; required
workspace.recording_consent        # off | announce | require-yes
persona.name
persona.register                   # brisk-trade | measured-utility | calm-authority
persona.never_say[]
knowledge.files[]
knowledge.urls[]
knowledge.facts.hours
knowledge.facts.address
knowledge.facts.service_area
knowledge.facts.emergency_rule     # e.g. burst pipe → transfer immediately
connectors.phone                   # none | twilio | telnyx | sip-uri
connectors.calendar                # none | local-ics   (google is v1.1)
connectors.sms
connectors.owner_number            # E.164 for transfer
providers.profile                  # local | managed | s2s
providers.stt / tts / llm          # override profile
```

### 6.5 Conversation contract for the default tenant

Building blocks from Chapter 8, compiled, not prompted as a novel:

1. **Greet + disclose.** "This is the River Plumbing desk. I'm an automated assistant."
2. **Intent.** Book / move / cancel / status / hours / price / emergency / person.
3. **Emergency short-circuit.** If emergency_rule matches, transfer before collecting address details beyond what the human needs.
4. **Collect** only slots the intent needs. Confirm high-risk slots (address, time) in groups.
5. **Act** through tools (calendar, SMS, ticket). Confirm aloud after the tool succeeds, never before.
6. **Grounded FAQ** for hours, prices, service area from RAG. If retrieval is empty or stale, do not invent.
7. **Close** with a receipt (spoken + optional SMS).
8. **Escalate** on three failed repairs, on "person", on policy block, or on low confidence identity when the action needs it.

### 6.6 What "fully agentic" means here

Not a swarm of voices on one call. Agentic means:

- The model may **choose tools and specialist skills** inside a policy envelope.
- Irreversible actions (book, cancel, SMS, transfer) are **proposed, confirmed, executed**.
- Knowledge is retrieved, not stuffed.
- Offline sidecar agents may summarize, score, and re-index.
- A later A2A surface may let an external agent book with us, still behind the same policy.

The caller hears **one persona**. Chapter 14.6 is the law.

---

## 7. Framework: layer contracts

Own these interfaces. Pipecat, LiveKit, Whisper, Deepgram, and the rest are adapters. If we expose Pipecat types as our public API, we become a starter kit and the book's swap story dies.

### 7.1 The eight layers (Chapter 2 / 9)

```
Caller
  │
  ▼
[1] Transport     PSTN / SIP / WebRTC / mock
  │  frames in, frames out, call control
  ▼
[2] Hearing       streaming STT (or S2S ear)
  │  partials, finals, language
  ▼
[3] Turn-taking   VAD + acoustic + semantic end-of-turn + barge-in
  │
  ▼
[4] Agent core    state, policy, specialists, tools, RAG
  │  (LLM or S2S mouth/brain)
  ▼
[5] Speaking      TTS (or S2S mouth)
  │
  ▼
[6] Transport     audio out, transfer, DTMF, recording tap
  │
  ▼
Caller

Beside the loop, not on it:
[7] Knowledge / memory / CRM
[8] Observability / eval / recordings
```

Speech-to-speech collapses 2+4+5 behind the same agent-core and transport contracts. Turn-taking and policy do not disappear.

### 7.2 Shared clock and identity

Every frame and every tool call carries:

```
trace_id          # call-scoped
span_id
layer             # transport | stt | turn | llm | tts | s2s | rag | tool | policy
t_mono_ms         # monotonic clock, not wall
call_id
turn_id
workspace_id
```

Latency attribution is a query over these, not a vendor dashboard. Chapter 9 implementation idea.

### 7.3 Cancel contract

Barge-in cancels at **transport**, not at text. Downstream layers must drop in-flight TTS and unused LLM tokens. A layer that cannot cancel is not a valid adapter.

### 7.4 Public interfaces (normative sketch)

Names can change in implementation. The shapes cannot get vaguer.

**Transport**

```
connect(call) -> media_duplex
send_audio(pcm16k_mono)
on_audio(handler)
on_dtmf(handler)
interrupt()                  # stop playback now
play(audio_chunk)
hold(reason)
transfer(target, payload)    # cold | warm | conference
hangup(reason)
start_recording() / pause_recording() / resume_recording()
```

**STT**

```
stream(audio) -> partials + finals
boost(vocabulary[])
set_language(code | auto)
```

**Turn-taking**

```
on_partial(text, vad_ms) -> { hold | cut | backchannel }
on_barge_in() -> cancel
on_silence(ms) -> prompt | hang_check | transfer
```

**LLM / Agent core**

```
propose(state, user_turn) -> { say, tool_calls, specialist, commit_check }
```

**Policy**

```
dispose(proposal) -> allow | rewrite | block | escalate
```

Policy runs on **every** irreversible tool and **every** spoken commitment ("I have booked you", "I have refunded you").

**TTS**

```
speak(text, voice, locale) -> audio_stream   # first byte measured
normalize(text, locale)                      # numbers, dates, money
lexicon(overrides)
```

**RAG**

```
retrieve(query, call_state) -> { sentence, source_id, expiry, confidence }
ingest(doc) -> { chunks, warnings }
```

**Tool**

```
name, latency_class          # instant | short | long
confirm_class                # none | implicit | explicit | explicit + step-up
run(args, operation_id?) -> { speakable, data, error }   # operation_id required on every write
lookup(operation_id) -> first result | absent            # read-back for reconciliation
```

Every write is an **operation**: one business action the caller agreed to (one booking, one cancellation). The operation journal holds one record per operation:

```
operation_id        # random; minted when the caller confirms
fingerprint         # hash of the material terms: tool, account, every parameter the caller agreed to
status              # confirmed | submitted | committed | rejected | unknown | not_done | expired | compensated
call_id, turn_id    # lineage only; never part of the id
```

- **Mint the id when the caller confirms.** Not at proposal: a declined proposal is not an operation. Not per attempt: a retry would become a new operation. Not from `call_id` and `turn_id`: a reconnect gets a new call id, one turn can create two operations ("book Tuesday and cancel Friday"), and a changed mind creates two operations in two turns. A yes counts only if it covers this fingerprint: the same terms, every material term heard, not expired, not from a canceled turn.
- **Journal before sending.** Write `operation_id`, `fingerprint`, and status `confirmed` to the journal before the first request is sent. Keep the journal in the same store as call state (11.3), so one write records the yes and the operation. If the worker dies after the yes, the journal still shows an operation that was promised and not sent.
- **Reuse the id; refuse a mismatch.** Every attempt sends the same `operation_id`, also after a reconnect or on another worker. The system of record (or the adapter, if the system cannot) stores the id with the fingerprint and the first result, and returns that result to every retry. A known id with a different fingerprint gets `mismatch` and no side effect. Changed terms need a new confirmation and a new id.
- **Read back after a timeout.** A timeout makes the operation `unknown`, not failed. Before the agent says anything about the outcome, it calls `lookup(operation_id)`. A found result is the outcome. `absent` means `not_done`; a resubmit with the same id is safe. If the read-back also times out, the agent says the `timeout` line and opens a tracked promise (`promises[]`, 11.3). Only `committed` may be spoken as done.
- **No read by id.** If a system of record cannot store the id or read by it, the adapter keeps the journal and reconciles by a natural key (account, resource, time window). This is slower and weaker. The adapter declares it as a known limit.
- **Undo is a new operation.** A committed operation is never edited. A reversal is a compensating operation with its own id and its own confirmation; the original becomes `compensated`.
- **Speakable beside data.** Every `run` and `lookup` result carries `speakable`, one short sentence about the outcome from the system that produced it, next to `data`. The model does not invent outcome wording.

`error` is one of seven classes (builders' Chapter 17, Table 17.3). The class chooses the spoken line; the model never improvises failure wording. Lines are data, versioned with the voice bible (13.5), at most two sentences, and never ask the caller to do something they cannot.

| Class | Fixed by | Retry |
| --- | --- | --- |
| `invalid_input` | the caller | no; re-ask |
| `not_found` | the caller | no; re-ask |
| `conflict` | the agent | no; offer another |
| `not_permitted` | a step-up or a person | no |
| `unavailable` | time | yes, silently, within budget |
| `timeout` | reconciliation | yes, same operation id |
| `internal` | a person | no |

`mismatch` is an agent defect, not a caller error: log it, do not retry, and speak the `internal` line.

Reference implementation: `code-labs/builders/ch17/tools_lab.py` (`Proposal.fingerprint`, `Confirmation.covers`, `Calendar.book`, `Calendar.lookup`, `keyed_reconciled`). Changed 2026-09-25 to match builders' Chapter 17 (`manuscript/builders/ch17-tools-and-actions.md`); see `brainstorm/common-research.md`.

### 7.5 Three profiles

| Profile | Hearing | Brain | Speaking | Keys required | Default for |
| --- | --- | --- | --- | --- | --- |
| **local** | Moonshine or sherpa-onnx or Whisper | Ollama / compatible local server | Kokoro (default) or Piper sidecar | No | Laptop, privacy, book labs |
| **managed** | Deepgram (default hosted STT) | OpenAI or compatible | Cartesia or ElevenLabs or OpenAI TTS | Yes | Production small business |
| **s2s** | Provider realtime ear+mouth | Same provider or hybrid tools | Same | Yes | Swap lab; optional production |

A workspace picks a profile, then may override one layer. The dialogue object and tools do not change.

### 7.6 First orchestrator adapter

**Recommendation:** implement the first pipeline adapter on **Pipecat**, because it already has local Whisper, Moonshine, Piper, Kokoro, many hosted STT/TTS/LLM/S2S plugins, and multi-agent pipeline primitives. Expose **our** contracts, not Pipecat frames, to the app and labs.

**First transport adapter:** LiveKit (self-hosted in Compose) for WebRTC rooms, SIP bridging, recording. Second transport: Twilio Media Streams / ConversationRelay so a reader with only Twilio and no SIP skill can still get a number. Mock transport for labs.

If Pipecat-over-LiveKit becomes painful, a native LiveKit Agents adapter is the twin, still behind the same contracts. Do not pick a winner in application code.

---

## 8. Substrate evaluation

Jay asked whether Google AX is the right place to "bring multiple agents and talk to each other." Research date: 2026-09-20.

### 8.1 Google AX (Agent Executor) — do not use for the call path

Repo: [github.com/google/ax](https://github.com/google/ax). Apache-2.0. Preview. The README warns of breaking changes before a stable release.

What AX is:

- A **Kubernetes-shaped orchestrator for sandboxed agent workloads**.
- Primitives: `Task`, `Workspace` (git, MCP, skills), `Gateway` (egress allowlist), `Model`.
- Built to run **billions of isolated, suspendable, resumable tasks** on Agent Substrate.
- Feels like `kubectl` for long-running code agents (`ax apply`, `ax ssh`, `ax suspend`).
- Designed for untrusted agent code that accumulates state, calls model APIs, and can burn money if unsupervised.

What AX is not:

- Not a voice pipeline. No frames, no barge-in, no 800 ms budget, no PSTN.
- Not a conversational multi-agent bus. Agents do not "talk to each other" on a phone line.
- Not one-click. Control plane + Redis + `ko` + a reachable Agent Substrate API + a cluster.
- Not stable enough to pin a book or a product to in 2026.

**Verdict (locked 2026-09-20):** ignore AX as a voice substrate. Jay confirmed it is not a fit yet. Optional far-future: run **offline** sidecar jobs (eval suites, untrusted tool sandboxes, bulk re-index) on AX if we ever need that isolation. Do not mention AX in the getting-started path. Reopen only if Jay asks.

### 8.2 Google A2A (Agent2Agent) — later interop, not media

A2A is an HTTP/JSON-RPC protocol (Linux Foundation) for opaque agents to delegate tasks, discover Agent Cards, and stream task updates. Twilio has a latency extension for routing among agents. Native WebRTC/WebTransport is **not** a first-class A2A transport (issue #997; custom bindings only).

**Verdict:** useful in a later phase for (a) specialist agents in other processes and (b) the book's agent-to-agent call (a passenger's assistant books with our desk). **Not** the audio path. We would still terminate RTP/WebRTC ourselves and speak A2A in text/tools beside the call.

### 8.3 Google ADK / Gemini Live

Useful as **one** S2S and LLM adapter. Not the framework. Same rule as OpenAI Realtime.

### 8.4 Pipecat

Best current open **pipeline** framework: transport-agnostic, huge provider catalog, local STT/TTS extras, multi-agent pipelines, Daily/Twilio/LiveKit/WhatsApp transports. Maintained by Daily. Python.

Cost: we assemble production media ourselves unless we also run Daily or LiveKit.

### 8.5 LiveKit Agents

Best current open **media + SIP** stack. Rooms, tracks, egress, recording, inbound/outbound SIP, Railway templates already exist. Agents SDK is capable. Self-host removes concurrent-session ceilings of LiveKit Cloud.

Cost: less frame-level custom pipeline than Pipecat; local STT/TTS exist via community plugins (faster-whisper is often **batch**, which loses ~300 ms to cloud streaming).

### 8.6 Vocode, TEN, others

Vocode: simpler telephony, smaller ecosystem. TEN: another realtime stack; do not take a third orchestrator in v1. Vocode can be a later adapter if a reader already has it.

### 8.7 Mastra, LangGraph, CrewAI, AutoGen

Text-agent frameworks. Fine for sidecar planners and SOP compilers. They do not hear or speak. Do not put them on the turn loop.

### 8.8 Managed voice platforms

Vapi, Retell, Bland, ElevenLabs ConvAI, Deepgram Voice Agent, Twilio ConversationRelay: competitors and also possible **S2S/orchestration adapters** behind our interface (Chapter 19 buy shapes). The product thesis is that a reader can leave them. We do not need a Vapi adapter in v1.

### 8.9 Decision

```
Own contracts.
First pipeline: Pipecat adapter.
First media: LiveKit in Compose (+ Twilio WS as the low-skill phone path).
First local speech: Moonshine or sherpa streaming STT + Kokoro TTS + Ollama LLM.
A2A: phase 4 interop.
AX: out of scope.
```

---

## 9. Local and hosted speech: the swap

This is a v1 requirement, not a nice-to-have. The local path is how the book stays honest and how a privacy-sensitive shop runs without sending audio to a vendor.

### 9.1 Design rules

1. **Same dialogue, same tools, same RAG**, three provider profiles.
2. Audio never leaves the machine on the local profile except the optional phone trunk.
3. Adapters are config. The admin UI writes that config. No code gen.
4. Measure TTFB and voice-to-voice on **our** prompts at **our** concurrency. Never publish a vendor's blog number as ours.
5. A vendor model update is a canary through the scenario suite, not a silent accept.
6. License: default images must stay Apache-compatible. Piper in-process is GPL-3.0 (`piper-tts`). If we offer Piper, it is an **HTTP sidecar** (`PiperHttpTTSService` or equivalent) or an optional extra, not the default wheel.

### 9.2 Hearing (STT)

| Adapter | Mode | Why it is here | Caveats (checked 2026-09-20) |
| --- | --- | --- | --- |
| **Moonshine** (Pipecat) | Local CPU, ONNX | Fast enough for a laptop; streaming English models exist; no GPU | Limited languages; still often segment-batched after VAD |
| **sherpa-onnx** Zipformer / SenseVoice | Local streaming | True streaming partials; multilingual SenseVoice | Extra model packaging; we may wrap it ourselves if Pipecat support is thin |
| **faster-whisper / MLX Whisper** | Local | Quality, Apple Silicon MLX path | **Batch**: waits for end of speech. Fine for labs, loses to cloud on the 800 ms wall |
| **Deepgram** | Hosted streaming | Default managed STT; partials, keywords, endpointing | Audio leaves; logs/retention must be disclosed |
| **AssemblyAI, Google, Azure, AWS, Speechmatics, OpenAI transcribe** | Hosted | Swap examples | Adapter quality varies; do not all ship in v1 |
| **S2S ear** | Hosted/local | Profile 3 | Observability is worse; keep raw audio if the provider allows |

v1 ships: Moonshine **or** sherpa (pick one as default after a laptop bake-off), Whisper as quality fallback, Deepgram as hosted default. Others are adapter stubs or phase 2.

**Keyword boosting** is data: per-workspace vocabulary (street names, service SKUs, staff names). Local adapters that cannot boost must still accept the list and no-op, so the UI does not fork.

### 9.3 Turn-taking

Ship our own policy on top of:

- Silero VAD (local, default).
- Acoustic end-of-turn timeout (tunable).
- Cheap semantic completeness check on the partial (small local model or heuristic).
- Barge-in: energy + not-our-echo (AEC at the transport).
- False interrupt: TV/dog hold.

Log every end-of-turn decision with the partial that drove it (Chapter 12). Default thresholds ship with a sweep lab, not magic numbers claimed as universal.

### 9.4 Speaking (TTS)

| Adapter | Mode | Why | Caveats |
| --- | --- | --- | --- |
| **Kokoro ONNX** | Local | Apache-friendly, 50+ voices, 9 languages, CPU, Pipecat first-party | Quality good not premium; not a clone |
| **Piper HTTP sidecar** | Local | Fast CPU, many locales | GPL if in-process; use sidecar |
| **Chatterbox / Orpheus / XTTS** | Local optional | Higher quality / clone experiments | Heavy; not default |
| **Cartesia, ElevenLabs, Deepgram Aura, OpenAI TTS, Azure, Polly, Rime** | Hosted | Managed profile | TTFB and voice drift; pin voice ids |
| **S2S mouth** | Hosted | Profile 3 | Same persona must survive the swap; voice bible is data |

v1 default local: **Kokoro**. v1 default hosted: pick one after a MOS-on-our-lines bake-off (Cartesia vs ElevenLabs vs OpenAI). Cache the twenty most common phrases (disclosure, hold, "let me check that").

**Locale formatter** sits in front of every TTS: numbers, dates, money, addresses. Codes read with pauses. This is our code, not the vendor's.

### 9.5 Brain (LLM)

| Adapter | Mode | Why |
| --- | --- | --- |
| **Ollama** (Llama/Qwen/Gemma) | Local | Zero-key path |
| **vLLM / OpenAI-compatible** | Self-hosted | Faster local/server |
| **OpenAI, Anthropic, Gemini, Groq** | Hosted | Managed profile |
| **S2S model** | Hosted | Profile 3; tools must still hit our policy |

Turn model stays **small and fast**. Summaries, SOP compile, QM judge, and retrieval rerank may use a stronger model **off** the call path (Chapter 15.4).

Time-to-first-token timeout falls back to a smaller model plus a holding line. Pin versions. Canary in CI.

### 9.6 Embedded / on-device

v1 "embedded" means **in-process or sidecar on the same host**, not a phone NPU. On-device mobile STT/TTS is a Chapter 29 note, not a v1 runtime. The contracts should not forbid a future embedded adapter (same PCM16k in, same events out).

### 9.7 Swap UX

```
providers:
  profile: local
  stt: moonshine          # or deepgram
  tts: kokoro             # or elevenlabs
  llm: ollama:qwen2.5
  s2s: null
```

Admin UI: three radio buttons (Local / Hosted / Realtime) and advanced overrides. A "render nine test lines" button plays the voice bible through the current TTS (Chapter 6 implementation idea).

---

## 10. Telephony and other connectors

### 10.1 Channels in v1

| Channel | Priority | Notes |
| --- | --- | --- |
| Browser WebRTC | P0 | Zero-phone path; companion site uses this |
| Mock / fixture | P0 | Labs and CI |
| Twilio inbound | P0 | Lowest-skill real number |
| Telnyx inbound | P1 | Documented twin so Twilio is not a lock |
| LiveKit SIP | P1 | Self-host path; any SIP trunk |
| SMS (out) | P1 | Confirmations and links |
| Outbound single call | P2 | Callback promise, not a dialer |
| WhatsApp / in-app | P3 | Pipecat already has WhatsApp; do not advertise until tested |

### 10.2 Phone number wizard

The user should not read a SIP RFC.

1. Paste CPaaS account credentials (or env).
2. Buy or pick a number in the provider console (we link the exact screen; we do not scrape).
3. We write the webhook / SIP origination for them via API where the provider allows.
4. We place a verification call or ask them to dial and say a code.
5. Inbound calls hit Knowledge Line for that workspace.

Toll-fraud controls before the first outbound: destination allowlist, max rate, max price per minute, daily cap. Chapter 10.10.

Never touch emergency numbers. Reject 911/112/999 etc. in the dialer.

### 10.3 Call control

v1: answer, hangup, DTMF 0, cold transfer to `owner_number`, optional warm transfer if the transport can attach a whisper summary ≤15 words (Chapter 21).

Recording: we record at the edge we own. Pause/resume API exists even if PCI is stubbed.

Dropped-call resume: serialize state every turn (Chapter 14). If the same ANI calls back within N minutes, offer "shall I continue where we left off?"

### 10.4 "Any other piece of information" (connectors)

A connector is a typed plugin with ingest + tools + UI.

| Connector | v1 | Tools it adds |
| --- | --- | --- |
| Documents | yes | `retrieve_knowledge` |
| Structured facts | yes | read-only grounding |
| Phone number | yes | inbound |
| Owner / desk number | yes | `transfer_human` |
| Local ICS calendar | yes | `find_slot`, `book`, `move`, `cancel` |
| Google Calendar | v1.1 | same tools |
| SMS | should | `send_receipt` |
| Website crawl | should | ingest |
| Fake CRM / tickets | yes (labs + app) | `lookup_ani`, `open_ticket` |
| HubSpot / Salesforce / Zendesk | later | same contracts |
| Google Business hours | later | facts sync |
| MCP generic | later | policy-wrapped tools only |
| Slack / email notify | later | morning digest |

Connectors declare latency class and confirm class. A calendar write is `explicit`. A knowledge retrieve is `none`. An SMS is `implicit` after a successful book.

---

## 11. Multi-agent design

### 11.1 Three kinds of agent, three different buses

| Kind | When | How they communicate | On the call? |
| --- | --- | --- | --- |
| **Specialists** | FAQ/RAG, booking, identity, escalate | In-process handoff on a shared state object, one persona prompt | Yes, one voice |
| **Sidecars** | Summary, QM score, re-index, SOP compile | Queue / HTTP after the turn or after the call | No |
| **External agents** | Another org's assistant books with us | A2A or SIP+identity, later | Yes, but they are a **caller**, not a second mouth |

Do not run a debate among specialists on the audio path. The router picks one specialist per turn (or a planned sequence), the policy gates tools, the speaker stays the workspace voice.

### 11.2 Router

Inputs: intent, state, retrieval emptiness, risk of next action.  
Outputs: `faq` | `booking` | `identity` | `escalate` | `smalltalk`.  
Implementation: compiled SOP first (deterministic), model only to classify leftover utterances. Chapter 14.7: determinism lives in policy and routing tables.

### 11.3 Shared state object

```
call_id, ani, workspace_id
identity: { level, name, account?, verified_fields[] }
intent, slots, confirmations[]
commitments[]            # things we have actually done
promises[]               # callbacks we owe
last_retrieval[]         # source_ids
specialist, persona_id, instruction_version
language
recording: { on, paused }
repair_count
```

Serialized every turn to Postgres (or SQLite in local profile). Resume and failover read this, not the LLM context window.

### 11.4 Why not AX here

AX isolates **untrusted long-running workers**. A voice turn is trusted-enough, latency-bound, and must share memory with the media thread. Putting FAQ and booking in separate AX tasks would add sandbox boot and gRPC hops we cannot afford. If a future tool executes caller-influenced code (browser, shell), **that tool** may someday sit in a sandbox. The turn loop does not.

---

## 12. RAG for the ear

Chapter 16.5 is the product, not "chat with your PDF."

### 12.1 Ingest

Supported v1: PDF, Markdown, TXT, DOCX, pasted facts, optional single-site crawl.  
Chunking: heading-aware, 400–800 tokens, overlap, each chunk stores `source_id`, `title`, `locator` (page or heading), `owner`, `ingested_at`, `expires_at` (optional).  
Parse warnings surface in the console (scanned PDF with no text, empty file, language mismatch).

### 12.2 Index

Local profile: `sqlite-vec` or LanceDB on disk, embeddings from a local ONNX model (e.g. a small E5/GTE class; bake-off).  
Managed/hosted: pgvector on the Compose Postgres, same embedding interface, optional hosted embeddings.

One interface: `embed(texts) -> vectors`. Swap local/hosted like STT.

### 12.3 Retrieve

Query is the caller turn plus active slots.  
Return **k=3** max. The agent-facing payload is:

```
sentence: "Saturday hours are 8 to 12, last booking at 11."   # already speakable
source_id: doc_hours_v3
confidence: 0.82
expires_at: null
```

Never dump a paragraph into the prompt and hope. A formatter/rewriter (small model or extractive) produces the sentence. If confidence < threshold or the chunk is expired, retrieval returns empty and the agent must say it does not know.

### 12.4 Freshness and operations

Console shows last ingest, chunk count, failed files, expired items.  
Re-ingest on upload. Optional TTL.  
Knowledge owner defaults to the workspace owner.  
Chapter 26 content operations: v1 is a single owner, not a CoE.

### 12.5 Hallucination control

- System instruction: only answer from retrieval + structured facts + tool results.
- Post-generation **commitment check**: if the utterance asserts a price, hour, or policy, it must match a source_id or fact key.
- Evaluation: a fixture corpus with known Q/A; CI fails if the agent invents a closed-day opening.

---

## 13. Agent core, policy, tools, guardrails

### 13.1 Control style

**Hybrid** (Chapter 14.2). Compiled SOP is the skeleton. The model fills language and leftover classification. Free-form only inside FAQ after retrieval. Scripted only for disclosure, emergency, and payment-shaped turns (even though payment is stubbed).

### 13.2 Policy layer

The model proposes. Policy disposes.

Blocks:

- Tools not allowed for this identity level.
- Spoken commitments with no matching tool result.
- Never-say list (competitor slander, legal/medical advice patterns, guaranteed outcomes).
- Outbound-like persuasion (v1 has almost no outbound; still refuse pressure language).
- Emergency medical/legal advice: escalate.
- Injection: caller text is data. Instruction hierarchy is system > SOP > developer > retrieved > caller.

### 13.3 Tools (v1 set)

| Tool | Latency | Confirm | Notes |
| --- | --- | --- | --- |
| `retrieve_knowledge` | instant | none | speakable sentence |
| `lookup_facts` | instant | none | hours/address |
| `lookup_ani` | instant | none | fake CRM |
| `find_slot` | short | none | |
| `book` / `move` / `cancel` | short | explicit | operation id (7.4) |
| `open_ticket` | short | implicit | leftover / message |
| `send_receipt` | short | implicit | SMS or skip |
| `transfer_human` | short | implicit | always allowed |
| `schedule_callback` | short | explicit | single outbound later |

Long tools become a promise + filler ("let me check that") + callback. No 8-second silent hold.

### 13.4 Guardrails (Chapter 18)

- Loop detector: 3 repairs → offer a human.
- Persistence / jailbreak: do not change policy because the caller asked nicely five times.
- Child-on-the-line heuristic: conservative, transfer.
- Profanity: stay in register; do not lecture.
- Shadow mode hook: replay a recording against a new core (v1.1).

### 13.5 Instructions as data

```
instruction_version
voice_bible_id
sop_id
never_say[]
disclosure_by_locale[]
```

Prompt, voice, and SOP ship together. Rolling back one rolls back all three (Chapter 16.8, 24.12).

---

## 14. Admin console

A web app. Not a second product. It configures Knowledge Line.

### 14.1 Surfaces

1. **Setup wizard** (section 6.4).
2. **Talk** — in-browser call with live transcript (partials + finals), latency chips (STT, LLM, TTS, e2e).
3. **Knowledge** — files, facts, chunk browser, "ask a test question."
4. **Voice** — persona, nine test lines, provider radios.
5. **Phone** — number wizard, trunk status, fraud caps.
6. **Calls** — list, transcript, trace waterfall, source citations, recording if consented.
7. **Scenarios** — run the fixture suite against the current core.
8. **Kill switch** and degradation (close new calls / FAQ-only / transfer-all).

### 14.2 Empty, loading, error states

Empty knowledge: Talk still works, but the agent only takes a message and states that the desk has no published hours.  
Ingest running: banner, Talk uses last good index.  
Provider down: spoken fallback + console error with **problem, cause, fix** (DX).  
Number misconfigured: wizard shows the last provider error, not a generic 500.

### 14.3 Auth (self-host v1)

Single-user password or setup token on first boot. Optional OIDC later. The companion public demo is passwordless against the **sample tenant only**. Talk is limited to the bundled sample turns and sample documents. No user uploads, no user-created workspaces, no SMS, no outbound dial.

---

## 15. Companion website

Purpose: prove the book and the repo in one click. It is not a separate agent.

### 15.1 Pages

- Home: promise, Talk widget (sample River Plumbing or "ask the book"), Deploy buttons (GitHub, Compose, Railway/Fly).
- Live demo: Knowledge Line Talk against the sample tenant only. Sample turns and sample documents. Writes, uploads, and number attach are off.
- Audio gallery: the book "hears" (good call, fluent-wrong, cut-off, barge-in, two voices). Hosted files, transcripts beside them.
- Docs: getting started, swap guide, telephony, RAG, security.
- Chapter lab index (can start as links into the repo).
- Dated facts / errata hook for Appendix I later.

### 15.2 Technical split

| Piece | Where |
| --- | --- |
| Marketing, docs, audio gallery | Static (Cloudflare Pages, GitHub Pages, or Vercel) |
| Talk demo and console | Same Knowledge Line image as self-host, on Fly/Railway/GPU box |
| Deploy | Buttons that deep-link to the public GitHub repo + template |

The demo must use the **local or cheap hosted** profile with hard concurrency limits, no outbound dial, and **no ingest**. Sample documents and sample turns only. Visitors cannot upload files or create a workspace on the public instance.

### 15.3 Book integration

QR codes and short URLs in print resolve here. Clip file names in the ebook match gallery slugs. The website is allowed to date itself ("stack checked 2026-09-20").

---

## 16. One-click deploy

"One click" is a ladder, not a lie.

### 16.1 Rung 0 — laptop, no accounts

```
git clone
cp .env.example .env
docker compose up
open http://localhost:8080
```

Pulls: runtime, console, LiveKit (or small WebRTC path), Ollama or a bundled tiny LLM **optional** (if the image is huge, document a two-step: compose + `ollama pull`).  
STT/TTS models download once, cached in a volume.  
Talk works on loopback.

Target: **time-to-hello-world under 15 minutes** on a recent Mac or 16 GB Linux box, assuming model cache cold. Second start under 2 minutes.

### 16.2 Rung 1 — one-click host (Fly and Railway)

Both ship. Compose remains the source of truth; `deploy/fly` and `deploy/railway` are generated from it and tested every release.

- **Fly:** preferred for the public companion demo. UDP WebRTC is less painful.
- **Railway:** first-class template for builders who already live there. Railway has no native UDP; WebRTC must use TCP ICE or a TURN service. Document that limit in the Railway README. Phone via Twilio WS avoids UDP on our host.

A user who clicks Deploy on the companion site sees **both** buttons.

Required env: none for a browser-only hosted demo with our keys **off**. For a user's own deploy: their LLM key **or** a local-model machine type.

We will **not** pretend GPU cloud is one click in v1. Hosted profile uses cloud STT/TTS/LLM. Local profile on a $12 VPS is CPU Moonshine + Kokoro + a small LLM, quality-limited, and we say so.

### 16.3 Rung 2 — phone

Add `TWILIO_*` or `TELNYX_*`, run the number wizard. One extra click is acceptable. "One click including buying a number for you" is out of v1 (payments, KYC).

### 16.4 Rung 3 — production-ish

Compose on a VPS with Caddy, DNS, persistent volumes, backups of Postgres/SQLite, recording bucket. A `deploy/vps` guide, not a full Kubernetes distro.

**No Kubernetes, no AX, no Agent Substrate in the getting-started path.**

### 16.5 Images

- `open-voice-agents-runtime`
- `open-voice-agents-console` (can be served by runtime in v1 to reduce moving parts)
- `livekit` (upstream)
- `postgres` or sqlite volume
- `ollama` (profile local)
- `piper` sidecar (optional extra)

Default `compose.yaml` is the local profile. `compose.managed.yaml` overlay adds no local models.

---

## 17. Data model (logical)

```
workspaces
  id, name, timezone, language, disclosure, recording_policy, kill_switch,
  provider_profile, created_at

voices / voice_bibles
  workspace_id, persona attrs, never_say, test_lines, tts_voice_id

sops / dialogue_objects
  workspace_id, version, compiled_json, source_md

documents
  workspace_id, filename, mime, status, bytes, ingested_at, error

chunks
  document_id, locator, text, embedding, expires_at, owner

facts
  workspace_id, key, value, speakable, expires_at

connectors
  workspace_id, type, config_encrypted, status

provider_configs
  workspace_id, layer, adapter, settings_json

calls
  id, workspace_id, channel, ani, dnis, started_at, ended_at,
  disposition, recording_uri, language

turns
  call_id, turn_id, specialist, user_final, agent_text,
  retrieval_ids, tool_calls, policy_decision, t_layer_ms

commitments / promises
  call_id, type, payload, kept_at

tickets
  workspace_id, call_id, body, status

eval_scenarios
  id, audio_or_script, expect, layer

instruction_revisions
  workspace_id, triple (prompt, voice, sop), shipped_at
```

Secrets live in env or a local secret store, never in git, never in traces.

Retention: workspace-configurable. Default 30 days for recordings, 90 for transcripts, redaction at write.

---

## 18. API surface (v1 sketch)

All application actions the console can do, an agent or script can do (agent-native parity).

```
POST /api/workspaces
GET  /api/workspaces/:id
PATCH /api/workspaces/:id/providers
POST /api/workspaces/:id/documents
GET  /api/workspaces/:id/documents
POST /api/workspaces/:id/facts
POST /api/talk-tokens                 # LiveKit or WebRTC token
POST /api/telephony/twilio/voice      # inbound webhook
POST /api/telephony/telnyx/voice
POST /api/calls/:id/kill
GET  /api/calls
GET  /api/calls/:id
GET  /api/calls/:id/trace
POST /api/eval/run
GET  /healthz
GET  /readyz                          # models loaded, livekit up
```

OpenAPI published. Webhooks we send: `call.completed`, `booking.created`, `escalation.requested`.

---

## 19. Observability, metrics, evaluation

### 19.1 Two families (Chapter 23)

**Experience / engineering:** TTFB per layer, end-of-turn to first audio, voice-to-voice p50/p95/p99, WER on fixtures, interruption rate, false cut-off rate, MOS panel hook.

**Operations:** task completion (not containment alone), transfer rate, time-to-human, callback keep rate, cost per minute, cost per resolved task.

Every number cohorted by language, channel, provider profile.

### 19.2 Traces

OpenTelemetry. One trace per call, spans per layer. Attach redacted transcript and audio pointer. Langfuse-compatible exporter optional.

### 19.3 Evaluation

- Bundled scenario library (Appointment Line happy path, emergency, out-of-scope, noisy fixture, stale knowledge, jailbreak-lite, "agent" escape).
- Mock caller over the same transport interface.
- CI: mocks + fixtures, no keys.
- "Promote this bad call to a scenario" button in the console (v1.1).
- Live provider tests optional, nightly, banded.

---

## 20. Trust, security, compliance

v1 is a self-hosted small-business line, not a HIPAA platform. Still ship the hooks the book will teach.

### 20.1 Must

- Spoken disclosure, data-driven per locale.
- Recording off by default on the public demo; announce-or-consent on self-host.
- Redact obvious PII (phone, email, card-shaped, SSN-shaped) before logs land.
- Caller utterances never enter the instruction channel.
- Tool least privilege; no generic shell.
- CSRF, auth on admin, rate limit Talk and telephony webhooks (signature check).
- Trunk fraud caps.
- No emergency dial.
- Dependency and secret scan in CI.
- Threat model documented: spoofed ANI, synthetic caller, prompt-via-audio, data leaving through a tool, DoS by call volume.

### 20.2 Must not claim

HIPAA, PCI, SOC2, "voice biometrics are safe," emotion detection accuracy. Voice biometrics are out (Chapter 20.8). Emotion detection is out (Chapter 7.13 liability).

### 20.3 Public demo extra

Sample tenant and sample turns only. No uploads, no URL fetch, no user workspaces. Concurrency cap. Dial allowlist empty.

---

## 21. Repository layout (proposed)

```
repo/
  REQUIREMENTS.md              # this file
  README.md
  LICENSE                      # Apache-2.0
  lock-in-ledger.md            # Chapter 19.7, living
  packages/
    contracts/                 # interfaces + fixtures schemas
    runtime/                   # turn loop, policy, state, SOP compile
    adapters/
      transport/{livekit,twilio,mock}
      stt/{moonshine,whisper,deepgram,sherpa}
      tts/{kokoro,piper_http,elevenlabs,cartesia}
      llm/{ollama,openai_compat}
      s2s/{openai_realtime,gemini_live}   # may land v1.1
      rag/{sqlitevec,pgvector}
    app/                       # Knowledge Line API
    console/                   # admin + Talk UI
    website/                   # companion marketing
    labs/                      # chapter labs, mock-first
    scenarios/                 # Appointment Line, later packs
  deploy/
    compose.yaml
    compose.managed.yaml
    railway/
    fly/
    vps/
  testdata/                    # audio fixtures, sample PDF, frozen outputs
```

Language split: **Python** for runtime/adapters/labs (Pipecat, scientific audio). **TypeScript** for console and website. One OpenAPI contract between them.

---

## 22. Book labs and scenario packs

Labs remain small, stdlib-friendly where possible, and import contracts rather than the full app.

| Pack | Code promise |
| --- | --- |
| **Knowledge Line** | Full app |
| **Appointment Line** | Complete vertical on the app: calendar, SMS stub, emergency transfer, morning digest |
| **Service Line** | Scenario files, fake CRM, spike greeting, recorder-pause stub, desktop payload. Not a utility |
| **Disruption Desk** | Contracts, identity/third-party cases, A2A sketch, surge numbers as load fixtures. Not an airline |

Each chapter lab from v6 that needs a runner gets a folder under `packages/labs/chXX-*` as the book is written. Do not pre-build 29 empty labs.

---

## 23. Phased delivery

Effort is order-of-magnitude for a small team plus coding agents, not a bid.

### Phase 0 — Contracts and a talking loop (2–3 weeks)

- Contracts package + mock transport + mock STT/TTS/LLM.
- Hybrid core with FAQ-only SOP and policy gate.
- Browser Talk against mocks.
- One fixture lab green in CI.
- **Exit:** a reader hears a scripted agent with no keys.

### Phase 1 — Local profile + RAG (3–4 weeks)

- Moonshine or sherpa + Kokoro + Ollama.
- Document ingest + sqlite-vec + speakable retrieval.
- Compose path. Sample River Plumbing corpus.
- Console: wizard, knowledge, Talk, traces.
- **Exit:** section 3.4 laptop criterion.

### Phase 2 — Swap + phone (3–4 weeks)

- Deepgram + one hosted TTS + one hosted LLM.
- Provider radio in the console; nine test lines.
- Twilio inbound wizard; LiveKit SIP documented.
- Kill switch, fraud caps, redaction.
- **Exit:** real inbound call on a bought number.

### Phase 3 — Appointment Line complete + website (3–4 weeks)

- Local ICS calendar, SMS receipt, owner transfer, morning digest. Google Calendar is v1.1.
- Scenario suite for the Appointment Line.
- Companion website with sample-turn Talk demo, gallery stub, Deploy buttons for **Fly and Railway**.
- Fly launch file and Railway template, both tested.
- **Exit:** fork-or-click story is true; website showcases it.

### Phase 4 — Agent depth (ongoing)

- Specialists behind one voice.
- S2S profile (OpenAI Realtime and/or Gemini Live).
- Telnyx twin. Optional Piper sidecar.
- Promote-bad-call, shadow replay.
- A2A inbound sketch for "assistant calling the desk."
- Service Line scenario pack.

### Phase 5 — Out of band

CCaaS seat, outbound program, multi-region, AX sandboxes if ever, on-device.

**Ship Phase 3 before writing book chapters that claim the companion app exists.** Labs can ship from Phase 0.

---

## 24. Success metrics for the repository itself

| Metric | Target after Phase 3 |
| --- | --- |
| Time to first spoken turn, local, cold models | < 15 min documented; measure on a clean machine |
| Time to first spoken turn, warm | < 2 min |
| Voice-to-voice p95 on local laptop, short FAQ | Measure and publish; do not invent a number now. Design target 800 ms; local CPU may miss it and we will say so |
| Task completion on Appointment Line fixture set | ≥ 90% |
| Hallucinated hour/price on held-out FAQ | 0 in CI |
| Provider swap: same scenario pass rate local vs managed | Within a stated band |
| Public demo availability | Best-effort; status badge |
| Book CI | Labs green without keys |

---

## 25. Risks

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Local path misses the 800 ms wall | Readers will call the book dishonest | Publish real numbers; use streaming STT; keep local as privacy profile, managed as latency profile |
| Whisper-as-default teaches a batch lie | Chapter 11 is about partials | Do not default to faster-whisper for Talk; keep it as a quality/lab adapter |
| Piper GPL contaminates Apache repo | Legal | Kokoro default; Piper sidecar optional |
| Pipecat or LiveKit churn | Lock-in ledger becomes real | Contracts owned by us; lock-in ledger file in repo |
| "One click" on Railway WebRTC is a trap | UDP, TCP ICE, TURN | Twilio WS phone path; document WebRTC limits; test the template every release |
| Public demo abused for toll fraud | Money, reputation | No outbound; signed webhooks; concurrency cap |
| Scope explodes into a CCaaS | Never ships | Non-goals enforced; Service Line is data |
| AX curiosity derails the stack | Months on K8s | Stay-out locked 2026-09-20. Reopen only if Jay asks |
| Book vs product drift | Two sources of truth | Dated facts file shared; this document versioned with the repo |

---

## 26. Locked decisions (Jay, 2026-09-20)

These were open in the first draft. They are now product locks.

| # | Decision | Lock |
| --- | --- | --- |
| 1 | Name | **Open Voice Agents**. Slug `open-voice-agents`. Spoken product name in docs and the console. The sample tenant is still River Plumbing; the agent does not have to say the framework name on every call. Companion-site domain is still open (see 26b). |
| 2 | Google AX | **Stay out** of the call path. Not a fit yet. Reopen only if Jay asks, and only for offline sandboxes. |
| 3 | License | **Apache-2.0**. Kokoro default. Piper only as an optional HTTP sidecar so GPL does not enter the default image. |
| 4 | One-click host | **Both Fly and Railway**. Compose is the source of truth. Fly is the public-demo host (UDP). Railway is a first-class builder template; document TCP ICE / no-UDP. Test both every release. |
| 5 | Calendar | **Local ICS in v1.** Book, move, cancel against a file-backed calendar so Appointment Line is complete. Google Calendar OAuth is v1.1. |
| 6 | Public demo | **Sample tenant and sample turns only.** No uploads, no user workspaces, no outbound dial, no SMS on the companion site. |

### 26b. Still open (does not block Phase 0)

1. **Companion-site domain and GitHub org** for the public repo (develop here under `repo/` until Phase 1 is demoable, so brainstorm notes never leak).
2. **Default local STT after bake-off.** Moonshine vs sherpa-onnx streaming. Whisper is not the Talk default.
3. **Default hosted trio.** Bake-off: Deepgram + (Cartesia or ElevenLabs) + OpenAI-compatible LLM.
4. **Console CSS system.** TypeScript + one boring system.

---

## 27. Naming

**Locked:** Open Voice Agents.

| Form | Value |
| --- | --- |
| Product | Open Voice Agents |
| Slug / images / packages | `open-voice-agents` |
| Short in code | `ova` is acceptable as a prefix (`ova-runtime`), not as the public name |
| Sample tenant | River Plumbing (Appointment Line) |
| Flagship app | Knowledge Line (the document-grounded agent people fork) |

Rejected placeholders: OpenLine, Switchboard, Deskline, Signal, River-as-framework. Do not use them in new files.

---

## 28. Glossary (terms this document uses)

- **Cascade:** STT → LLM → TTS, three models.
- **Speech-to-speech (S2S):** one realtime model hears and speaks; tools still go through us.
- **Profile:** a named bundle of adapters (local, managed, s2s).
- **Adapter:** an implementation of one layer contract.
- **Knowledge Line:** the flagship app.
- **RAG-for-the-ear:** retrieval that returns a speakable sentence and a source id.
- **Policy:** deterministic gate on tools and spoken commitments.
- **Operation:** one business action the caller agreed to. Its id is minted at confirmation, journaled before the first request, and reused on every retry (7.4).
- **Specialist:** in-process skill behind one persona.
- **Seat:** where the agent sits relative to the contact center (Chapter 4). CPaaS-native is our v1 seat.
- **Containment:** calls that never reached a human. Not a success metric without task completion and CSAT.
- **Voice-to-voice:** caller stops speaking → caller hears the first audio of the reply.
- **Open Voice Agents:** this repository's product name.
- **AX:** Google Agent Executor. Sandbox runtime. Stay-out locked. Not our substrate.
- **A2A:** Agent2Agent protocol. Later interop.

---

## 29. Research log (2026-09-20)

Sources checked this session. Re-check before any number or vendor is printed in the book.

- [google/ax README](https://github.com/google/ax) — Agent Executor; Task/Workspace/Gateway/Model; K8s + Agent Substrate; preview / breaking changes.
- [Google Cloud: Agent Executor announcement](https://cloud.google.com/blog/products/ai-machine-learning/agent-executor-googles-distributed-agent-runtime) (2026-05-20).
- [A2A specification](https://a2a-protocol.org/v1.0.0/specification/) — HTTP/JSON-RPC, Agent Cards, not a media transport.
- [Twilio latency extension for A2A](https://www.twilio.com/en-us/blog/developers/latency-extension-a2a) — routing among agents by advertised latency; ConversationRelay sample; still not RTP.
- [A2A issue #997](https://github.com/a2aproject/A2A/issues/997) — WebRTC/WebTransport not official.
- [Pipecat](https://github.com/pipecat-ai/pipecat) — STT/TTS/S2S/transport catalog; local Whisper, Moonshine, Piper, Kokoro.
- [Pipecat Whisper](https://docs.pipecat.ai/api-reference/server/services/stt/whisper), [Moonshine](https://docs.pipecat.ai/api-reference/server/services/stt/moonshine), [Kokoro](https://docs.pipecat.ai/api-reference/server/services/tts/kokoro), [Piper](https://docs.pipecat.ai/api-reference/server/services/tts/piper) (GPL note on in-process Piper).
- [Pipecat telephony](https://docs.pipecat.ai/pipecat/telephony/overview) — Twilio/Telnyx/Plivo WS vs SIP.
- LiveKit vs Pipecat comparisons (2026 community writeups): LiveKit owns media/SIP; Pipecat owns pipeline/swap.
- [CoreWorxLab/local-livekit-plugins](https://github.com/CoreWorxLab/local-livekit-plugins) — documents faster-whisper **batch** vs cloud streaming (~300 ms).
- [ShayneP/local-voice-ai](https://github.com/ShayneP/local-voice-ai) — one-container LiveKit + Whisper/Nemotron + Kokoro + Ollama; closest prior art for our Compose path.
- Railway LiveKit templates — one-click WebRTC with TCP ICE limitations.
- Book files: `chapters-v6.md`, `use-cases-and-reference-stack.md`, `graded-use-cases.md`, `common-research.md`, `how-to-make-it-the-best.md`.

Prior art we should steal patterns from, not wrap blindly: `local-voice-ai` (process supervision), Comcent CE (SIP-on-a-VPS wizard), Pipecat examples (provider swap), LiveKit SIP examples (Twilio trunk scripts).

---

## 30. Acceptance checklist (Phase 3)

A reviewer should be able to walk this without us in the room.

- [ ] Clone, compose, Talk, five-turn grounded FAQ, no keys.
- [ ] Upload a new PDF; a new fact is spoken; an unknown fact is refused.
- [ ] Flip profile to managed; same dialogue; fixtures still pass.
- [ ] Buy or reuse a Twilio number; inbound call matches browser behavior.
- [ ] "Agent" transfers to the owner number with a short whisper or SMS context.
- [ ] Kill switch stops new calls.
- [ ] Companion site Talk button works on a phone browser.
- [ ] Deploy button reaches a working hosted instance.
- [ ] CI green on mocks/fixtures.
- [ ] Lock-in ledger lists every default vendor and the exit.
- [ ] No AX, no K8s, no employer name, no emergency routing, no card data.

---

## 31. Next step after this document

Section 26 locks are in. Phase 0 can start without waiting on domain, STT bake-off, or hosted-trio bake-off.

1. Freeze a short ADR: contracts + Pipecat adapter + LiveKit/Twilio + Kokoro + local ICS. Local STT listed as Moonshine-or-sherpa pending bake-off.
2. Phase 0 implementation in this folder: contracts, mock loop, browser Talk.
3. Keep chapter labs on the same contracts so the book and the app cannot drift.

Vendor defaults that are still a bake-off (local STT, hosted TTS/LLM) stay recommendations until measured. Name, license, hosts, calendar, demo policy, and AX stay-out do not.

---

## 2026-09-24 decision (Jay; recorded by Claude Fable)

The **Knowledge Line is the implementation of the book's Appointment Line.** One business, one
name: River Plumbing is the default tenant here and the example's business in the book. The
builders' volume (v9) opens with Interlude A, in which the reader runs this app before the parts
are explained. The book's delivery contract (see `brainstorm/chapters-v9-two-volumes.md`) names
this app as the one complete system; the Service Line is an assembled slice and the Disruption
Desk is architecture plus labeled simulations. Chapter numbers in this document follow v6; v9
numbering differs (for example, tools and actions is builders' Chapter 16, testing is 23).

---

## 2026-09-27 decision (Jay; recorded by Claude)

**Insurance claims is the companion's showcase tenant**, beside the Knowledge Line. The same
runtime serves both. What the Claims Line must do:

| Capability | Requirement |
| --- | --- |
| Policy questions | Answers grounded in the policy wording, one speakable sentence with a source id; the caller's own deductible and coverages only after verification; never states that a loss is covered, because the adjuster decides |
| First notice of loss by voice | Verify, check safety first (anyone hurt: emergency services, never dialed by the agent), then loss type, date and time, place, what happened, other party, police report, drivable or habitable; read the material terms back; the yes files one claim, once, under an operation id |
| Photos | A signed, expiring upload link sent by text (say it, then send it), or the camera button in the app; images checked by type and size; a photo that arrives during the call is acknowledged on it; an optional model note for the adjuster, labeled as a suggestion |
| Claim status | By claim number or by verified policy; status, next step, and date in plain words; a status link by text on request |
| Handover | A person on request without a fight: one offer when a task is half done, then the transfer; a short summary for the adjuster; a truthful callback promise when no one is free |
| Documents | Proof of insurance or the policy wording by email or text, after verification |
| Channels | Web and mobile (PWA) over WebRTC or browser voice, typing as a fallback, and a phone number (Twilio ConversationRelay or Media Streams) |

The three book examples are unchanged. The plan, the milestones, and the decisions this phase
made are in `PLAN.md`.
