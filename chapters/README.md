# Chapter labs

Each folder is independently runnable with Python 3.12 or later and no third-party packages.
Mock and fixture inputs are synthetic. Neither mode is a live provider benchmark.

| Chapter | Lab |
| --- | --- |
| [1. A call is a system, not a chat with a microphone](ch01/README.md) | `call_budget_lab.py` |
| [2. Where the agent sits: contact centers, service desks, and the systems that were there first](ch02/README.md) | `seat_lab.py` |
| [3. Voice design](ch03/README.md) | `voice_lab.py` |
| [4. Conversation design](ch04/README.md) | `dialogue_lab.py` |
| [5. Which calls first, then SOP to spoken flow](ch05/README.md) | `sop_lab.py` |
| [6. The stack: reference architecture and the first fork](ch06/README.md) | `stack_lab.py` |
| [7. Transport and telephony](ch07/README.md) | `telephony_lab.py` |
| [8. Connecting to the business: every way in](ch08/README.md) | `entry_lab.py` |
| [9. Where the voice lives: web, mobile, workplace apps, and devices](ch09/README.md) | `surface_lab.py` |
| [10. Hearing](ch10/README.md) | `hearing_lab.py` |
| [11. Turn-taking](ch11/README.md) | `turn_lab.py` |
| [12. Speaking](ch12/README.md) | `speaking_lab.py` |
| [13. Speech-to-speech, in depth](ch13/README.md) | `s2s_lab.py` |
| [14. Agent architecture: the turn loop, control, state, and policy](ch14/README.md) | `core_lab.py` |
| [15. Choosing and running the model](ch15/README.md) | `model_lab.py` |
| [16. Instructions and knowledge: what the agent is told and what it knows](ch16/README.md) | `knowledge_lab.py` |
| [17. Tools and actions](ch17/README.md) | `tools_lab.py` |
| [18. Guardrails and agent reliability](ch18/README.md) | `guard_lab.py` |
| [19. Orchestration, and the swap](ch19/README.md) | `orch_lab.py` |
| [20. Systems of record, identity, and memory](ch20/README.md) | `identity_lab.py` |
| [21. Handoff to people: contact-center queues, the service desk, and on-call staff](ch21/README.md) | `handoff_lab.py` |
| [22. Agents on the line: machine callers, delegation, and agent protocols](ch22/README.md) | `agents_lab.py` |
| [23. Trust on the live call: disclosure, card numbers, and threats](ch23/README.md) | `trust_lab.py` |
| [24. Metrics the business will accept: two families, one record, and numbers that last](ch24/README.md) | `metrics_lab.py` |
| [25. Testing voice agents: the pyramid, simulated callers, and rates you can trust](ch25/README.md) | `testing_lab.py` |
| [26. Observability, and the week you improve: traces, the failure taxonomy, and the review](ch26/README.md) | `observe_lab.py` |
| [27. Deploy it: environments, the control plane, and release](ch27/README.md) | `deploy_lab.py` |
| [28. Keep it up: capacity, failure, and recovery](ch28/README.md) | `resilience_lab.py` |
| [29. Keeping it good: maintenance over the years](ch29/README.md) | `care_lab.py` |
| [Interlude A. Run it first: the Appointment Line](interlude-a/README.md) | `appointment_line.py` |
| [Interlude B. Assemble the Service Line slice](interlude-b/README.md) | `service_slice.py` |
| [Appendix M. The scenario format, and a starter catalogue](appendix-m/README.md) | `scenario_lab.py` |

Run `python scripts/run_labs.py ch17` from the companion root, or follow a chapter README.
`python scripts/run_labs.py --check` checks mock and fixture output and runs all tests.

The [delivery contract](../docs/delivery.md) identifies the gaps between the isolated labs
and the integrated application. Leaders' chapters are prose and worksheets;
they do not have a separate executable code track.
