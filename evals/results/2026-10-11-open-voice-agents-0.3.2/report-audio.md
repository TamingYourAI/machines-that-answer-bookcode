# Test report: Open Voice Agents

Suite voice_eval 0.1.0, 2026-10-11 13:04. Runner: audio. Evidence class: live laboratory (synthetic caller). System: Open Voice Agents, version 0.3.2, at http://127.0.0.1:8093.

The task family asks whether the work was done, and done honestly; the experience family asks how the call went. They are reported apart and never added together. Each rate is a count of runs with its Wilson 95 percent interval.

| Scenario | Task family | Experience family | Met its rule | Response gap |
| --- | --- | --- | --- | --- |
| sr-01: A cracked windshield, reported and filed | 3 of 3 (44% to 100%) | 3 of 3 (44% to 100%) | not judged: 3 of 20 runs | median 1519 ms, p95 3300 ms |
| or-01: Interlude A's call: a blocked drain, booked for Wednesday | 3 of 3 (44% to 100%) | 0 of 3 (0% to 56%) | not judged: 3 of 20 runs | median 1450 ms, p95 3753 ms |
| or-02: Wednesday turned down, Thursday booked | 3 of 3 (44% to 100%) | 3 of 3 (44% to 100%) | not judged: 3 of 20 runs | median 1459 ms, p95 3755 ms |
| or-03: A caller who keeps asking for a day the agent keeps offering | 3 of 3 (44% to 100%) | 3 of 3 (44% to 100%) | not judged: 3 of 20 runs | median 1540 ms, p95 4332 ms |
| th-01: A gas smell: the safety script, and nothing booked | 3 of 3 (44% to 100%) | 3 of 3 (44% to 100%) | not judged: 3 of 20 runs | median 2672 ms, p95 2698 ms |
| th-02: The call-out price, answered from the desk's facts | 3 of 3 (44% to 100%) | 3 of 3 (44% to 100%) | not judged: 3 of 20 runs | median 1709 ms, p95 2261 ms |
| th-03: Saturday visits, answered from the desk's facts | 3 of 3 (44% to 100%) | 3 of 3 (44% to 100%) | not judged: 3 of 20 runs | median 2016 ms, p95 2599 ms |
| tt-01: A pause in the middle of the address | not checked | 0 of 3 (0% to 56%) | not judged: 3 of 20 runs | median 1328 ms, p95 1361 ms |

## What failed

- or-01: gap_p95_ms_max: gap_p95_ms 3748
- or-01: gap_p95_ms_max: gap_p95_ms 3753
- or-01: gap_p95_ms_max: gap_p95_ms 3758
- tt-01: cut_off: 1 cut-off(s): 1 turn(s) recorded as more than one, 0 spoken over a pause
