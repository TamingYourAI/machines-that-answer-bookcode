# Open Voice Agents: the book companion

Runnable chapter labs and a complete local application for Jay Gopalan's *Machines That
Answer* and *Every Call Answered*. The application is the book's **Knowledge Line**: it
opens on River Plumbing's Appointment Line, the simple example the book walks through, and
carries an insurance-claims line as a second showcase on the same framework.

**Release 0.3.1, 4 October 2026.** Every builders' lab is included: Chapters 1 to 29,
Interludes A and B, and Appendix M, checked on Python 3.12, 3.13 and 3.14. The
[delivery table](docs/delivery.md) says what the application implements, what the labs
only simulate, and what neither does. Apache-2.0 covers the code. Manuscripts and model
weights are not bundled.

## Start the Knowledge Line

Use **Python 3.12**. From this folder:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e './full-app[all]' -c full-app/requirements.lock
ova serve --profile browser
```

Open **http://127.0.0.1:8080**. It opens on River Plumbing. Choose **Type** for the
quickest complete demonstration, or **Browser voice** and allow microphone access in a
supported browser. No API key is needed. Browser recognition can use an online service;
this mode does not guarantee offline speech.
[Browser behavior](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).

Try the book's call from Interlude A:

1. "My kitchen drain is blocked."
2. Give an address, a name, and a day. The agent reads back the time and the $60 call-out
   charge before it books, and texts the booking (see **Texts**).
3. Ask "How much is a call-out?" or "Are you open on Saturday?"
4. Open the console at `/admin` to see the transcript, the operation ledger, and the
   **kill switch**: with it on, every call goes straight to the owner, at any hour.

All people, appointments, policies and business records are synthetic. Texts and emails
appear in the demonstration outbox; the browser and local profiles do not send them.

### The claims showcase

Open `/?pack=claims`, or start with `OVA_DEFAULT_PACK=claims`, for the invented insurer
Quillmere Mutual:

1. "My windshield cracked this morning."
2. Policy **481273**, confirm it, then date of birth **March 4, 1985**.
3. Answer the incident questions and confirm the summary.
4. Upload a photo through the card or the link in **Texts**.
5. Open the claim-status link.

## Speak through local models

Install and download once, then run recognition and synthesis on this machine:

```sh
python -m pip install -e './full-app[all,local]' -c full-app/requirements.lock
python scripts/setup_local.py
ova serve --profile local --models models
```

Open the same page and choose **Server voice**. This uses WebRTC, faster-whisper's `base.en`
model, Kokoro ONNX and deterministic dialogue rules. No language-model service is required.
Wait for the first greeting while the models load. Downloads require internet access;
inference uses local files. [Local setup and troubleshooting](docs/local-voice.md).

## Run one chapter, or all chapters

Each chapter folder has independent code, fixtures, expected output, tests and a README.
The labs need only the Python standard library.

```sh
python scripts/run_labs.py ch17
python scripts/run_labs.py ch17 --mode fixture
python scripts/run_labs.py --check
```

The last command checks both modes against saved output and runs all lab tests. Start at
the [chapter index](chapters/README.md). These isolated simulations are not production
benchmarks or interchangeable pieces of the integrated application.

## Repository map

| Location | Contents |
| --- | --- |
| [chapters/](chapters/README.md) | 32 independent labs: builders' Chapters 1 to 29, Interludes A and B, and Appendix M |
| [full-app/](full-app/README.md) | The Knowledge Line: runtime, River Plumbing and claims packs, browser UI, persistence, uploads, console with kill switch, voice transports |
| [docs/delivery.md](docs/delivery.md) | Implemented, simulated and planned capabilities |
| [docs/validation.md](docs/validation.md) | Checks and their evidence boundaries |
| [docs/release.md](docs/release.md) | GitHub preparation, provenance and dependency notes |
| [docs/changes.md](docs/changes.md) | Fixes beyond the source snapshot |

## Verify

```sh
python -m pytest full-app/tests -q
python -m pip install build
python -m build full-app
python scripts/smoke_wheel.py
```

The wheel check installs into a fresh environment, changes to an unrelated directory,
and checks packaged assets and policy data. More checks are in [validation](docs/validation.md).
GitHub Actions is configured for Python 3.12; the workflow has not run on GitHub yet.

This is a working single-process reference application. Live telephone calls, physical
device listening, distributed operation and production identity integration remain
unverified or unimplemented, as specified in the delivery table.
