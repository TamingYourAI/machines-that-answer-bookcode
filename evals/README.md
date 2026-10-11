# The voice-agent test suite

One test suite for any voice agent, whatever is inside it: a pipeline of recognizer, model, and
voice, or a speech-to-speech model. It meets the agent the way a caller does, then checks what
happened in the agent's own records. It is the scenario runners of *Machines That Answer*,
Chapter 25, built.

- **The book's own format.** Every scenario is in builders' Appendix M's format and passes the
  book's validator (`chapters/appendix-m`).
- **Two families, never one score.** Every report shows the task family (was the work done, and
  done honestly) and the experience family (how the call went) side by side (Chapter 24). A
  system strong on one and weak on the other looks exactly like that.
- **Rates, not verdicts.** Each scenario runs many times. Each family's result is a count of runs
  with its Wilson 95 percent interval, and a scenario is judged against its own rule only when it
  has had all its runs (Chapter 25).

It is not a leaderboard, and its author does not test commercial products on his own initiative.
See [Testing a commercial product](#testing-a-commercial-product).

## Run it on the companion app

From the companion's root, with its environment active (see the main README):

```sh
ova serve --profile browser &          # the Knowledge Line, typing and browser voice
cd evals
python -m voice_eval validate
python -m voice_eval run --url http://127.0.0.1:8080 --runs 5
```

The text runner is fast, needs no keys, and is the one CI runs. It tests the agent's decisions
and its records. It cannot test its ears or its voice.

The audio runner needs the local speech models (`python scripts/setup_local.py`) and a server
with server voice:

```sh
ova serve --profile local --models models --port 8093 &
python -m voice_eval run --url http://127.0.0.1:8093 --runner audio --runs 3
```

The caller speaks with the local Kokoro voice, in a voice unlike the agent's, in real time, in
20 ms packets. The scenario's line conditions are applied to its audio first: noise, the phone
codec, and lost packets (`voice_eval/conditions.py`). The runner times the agent's audio packet by
packet. An audio run takes as long as a call does.

Each run writes `report-<runner>.md` and `report-<runner>.json` to `--out` (default
`eval-results/`). Use `--runs 1` for a smoke test. It is not a rate, and the report says "not
judged".

## The scenarios

| Scenario | Line | What it tests | Runners |
| --- | --- | --- | --- |
| `or-01` | River Plumbing | Interlude A's call: a booking, the fee before the yes, "booked" only after the commit, the text | text, audio |
| `or-02` | River Plumbing | Wednesday turned down, Thursday booked | text, audio |
| `or-03` | River Plumbing | A caller who repeats the same request: the agent must not loop | text, audio |
| `th-01` | River Plumbing | A gas smell: the safety script, and nothing booked | text, audio |
| `th-02` | River Plumbing | The call-out price, from the desk's facts | text, audio |
| `th-03` | River Plumbing | Saturday visits, from the desk's facts | text, audio |
| `tt-01` | River Plumbing | A 700 ms pause in the middle of the address: no cut-off | audio |
| `sr-01` | Claims line | A cracked windshield, reported and filed; never "you're covered" | text, audio |

The suite adds one optional field to Appendix M's format: `caller.answers`, a list of
`[pattern, words]`. After each agent turn, the caller answers with the first unused answer whose
pattern is found in the agent's last line. An answer is used again only when the question is
asked again. Without answers, or when none matches, the caller says the next of `caller.lines` in
order. Answers let one scenario survive an agent that asks for the name before the address.

## The checks

| Key | Family | Passes when |
| --- | --- | --- |
| `booked` | task | A booking operation committed; with a day, the booked line names it |
| `bookings` | task | Exactly this many booking operations committed |
| `no_booking` | task | No booking operation committed |
| `fee_before_yes` | task | A line carrying the fee came before the caller's yes that the booking bound |
| `confirmed_after_commit` | task | Every "booked" line came after the operation committed |
| `safety_script` | task | The gas safety line was said, and nothing was booked |
| `transferred` | task | The call ended in a transfer to a person |
| `texted` | task | A text was sent |
| `claim_filed` | task | A claim was filed |
| `said`, `never_said` | task | Each pattern was, or was never, in the agent's lines |
| `turns_max` | experience | The caller needed at most this many turns |
| `same_turn_max` | experience | The agent never said the same turn more than this many times in a row |
| `cut_off` | experience | False: no caller turn was ended inside a pause the caller left (audio) |
| `gap_p95_ms_max` | experience | The p95 of response gaps was at most this (audio) |
| `talk_over_max` | experience | The agent began to speak over the caller at most this many times (audio) |

A check the runner cannot make is reported as not checked, never as passed. A key the suite does
not know fails the family it was meant for.

## Testing another system

A system under test needs three things:

1. **The text protocol** (`voice_eval/runners/text.py`), the audio protocol
   (`voice_eval/runners/audio.py`), or both, over a WebSocket. The companion app's `/ws/talk` and
   `/ws/audio` are the reference.
2. **Its records for each call**, for the task family. This release reads them through the
   companion's console API (`GET /api/admin/calls/<id>`). Another system can expose the same shape
   (`voice_eval/records.py`).
3. **Its name and version**, passed as `--name` and `--version`, so the report says what was
   tested.

Planned:
- a phone runner, which calls a real number;
- a tool service, which records the writes of a system whose records cannot be read.

## What the companion app scored

The first results are from 11 October 2026, on one Mac (Apple silicon), with the app and the
suite on the same machine. They are in
[`results/2026-10-11-open-voice-agents-0.3.2/`](results/2026-10-11-open-voice-agents-0.3.2/),
reported as found.

- **Text runner, 20 runs of each of the seven text scenarios:** every run passed both families.
  Each scenario met its rule, at 84 to 100 percent with 95 percent confidence.
- **Audio runner, 3 runs of each of the eight scenarios, local Whisper and Kokoro:**
  - **Task family:** the work was done in every run.
  - **Experience family:** two failures.
    - **Response gaps:** with local speech on the laptop's processor, the median gap per
      scenario was 1.5 to 2.7 seconds and the p95 up to 4.3 seconds. The book's wall is 800 ms
      at p95; `or-01`, the one scenario that asserts it, fails it in every run.
    - **`tt-01`:** the app's fixed 600 ms end-of-turn wait ended the caller's turn inside a
      700 ms pause in every run. The address was recorded as "12" and the street became the
      caller's name. This is the failure builders' Chapter 11 describes.
  - **Not judged:** three runs per scenario are a smoke test, not a rate.
- **A bug the suite found, and 0.3.2 fixed:** the first text runs found a loop. A caller who
  repeated a request heard the same offer ten times and more, because every reply was understood
  and nothing counted as a failure. Release 0.3.2 adds loop detection (builders' Chapter 18), and
  `or-03` keeps it fixed.

## Evidence classes

- **A text run:** simulated.
- **An audio run with the synthetic caller:** live laboratory, with real recognition and synthesis
  under stated conditions, and no person on the line.
- **Field evidence:** never, from this suite. Only real callers on a production line give it.

## Testing a commercial product

The suite is open so that anyone can run it on a system they have the right to test. Its author
does not test commercial products on his own initiative, and publishes no comparison of them.

A provider that wants its system run can ask: open a
[Run request](https://github.com/TamingYourAI/machines-that-answer-bookcode/issues/new?template=run-request.yml) issue. The author decides which
requests to take. Results go to the provider first, and are published only with the provider's
agreement, with the conditions and evidence class of every number. Never put credentials or a
private endpoint in an issue. Those are arranged after a reply.

## Credits and license

The suite's ideas meet published work: the tau-Voice benchmark (Sierra with Princeton) and
EVA-Bench (ServiceNow AI Research). Both are MIT-licensed and cited in the book, and this suite
shares no code with either. The suite is Apache-2.0, like the rest of the companion.
