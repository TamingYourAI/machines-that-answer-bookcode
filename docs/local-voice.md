# Local speech setup

Checked 2026-09-29 on macOS arm64 with Python 3.12.7. Python 3.12 is the supported
installation target; physical audio on Linux and Windows has not been exercised here.

| Profile | Recognition | Synthesis | Network boundary |
| --- | --- | --- | --- |
| `browser` | Web Speech API | Browser speechSynthesis | The browser may send audio to its recognition service |
| `local` | faster-whisper / CTranslate2, `base.en` | Kokoro ONNX | Inference uses local files; no hosted model, SMS or email provider |

Browser support varies. This application does not set `processLocally` or install browser
language packs. [MDN SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition),
checked 2026-09-29.

## Install once

From the companion root, with its environment activated:

```sh
python -m pip install -e './full-app[all,local]' -c full-app/requirements.lock
python scripts/setup_local.py
ova serve --profile local --models models
```

The setup script downloads Kokoro's two model-files-v1.1 release files and the converted
Whisper base.en weights. It records SHA-256 digests in `models/manifest.json`. Allow roughly
a gigabyte for models and download caches, plus the Python environment. Model files stay
out of Git. Sources, checked 2026-09-29:

- [Kokoro ONNX setup and model files](https://github.com/thewh1teagle/kokoro-onnx)
- [faster-whisper setup](https://github.com/SYSTRAN/faster-whisper)
- [Converted base.en model](https://huggingface.co/Systran/faster-whisper-base.en)

Library and model licenses belong to their respective authors. The companion's Apache
license does not replace those terms. Models are fetched, not redistributed here.

## Use it

Open http://127.0.0.1:8080, choose **Server voice**, and allow microphone access. Claims is
the initial line; River Plumbing is in the selector. Loading the first model takes longer
than later turns. Recognition processes complete utterances after 600 ms of silence; it
does not stream partial transcripts or use a native speech-to-speech model.

Local understanding is rule based. It handles the supported workflows and supplied
knowledge questions; it is not an unrestricted conversational LLM. Text entry helps inspect
exactly where a workflow accepts or rejects a phrase. Browser voice pauses recognition
while speaking; use its interruption control to cut in. Server voice processes incoming
audio during playout.

## Reproduce the checks

```sh
python scripts/check_local_voice.py --pack claims --output test-results/local-claims
python scripts/check_local_voice.py --pack river --output test-results/local-voice
python -m pip install playwright
python -m playwright install chromium
python scripts/check_local_webrtc.py
```

The first two synthesize a caller, transcribe it, execute the dialogue and synthesize the
reply. They block `socket.connect` during inference. The last uses the generated River WAV
as Chromium's fake microphone with actual local models and received RTP audio. It does not
use a physical microphone or prove that a person heard the reply.

## Troubleshooting

- **Missing models:** run setup from the companion root, or supply an absolute `--models`
  path. Startup checks the files before accepting calls.
- **Server voice unavailable:** install both `webrtc` and `local` extras in the environment
  running `ova`, and use `--profile local`.
- **Microphone denied:** permit the site in browser and operating-system audio settings.
  Use localhost, or HTTPS when operating on another device.
- **Slow first turn:** wait for initialization and inspect the server log for model errors.
  A scripted recognizer or tone voice is a test double, not a performance fix.
- **Another device cannot connect:** the verified path is localhost. Deployment networking
  and TURN are separate configuration; `OVA_ICE_SERVERS` accepts JSON.
- **Install fails on newer Python:** use Python 3.12, the declared supported version.
