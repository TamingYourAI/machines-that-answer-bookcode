# Validation record

## Release 0.3.2, 11 October 2026

**VERIFIABLE, high confidence**, on macOS arm64 with Python 3.12.7. No result here is field
evidence.

| Check | Result | Evidence boundary |
| --- | --- | --- |
| Application suite | 91 pass, including loop detection (`test_the_same_turn_three_times_running_offers_a_person`) and the test server's reset to the seeds | Unit and integration tests, synthetic records |
| The test suite's own tests | 14 pass, including a text run that books a visit on the app over a real WebSocket | Fixed clock, synthetic records |
| Scenarios | All eight pass builders' Appendix M validator | The format, not behavior |
| Text runner on the app | Seven scenarios, 20 runs each, with the records reset before every run: every run passed both families | Simulated: the caller's words arrive as text |
| Audio runner on the app | Eight scenarios, 3 runs each, real-time 16 kHz audio, local Whisper and Kokoro: the task family passed every run. The response gap's median per scenario was 1.5 to 2.7 s and its p95 up to 4.3 s, against the book's 800 ms wall. `tt-01` was cut off in every run, by the fixed 600 ms end-of-turn wait | Live laboratory, synthetic caller, one machine; three runs per scenario are not a rate |
| Not rerun for 0.3.2 | The container, the wheel smoke test, and the browser checks below; 0.3.2 changes the agent's turn loop, the console API, and adds `evals/` | Rerun before the next container release |

The suite's reports, with every run's checks, are in `evals/results/2026-10-11-open-voice-agents-0.3.2/`.

## Release 0.3.1, 4 October 2026

4 October 2026, release 0.3.1. **VERIFIABLE, high confidence:** the local checks below
completed on macOS arm64. The [machine-readable summary](evidence/release-validation.json)
and linked evidence state exactly what was exercised. No result here is field evidence.
Every row was run for 0.3.1.

| Check | Result | Evidence boundary |
| --- | --- | --- |
| 32 chapter labs | 515 tests pass on Python 3.12.7, 3.13.15 and 3.14.7; mock and fixture outputs match their saved outputs | Simulated mechanisms and synthetic fixtures |
| Application suite | 89 pass on Python 3.12.7, including the River Plumbing default, the kill switch to the owner at night, the switch pressed mid-turn refusing the booking it was about to make, and a recognizer's stray symbols kept out of a caller's name | Unit, conversation, provider fakes, in-process server, aiortc loopback and regression tests |
| Browser, default line | `/` opens River Plumbing as the Knowledge Line | Chromium with synthetic records |
| Browser claims | Complete typed claim, photo upload during call, phone link, status, console, at `/?pack=claims` | Chromium with synthetic records |
| Browser speech state machine | 13 caller turns, 15 lines spoken/reported heard, claim filed | Scripted Web Speech stand-ins; no actual browser recognizer |
| Browser WebRTC with fakes | River Plumbing: caller speech event and next question | Fake microphone, scripted recognizer and tone audio |
| Local appointment | 6 synthesized turns; one booking for Jordan, the fee read before the yes | Real Whisper and Kokoro, batch core path, outbound socket connections blocked |
| Local claims | 10 synthesized caller turns at `--pack claims`; one claim filed | Same local inference boundary |
| Local WebRTC | Recognizes “My kitchen drain is blocked”; asks for address; browser receives RTP audio | Actual local models; Chromium file-backed fake microphone; 855 received audio packets in that run |
| Built wheel 0.3.1 | UI, static assets, synthetic records and API work from a fresh venv outside checkout | Installed package, no source-directory fallback |
| Container 0.3.1 | The image builds (Python 3.12.15, 393 MB) and is healthy within 2 s; `/` serves the Knowledge Line with River Plumbing as default; a typed call over `/ws/talk` books Wednesday at 9 am with the $60 charge read before the yes, and its text lands in the demonstration outbox | Docker Desktop on macOS arm64; no x86_64 host; no local models in the image |
| Source export | `scripts/export_release.py` writes 308 files to `dist/open-voice-agents-0.3.1.zip`; not published | The archive's file selection, not its publication |
| Source drift | Every exported lab matches the authoring tree at the sync commit | Read-only hash comparison against `docs/source-snapshot.json` |

One dependency warning remains: Starlette's TestClient warns about its deprecated `httpx`
path. It does not fail these tests; dependency compatibility remains part of routine upkeep.

## Run the deterministic checks

From the companion root, with its environment activated:

```sh
python scripts/run_labs.py --check --report test-results/labs.json
python -m pytest full-app/tests -q
python -m pip install build
python -m build full-app
python scripts/smoke_wheel.py
```

The wheel check downloads its constrained server dependencies into a temporary environment.
The chapter tests and installed application suite do not call paid services.

## Browser checks

```sh
python -m pip install playwright==1.63.0
python -m playwright install chromium
OVA_PYTHON="$PWD/.venv/bin/python" PW_PYTHON="$PWD/.venv/bin/python" bash full-app/tests/browser/run.sh "$PWD/test-results/browser"
```

This starts a temporary server and shuts it down afterwards. Its browser speech APIs are
stand-ins. A successful result proves the application state transitions, not microphone
recognition quality. Screenshots and server logs are local ignored artifacts.

## Real local speech checks

After [installing the local models](local-voice.md):

```sh
python scripts/check_local_voice.py --pack claims --output test-results/local-claims
python scripts/check_local_voice.py --pack river --output test-results/local-voice
python scripts/check_local_webrtc.py
```

The first two tests block Python socket connections while the actual models execute.
Their batch timings include synthesis of the caller, transcription, dialogue and reply
synthesis. They must not be quoted as voice-to-voice latency. The WebRTC check is a
separate local process and does not impose that socket block. It uses local providers and
an empty ICE-server list; it establishes an audio transport exchange, not a network audit.

The local batch test uses the text-core confirmation semantics. The WebRTC audio check
covers one recognized caller turn, not a complete voice-confirmed transaction. Tests of
unheard confirmations and remote marks are separately in the application suite.

The WebRTC screenshot displayed about 1.66 seconds for that one server-measured reply.
That is one synthetic turn on one host, not a percentile, physical-speaker measurement or
performance target. No comparative model benchmark was performed.

## Saved evidence

- [Chapter checks](evidence/labs.json)
- [Application console result](evidence/pytest.txt)
- [Browser console result](evidence/browser.txt)
- [Real local claims transcript](evidence/local-claims.json)
- [Real local appointment transcript](evidence/local-river.json)
- [Real local WebRTC result](evidence/local-webrtc.json)
- [Model sources and SHA-256 digests](evidence/model-manifest.json)

Every identity and business record in this evidence is synthetic. Generated test WAVs are
kept locally under `test-results/`, not in the release archive.

## Remaining acceptance work

Physical microphone and speaker behavior, a human listening session, browser-vendor
recognition, real Twilio/SMS/SMTP calls, remote-device networking, a container on an x86_64 host,
GitHub-hosted CI, sustained load and field outcomes remain unverified. Production SSO,
distributed operation, native speech-to-speech and later application packs are also outside
this release's implementation, as listed in [delivery](delivery.md).
