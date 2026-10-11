# Architecture

The book's eight layers, as code. One process serves every surface; each business is a pack on
the same runtime.

```text
 caller ── web or mobile app ── browser voice ─┐
        ── web or mobile app ── WebRTC ────────┤
        ── web or mobile app ── typing ────────┤         transports (ova/transports, server)
        ── phone ── Twilio ConversationRelay ──┤
        ── phone ── Twilio Media Streams ──────┘
                                               │
                    audio session (ova/voice.py): turn-taking, hearing, speaking,
                    play-out tagged by line, barge-in, silence, latency per turn
                                               │
                    agent core (ova/agent.py): understanding (rules, then the brain),
                    skills as data (ova/dialogue.py), confirmation by risk, repair catalog,
                    policy gate and commitment check (ova/policy.py)
                                               │
          operations ledger and promises (ova/operations.py) ── the pack's systems of record
          channels: texts and email (ova/channels.py), signed links (ova/links.py)
          knowledge for the ear (ova/knowledge.py), store and traces (ova/store.py)
```

## A turn, end to end

1. **The caller speaks.** A transport delivers audio (WebRTC, Twilio Media Streams, raw PCM) or
   text (browser voice, typing, ConversationRelay). For audio, `TurnDetector` finds the end of
   the turn (600 ms of silence as the working value) and `STT.transcribe` returns the words.
2. **The agent reads the turn.** `ova.nlu.understand` applies the rules with a frame that says
   what the agent is waiting for (a yes, a policy number, a date). If the rules cannot place the
   turn, `ModelBrain.understand` asks the language model, and the rules validate what it
   returns: a slot must parse, an intent must exist.
3. **The agent routes it**, in the book's order of precedence: an emergency first; a person on
   request (one offer when a task is half done, then the transfer, or a truthful callback);
   repeat and help; the question it is waiting on; the active skill; a question for the
   documents; the repair catalog.
4. **A skill fills slots and confirms by risk.** Identifiers are read back in groups; the
   action's terms are read back as one question, and the yes binds that one operation.
5. **The operation runs once.** `Ledger.execute` checks the confirmation covers it (same terms,
   heard, within ninety seconds, from this response), runs the tool under an operation id,
   reconciles a timeout instead of retrying blind, and returns a result or a failure line chosen
   by class.
6. **Every line passes the policy gate** before it is queued: the never-say list, and the
   commitment check (nothing is said as done unless an operation committed, or a record read
   this turn backs it).
7. **The agent speaks.** Each line has a display form and a spoken form (numbers, dates, and
   codes as words), and records where each material term sits in the spoken form. The audio
   session tracks playout progress. Remote playback evidence varies by transport, as below;
   generated or server-drained audio is not proof of human hearing.
8. **Other channels feed back in.** A photo uploaded through a texted link, or in the app,
   reaches the live call through the hub, and the agent says so.

## The event timeline in the code

| State | Where |
| --- | --- |
| proposed | `Agent.run_action` persists the selected proposal and operation ID before execution |
| generated | `Agent.say` creates the line (after the policy gate) |
| queued | `VoiceSession._speaker` synthesizes it into the play-out |
| played | the transport reads the line's audio out of `Playout` |
| heard | Browser: completion event; Media Streams: returned, uncleared mark. WebRTC/PCM: server playout estimate only. Partial character positions are estimates, not word alignment |
| authorized | `Ledger.authorize`: the confirmation covers the terms that were heard |
| committed | the system of record wrote it; the only state the agent may speak as done |

## Why these choices

The decisions and their counters are in `../PLAN.md`. In short: our own small runtime so the
contracts stay ours and everything is testable with no network; WebRTC terminated in the
server process so one process is the whole product; rules before a model, so the acts that
must never depend on a model (yes, no, a person, digits, dates, an emergency) are code.

## Release scope

See [delivery](../../docs/delivery.md) for one-process limits, session recovery, identity and
other gaps between teaching mechanisms and this integrated application.
