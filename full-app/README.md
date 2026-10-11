# Open Voice Agents application

The book's Knowledge Line: a complete local application that opens on River Plumbing's
Appointment Line, with an insurance-claims line as a second showcase (`/?pack=claims`, or
`OVA_DEFAULT_PACK=claims`). Both use one dialogue runtime, operation ledger, SQLite store, browser UI, uploads,
status pages, operator console and voice transports. Start at the [companion README](../README.md).

## Run from this directory

Use Python 3.12 and activate the companion environment:

```sh
python -m pip install -e '.[all]' -c requirements.lock
ova serve --profile browser
```

Open http://127.0.0.1:8080. This profile disables hosted speech/model/vision providers and
external email/SMS even if keys are in the shell. Browser recognition itself may still use
an online service. For local models:

```sh
python -m pip install -e '.[all,local]' -c requirements.lock
python ../scripts/setup_local.py
ova serve --profile local --models ../models
```

Choose **Server voice**. [Local speech details](../docs/local-voice.md).

`ova talk` (River Plumbing) and `ova talk --pack claims` run the text core in a terminal with
an in-memory store. No web server or audio libraries are needed for terminal use.

## Configuration

To deliberately select external providers, copy `.env.example` to `.env`, set the values,
and run `ova serve --profile configured --env-file .env`. Shell values take precedence.
[Provider status](docs/providers.md) and [phone setup](docs/telephony.md) explain the adapters.

The server persists data under `data/` in the working directory, or `OVA_DATA_DIR`. Its
console is open and demo sign-in enabled by default; the CLI binds to localhost. Real
customer deployment needs an application-specific authentication and access design. An
admin token alone is not that design.

## Structure

| Package | Responsibility |
| --- | --- |
| `src/ova/` | Dialogue, confirmation, business operations, promises, speech, retrieval, traces |
| `src/ova_apps/claims/` | Policy service, first notice of loss, photos, status, synthetic records |
| `src/ova_apps/river_plumbing/` | Appointment booking on the same contracts |
| `src/ova_server/` | FastAPI, CLI, settings, packaged HTML/JS/PWA assets |
| `tests/` | Unit, conversation, provider-fake, server and WebRTC checks |

See [architecture](docs/architecture.md), [changes](../docs/changes.md) and
[delivery boundaries](../docs/delivery.md). `PLAN.md` and `REQUIREMENTS.md` preserve the
original broader product plan; planned features are not all implemented in this release.

## Containers

`docker compose up --build` serves browser/text mode on localhost:8080 with a persistent
volume. The image has no local model weights. The image was built and run under Docker Desktop
on macOS arm64 on 3 October 2026 (see docs/validation.md); an x86_64 host has not been tried,
and server voice also needs appropriate UDP/ICE networking. External providers require an
explicit command override: `ova serve --profile configured --host 0.0.0.0 --port 8080`.

## Tests

Run `python -m pytest -q`. [Validation](../docs/validation.md) has browser, wheel and local
speech commands. Scripted recognition and tone audio are labeled simulations. Apache-2.0.
