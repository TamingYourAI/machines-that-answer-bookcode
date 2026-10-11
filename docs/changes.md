# Changes

## 0.3.1, 4 October 2026

1. **The container matches the package.** The Dockerfile starts from Python 3.12, which the
   package requires, and installs with the lock file's constraints (it had used 3.11). The
   same install command, run outside a container on Python 3.12.14 (macOS arm64, 3 October),
   installs and serves the Knowledge Line with River Plumbing as the default. Built under Docker
   Desktop (macOS arm64), the image is healthy in 2 seconds and books a visit over `/ws/talk`;
   an x86_64 host is still untried.
2. **The kill switch stops a write it finds not yet started.** Pressed while a caller's yes
   is still being understood, the switch refuses the booking that turn was about to make, and
   the caller goes where the switch sends calls: River Plumbing's owner. A write already
   running completes and is read back as before. A regression test presses the switch
   mid-turn.
3. **A caller's free text loses what the recognizer added at its edges.** Whisper once heard
   "Jordan." as "Jordan. //", and the booking kept the slashes; free-text slots now drop stray
   punctuation and symbols at both ends (89 application tests).

## 0.3.0, 3 October 2026

1. **The Knowledge Line opens on River Plumbing**, as the book's preface, Chapter 1 and
   Interlude A describe it (Jay's decision of 3 October). `OVA_DEFAULT_PACK` picks another
   line; the claims showcase stays at `/?pack=claims`. The page, console and app manifest are
   titled "Knowledge Line", and `ova talk` defaults to River Plumbing.
2. **The kill switch reaches the owner at any hour.** A pack names where calls go while the
   switch is on (`switch_route`); River Plumbing sends them to the owner, as Interlude A
   says. A line closed for the night says when to call back in plain words.
3. **Every builders' lab is in.** Chapters 23 to 29, Interlude B and Appendix M join the
   23 labs of 0.2.0, and the labs the book revised since are refreshed. `scripts/sync_labs.py`
   copies them with their READMEs, manifest and source hashes.
4. **The delivery table lists the kill switch and the per-turn stage timings**, which the
   book's Table 1.7 and Chapter 1 promise.

## 0.2.0: changes from the authoring snapshot

Provenance is in [source-snapshot.json](source-snapshot.json). Chapter labs are exported
intact, including the final Chapter 20 authentication-method correction. Application and
release-tooling changes follow.

1. **Operation identity survives a transport change.** The source derived IDs from a call
   and proposal. This release mints one per action, persists it before execution, and accepts
   the same ID on retry. A fingerprint binds pack, subject, tool and terms. Replay checks
   current authorization. Failed read-back leaves an unknown outcome; no blind resubmission
   occurs. Concurrent retries share a lock in one runtime. Tests cover restart, scope,
   authorization and timeout cases.
2. **Phone playback acknowledgment follows audio.** Media Streams sends a mark after a
   line's PCM drains. Only a returned, pending mark acknowledges it. Clear invalidates
   pending marks first, following [Twilio's media/mark/clear contract](https://www.twilio.com/docs/voice/media-streams/websocket-messages),
   checked 2026-09-29. Carrier validation is still open.
3. **Queued browser speech cannot authorize an action.** A premature yes triggers full
   read-back. Queued server audio counts as zero played characters.
4. **Failed document delivery is not announced as successful.** A failed sender result
   fails its operation. Simulated delivery stays labeled in the outbox and UI.
5. **The wheel includes the UI.** HTML, JavaScript, manifest, icons and policy data ship in
   the package. Asset lookup no longer depends on the working directory.
6. **Explicit browser/local/configured profiles.** The first two cannot accidentally use a
   paid provider from a shell key. Local startup validates models. The CLI binds to localhost
   and can read an explicitly selected env file.
7. **Independent reader workflow.** Chapter READMEs, manifest, lab runner, constraints,
   model setup, actual local audio checks, wheel checks, CI and evidence records are added.

The ledger remains single-process. External writes still require provider-side idempotency.
Old ledger rows without a fingerprint fail closed on replay. Use a fresh demo database or
design an audited migration before carrying real history forward. A fresh confirmation
must satisfy current policy even on replay.

The last authorized operation is persisted, but authenticated call-resume UX is not built.
WebRTC playout remains an estimate; it does not establish exactly what a human heard.
