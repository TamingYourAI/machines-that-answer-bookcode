# Putting a phone number on it (Twilio)

Two ways to connect one Twilio number, chosen with `OVA_PHONE_MODE`.
Use `ova serve --profile configured --env-file .env` for this setup. The browser and local
profiles deliberately disable external messaging credentials. These adapters have only
been checked against fakes and simulated messages, not a live carrier call.

| Mode | Who hears and speaks | You need | Barge-in |
| --- | --- | --- | --- |
| `relay` (default) | Twilio (ConversationRelay) | A Twilio account | Twilio stops speaking and tells us how much of the reply was played |
| `media` | Our providers (Media Streams) | A Twilio account, a hearing and a speaking provider | Our turn detector; we send `clear` |

## Steps

1. Run the server somewhere Twilio can reach over HTTPS and WSS (a VPS behind Caddy, Fly, or a
   tunnel for testing). Set `OVA_PUBLIC_URL` to that address.
2. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER`. With the auth token
   set, every webhook's `X-Twilio-Signature` is checked; requests that fail get a 403.
3. In the Twilio console, set the number's voice webhook to `POST <OVA_PUBLIC_URL>/twilio/voice`
   (add `?pack=river` for River Plumbing). The server answers with TwiML that connects the call
   to `/twilio/relay` or `/twilio/media`.
4. Set `OVA_CLAIMS_TRANSFER_NUMBER` (or `OVA_RIVER_OWNER_NUMBER`) so a transfer has somewhere
   to go. In relay mode the agent ends the session with the transfer in `handoffData`, and
   `/twilio/relay-action` answers with a `<Dial>`. In media mode the server redirects the live
   call to a `<Dial>` through Twilio's REST API.
5. Call the number. The first sentence says it is an automated assistant.

## What the agent never does on the phone

It never dials an emergency number: the safety line tells the caller to hang up and call. It
texts links only to the number on the policy, never to a number the caller dictates. Its
outbound calls are callbacks a person makes from the console's promise list; there is no dialer.

## Evidence

The TwiML and WebSocket message shapes were written to Twilio's documentation (the pages were
reached through search on 2026-09-27; the container could not fetch them directly) and are
tested against simulated Twilio messages in `tests/test_server.py`. No live call has been placed
from this repository yet.
