# Providers and their evidence classes

Every layer is swappable, and nothing is required. Each adapter below carries an evidence
class, the book's way of saying what backs a claim:

- **tested here**: run by this repository's tests on real code paths;
- **tested against a fake**: our requests and our parsing are tested against a local fake of
  the provider's documented API (`tests/test_providers.py`); not yet run against the service;
- **written to the docs**: written from the provider's or library's documentation, not run.

Updated 2026-09-29: actual local Whisper/Kokoro inference and a Chromium WebRTC exchange
passed with synthetic caller audio. Hosted speech and telephony remain unverified against
live services. The release evidence and measurement boundaries are in
[validation](../../docs/validation.md). Browser/local CLI profiles override hosted selections;
the environment selectors below apply to `--profile configured`.

| Layer | Adapter | Select with | Evidence | Notes |
| --- | --- | --- | --- | --- |
| Hearing | Browser (Web Speech API) | the app's "Browser voice" | simulated speech APIs in Chromium; actual recognition unverified | The browser may use online recognition; see the local setup guide |
| Hearing | Deepgram, pre-recorded REST | `DEEPGRAM_API_KEY` or `OVA_STT=deepgram` | tested against a fake | Segment recognition after the turn ends; streaming with partials is M2 |
| Hearing | OpenAI transcriptions | `OPENAI_API_KEY`, `OVA_STT=openai` | tested against a fake | Works with compatible servers via `OPENAI_BASE_URL` |
| Hearing | faster-whisper, local | `OVA_STT=whisper` | live laboratory, synthetic caller | Use the local profile and setup script; segment recognition after the turn ends |
| Hearing | Scripted | `OVA_STT=script`, `OVA_STT_SCRIPT` | tested here | Simulated: returns the next line whatever was said. Tests and demos only |
| Speaking | Browser (speechSynthesis) | "Browser voice" | tested here in part | Voices vary by browser and device |
| Speaking | ElevenLabs, streaming | `ELEVENLABS_API_KEY`, `OVA_ELEVENLABS_VOICE` | tested against a fake | `pcm_16000` output |
| Speaking | Deepgram Aura | `DEEPGRAM_API_KEY` | tested against a fake | linear16, 16 kHz, no container |
| Speaking | OpenAI speech | `OPENAI_API_KEY`, `OVA_TTS=openai` | tested against a fake | 24 kHz PCM |
| Speaking | Kokoro (ONNX), local | `OVA_TTS=kokoro` | live laboratory, synthetic caller | Local ONNX weights, no key; see model sources in the local setup guide |
| Speaking | Piper HTTP sidecar | `OVA_TTS=piper`, `OVA_PIPER_URL` | written to the docs | Separate service, not bundled or verified here |
| Speaking | Tones | `OVA_TTS=tones` | tested here | Simulated: soft tones, no words. Tests the pipeline and barge-in |
| Model | Anthropic Messages | `OVA_LLM=anthropic`, `ANTHROPIC_API_KEY`, `OVA_LLM_MODEL` | tested against a fake | Used for leftovers and phrasing only; photo notes when `OVA_VISION` is on |
| Model | OpenAI-compatible (OpenAI, Ollama, vLLM) | `OVA_LLM=openai` or `ollama`, `OVA_LLM_MODEL`, `OVA_LLM_BASE_URL` | tested against a fake | Same |
| Model | Rules only | default | tested here | The agent works fully without a model; answers are extractive |
| Transport | WebRTC (aiortc) | the app's "Server voice" | tested here (aiortc loopback, and Chromium with a fake microphone) | Needs a hearing and a speaking provider; TURN via `OVA_ICE_SERVERS` behind strict NAT |
| Transport | Twilio ConversationRelay | `OVA_PHONE_MODE=relay` | tested against simulated messages | Message shapes from Twilio's docs, reached through search on 2026-09-27 |
| Transport | Twilio Media Streams | `OVA_PHONE_MODE=media` | tested against simulated messages | mu-law 8 kHz; barge-in sends `clear` |
| Channel | Twilio SMS | `TWILIO_*` | tested against a fake | Without it, texts are simulated and shown in the app and console |
| Channel | SMTP email | `SMTP_*` | written to the docs | Without it, email is simulated |

## Model ids

No language-model id is built in. Set `OVA_LLM_MODEL` to a current, fast model from your
provider: the turn model is called only for what the rules cannot place, inside a 1.5 second
budget, and its output is checked by the rules. Grounded answers must cite the passages they
were given and may not state a number those passages do not contain; otherwise the extractive
answer is used.

## Measurement boundaries

Earlier scripted-hearing/tone measurements are historical test-fixture timings, not real
speech latency. Local batch timings include caller synthesis, recognition, dialogue and
reply synthesis. Neither is caller-perceived end-to-end latency. See the release validation
record for the actual measurements and the checks still pending.
