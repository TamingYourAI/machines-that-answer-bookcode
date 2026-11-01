# The capability framework, traced

The capability framework is the acceptance specification of *Machines That Answer* (the book's Chapter 1). This document traces each of its 86 checkpoints to the book's chapters that build it and to the lab tests in this repository that show it working. The leaders' volume writes each checkpoint in full, with what good looks like and how to evaluate it, and keeps every result in its acceptance record (its Appendix A).

Three things govern the table:

- **Built in** lists every chapter that builds part of the checkpoint. A number in bold is a chapter whose box, *Checkpoints this chapter satisfies*, names it; the others build a part the box leaves to a later chapter.
- **A lab test is simulated evidence.** It shows that a mechanism works on stand-ins, and says nothing about a rate on a business's own line. Each leaders' checkpoint says what live laboratory or field evidence to add, and a release-blocking one needs it before any launch.
- **Ten checkpoints rest on documents**, such as a business case, a roles chart, or a contract, so no lab can prove them, and the table names the document. Two of them are release-blocking: TRU-1 passes on the recording rules and on test calls from each place, and TRU-8 on the notice to employees and the workplace agreement.

Each test is named by the words of its function's name: "operation id prevents duplicates" is `test_operation_id_prevents_duplicates` in [`chapters/ch17/test_tools_lab.py`](../chapters/ch17/test_tools_lab.py). Every test named here passes in the labs' fixture mode on Python 3.12, 3.13, and 3.14 (checked 2026-10-02).

*Table 1. The 86 checkpoints, the chapters that build them, and the tests that prove them. [RB] marks the fourteen release-blocking ones.*

| Checkpoint | Built in | Proved in the labs by |
| --- | --- | --- |
| FIT-1 A first use case, graded, with a do-not-automate list | 1, **5** | Ch. 5: risk gates the highest score; the counter atlas is never ranked in. |
| FIT-2 A business case with one number to defend | 24 | The business-case one-pager (leaders' Chapter 4). Ch. 24: week 8 holds every line. |
| FIT-3 An owner with the authority to say no | 5, 27 | No lab: the roles chart, with the owner's right to stop a release (Chapter 27). |
| FIT-4 The calls that stay with people, written down | **5**, 21 | Ch. 5: the counter atlas is never ranked in; the safety step escalates to a person. |
| ARC-1 The architecture known and explained | **1**, **6**, **13** | Ch. 1: boundaries nest on every turn. Ch. 6: every layer has a contract. Ch. 13: fixed steps are the same on both roads. |
| ARC-2 Each layer's portability and cost of leaving | **6**, **13**, **19** | Ch. 6: only the conforming adapter passes. Ch. 13: fixed steps are the same on both roads. |
| ARC-3 Speed measured on real lines, as percentiles | **1**, **7**, **15**, **19**, 24, **28** | Ch. 1: the mean hides the tail; the tuned loop meets the wall at p95. Ch. 15: load stretches the tail more than the middle. Ch. 24: the server meets the wall while the caller does not. |
| ARC-4 Capacity for the peak, with a plan for the spike | **28** | Ch. 28: littles law gives 135 calls in progress; the desk binds at the storm peak. |
| ARC-5 Where each layer runs and the data goes | **6**, 23, **27** | The ecosystem map, by country (Chapter 6). Ch. 27: endpoints keys and region may differ. |
| SRF-1 Surfaces chosen by where people already are | 9 | No lab: the surface map (leaders' Chapter 3). |
| SRF-2 One agent behind every surface | **9**, **16** | Ch. 9: typed and spoken reach the same turn; the card shows what the voice says. |
| SRF-3 [RB] App identity from the sign-in, and no credential in the app | **9** | Ch. 9: the scan finds the prototype key only; a late token is refused; edited claims break the signature. |
| SRF-4 On a screen, the state shown, and tap or talk | 4, **9** | Ch. 9: every event has a visible state; a card with an unspoken fact is caught; a tap and a yes book once. |
| SRF-5 Another way through for people who cannot talk or hear | 4, **9** | Ch. 9: typed and spoken reach the same turn. |
| CAL-1 Callers listened to before anything was designed | **4**, 5 | The listening sessions and the ranked call reasons (Chapters 4 and 5). Ch. 5: practice is inserted where the desk does it. |
| CAL-2 A person reachable, or a truthful time for a callback | **4**, **21**, **28** | Ch. 4: a person on the second request at most. Ch. 21: the stated wait is right; every callback is kept. |
| CAL-3 Accessible to slow, different, and relay callers | 3, **4**, **10**, **11**, **21** | Ch. 11: two thresholds wait for the second half; a relay caller is never ended for silence. |
| CAL-4 Performance by accent, dialect, and age, with responses | **10**, **15**, 24 | Ch. 10: small samples give wide intervals. Ch. 15: a faster model that answers worse in one language is stopped. Ch. 24: a small group with a low number is a question not a pass. |
| CAL-5 Promises made on the call kept after it | **14**, **17**, 21 | Ch. 14: an approval outlives the call. Ch. 21: every callback is kept. |
| VOX-1 A voice brief, approved by the brand's owner | **3** | Ch. 3: service line brief is complete. |
| VOX-2 [RB] Says it is automated, and answers "are you a person?" truthfully | **3**, **13**, 23 | Ch. 3: disclosure must come first. |
| VOX-3 Courteous with interruptions and silence | **4**, **11** | Ch. 4: silence ends with a text not a loop. Ch. 11: a backchannel is not a barge in; a barge in stops within the voice window. |
| VOX-4 Confirms what matters as the risk requires | **4**, 17 | Ch. 4: identifiers are read back in groups; low risk needs no read back. Ch. 10: sound alike amounts are spelled back. |
| VOX-5 Recovers from misunderstanding without loops | **4**, **18** | Ch. 4: v1 loops on a misheard number and v2 recovers. Ch. 18: two refusals then a person. |
| VOX-6 Every language designed, not translated | **3**, 4, **10**, **12**, **16** | Ch. 12: german puts the units first; each locale says the time its own way. |
| VOX-7 Names pronounced correctly, from a maintained list | **3**, **12**, **29** | Ch. 3: codes spell letters. Ch. 12: one entry three forms. |
| INT-1 Knows who is calling, as surely as the task needs | **20** | Ch. 20: a number finds candidates not a caller; a number match proves nothing. |
| INT-2 Reads and writes the systems of record, every action traced | **17**, **20** | Ch. 17: operation id prevents duplicates. Ch. 20: the verified account is read. |
| INT-3 A person takes over without the caller repeating | **8**, **21** | Ch. 8: attached data survives both transfers. Ch. 21: a fresh pin is carried; the next action can need a step up. |
| INT-4 Callback promises made honestly and kept | **17**, **21**, **22**, **28** | Ch. 21: every callback is kept. Ch. 22: a silent partner still gets the passenger a person in time. |
| INT-5 Respects the contact center that was there first | **2**, **8**, **21** | Ch. 2: a second recording is caught; every screen pop field is required. |
| INT-6 How it connects, and what each path gives up | **2**, **8** | Ch. 2: overlay gives up interruptions and audio. Ch. 8: claims without an adapter are untested. |
| INT-7 [RB] No more authority than the verified caller | **16**, **17**, **20**, **22** | Ch. 20: another account on the same number is refused. Ch. 22: an assistant without a delegation gets no account data. Interlude B: it refuses another account. |
| INT-8 Another agent recognized, held to its proof, offered a door | **8**, **22** | Ch. 22: a partner agent is sent to the structured door; a synthetic sounding voice is still a person. |
| JDG-1 Answers from approved knowledge with an owner and an end date | **16**, **29** | Ch. 16: an item without an owner is never spoken; an ended policy is not spoken. Ch. 29: loud expiry pulls the ended waiver. |
| JDG-2 [RB] Never says it did what it did not | **17**, **18** | Ch. 17: reconciliation speaks only the truth. Ch. 18: the commitment check stops the words. Interlude B: one id per yes never says booked falsely. |
| JDG-3 [RB] Anything that cannot be undone confirmed aloud first | **17**, 20 | Ch. 17: a yes does not cover unheard terms. Ch. 25: a yes that never heard the fee is refused. |
| JDG-4 [RB] Policy decided by rules, never by the model's guess | **13**, **14**, **16** | Ch. 13: the waiver follows memo 114. Ch. 14: the rules come before the rung. Ch. 16: the policy memo outranks the web page. |
| JDG-5 Stays in scope, and declines advice it must not give | **5**, **18** | Ch. 5: the safety step escalates to a person. Interlude A: unknown question is not answered from the model. |
| JDG-6 Any decision explainable afterwards | **14**, **18**, **26** | Ch. 18: the record explains the turn on its own. Ch. 26: every flagged call named a known layer. |
| JDG-7 [RB] Nothing unheard is agreed; one yes, one operation | 11, **14**, **17**, **19**, **22** | Ch. 14: a term not heard is not agreed. Ch. 19: marks before the clear agree with chapter 8. Interlude B: a yes covers only what was heard. |
| JDG-8 [RB] One durable record per action, and unknown outcomes reconciled | **17**, **28** | Ch. 17: operation id prevents duplicates; timeout is not failure. Ch. 28: the journal and the fence book nothing twice. Interlude B: a restart reads the journal and the outcome back. |
| TRU-1 [RB] Consent and recording rules for every caller's location | **7**, **23** | No lab: the recording rules kept as data, one record per jurisdiction (Chapter 23), and the first seconds of test calls from each place. |
| TRU-2 [RB] Card numbers on an isolated path, proven first | **13**, **23** | Ch. 23: the isolated path reaches only the processor; a fork that says paused and keeps receiving blocks it. Interlude B: a fork still receiving keeps the path shut. |
| TRU-3 A written threat model | **7**, **18**, 20, **23** | Ch. 7: emergency numbers are never dialed. Ch. 20: an edited statement is refused. Ch. 23: one number probing accounts fires on the fourth. |
| TRU-4 [RB] Vulnerable callers and emergencies handed to a person | **21**, **23** | Ch. 5: the safety step escalates to a person. Interlude A: person gets a whisper and nothing is booked. |
| TRU-5 Outbound calls within consent, hours, opt-out, and limits | **5**, **7**, **23** | Ch. 5: nine pm is outside the window. Ch. 7: the hourly limit holds; an unregistered number is filtered. |
| TRU-6 Recordings and transcripts deleted on schedule | **10**, **23**, **26** | Ch. 10: accounts and emails are redacted. Ch. 23: the span redactor leaves no card or code digits. Ch. 26: the scenario carries no personal data. |
| TRU-7 Callers' data used only as agreed | **15**, **20**, **23** | The providers' terms, with logging and training off in writing (Chapter 23). Ch. 13: the hybrid sends the provider nothing. |
| TRU-8 [RB] Employees told how their calls are recorded and used | **23** | No lab: the notice to employees and the workplace agreement (leaders' Chapters 9 and 13). |
| PRT-1 Evaluated on your own calls | 1, 25, **26** | Ch. 1: demo passes and call fails the wall. Ch. 15: the published figure flatters every model. |
| PRT-2 Service levels written down | **19**, 27, **28** | The signed service levels (leaders' Chapter 10). Ch. 19: the hold is invisible to the vendor dashboard. |
| PRT-3 Your data owned, and the export tested | **19**, 27 | No lab: an export loaded into a second system, from the lock-in ledger (Chapter 19). |
| PRT-4 A pilot with exit criteria in both directions | 5, 25 | No lab: the pilot's exit criteria, in both directions (leaders' Chapter 10). |
| TST-1 A scenario library built from real calls | 5, **25** | Ch. 25: the state test catches the false booked. Ch. 26: the new scenario fails before the fix and passes after. |
| TST-2 Simulated callers with noise, accents, and interruptions | 10, 11, **25** | Ch. 25: the polite caller passes the version that breaks; the realistic caller exposes it. |
| TST-3 End to end on real phone lines | 7, 8, 23, **25** | Test calls on the business's own lines (Chapter 25). Ch. 7: the phone path removes what is above 4 khz. |
| TST-4 At peak load, and with parts failing | 15, **19**, **25**, 28 | Ch. 15: a rate limit sends turns down the ladder. Ch. 28: recognizer mid call loses no words within the buffer. |
| TST-5 By people trying to make it misbehave | **18**, 20, 23, **25** | Ch. 18: a false exception is blocked; paraphrases leak through patterns but not structure. |
| TST-6 [RB] Go-live criteria written first, and signed | 5, **25** | The go-live sheet, written before testing and signed (leaders' Chapter 11). Ch. 25: the runs a claim needs. |
| TST-7 Real callers met it in shadow or a limited pilot first | **18**, **25**, **27** | Ch. 18: replay finds the one regression and writes nothing. Ch. 27: at the tool layer no write leaves. |
| MEA-1 Speech quality and business results never mixed | **1**, **24** | Ch. 24: the metrics record gives all three numbers in order. |
| MEA-2 Containment never reported alone | **1**, 17, **24** | Ch. 1: containment is not task completion. Ch. 24: a person finishing a task is never the agents completion. |
| MEA-3 Every number split by language, segment, and surface | 10, **24**, **26** | Ch. 24: the second language sits wholly below the week; the week rose while every flow fell. |
| MEA-4 Five board numbers that are hard to game | **24**, 26 | Ch. 24: week 8 holds every line; machine callers are in no number. |
| MEA-5 Resolution counted only when it lasts | 1, 17, **24** | Ch. 24: a repeat call is part of the first calls cost. Ch. 29: resolution that lasts moves a week later. |
| LCH-1 [RB] A phased launch, and a switch that stops it in seconds | 2, 25, **27**, **28** | Ch. 9: the kill switch reaches every version. Ch. 27: the emergency stop refuses the action at once. Interlude A: kill switch goes straight to the owner. |
| LCH-2 The desk helped design it, trained on it, and hears first | 5, 21, 26 | The desk's design partners in the weekly review (Chapter 26). Ch. 5: practice is inserted where the desk does it. |
| LCH-3 Staffing follows the agent's results | 21, 24 | The staffing plan (leaders' Chapter 13). Ch. 28: the desk binds at the storm peak. |
| LCH-4 Customers told honestly what the agent is | 3, 23 | No lab: the customer notice (leaders' Chapter 13). |
| CAR-1 Every change a tested, versioned release | **15**, **27**, **29** | Ch. 27: a changed part changes the id; stale evidence does not count. |
| CAR-2 A care calendar with named owners | **29** | Ch. 29: five tasks are overdue; the failover drill is the most overdue. |
| CAR-3 Drift found by alerts, before complaints | **26**, **29** | Ch. 29: the carrier change alerts on the second day; the fixed limit catches the creep. |
| CAR-4 Provider changes announced, retested, and reversible | **12**, **15**, **19**, **27**, **29** | Ch. 12: the update sounds better and is heard worse. Ch. 29: a recognizer change triggers the entity scenarios. |
| CAR-5 Knowledge changed within hours on a bad day | **16**, **29** | Ch. 16: the day after says it ended. Ch. 29: loud expiry pulls the ended waiver. |
| CAR-6 Every production failure a test within a week | 25, **26** | Ch. 26: the new scenario fails before the fix and passes after; one promotion took longer than a week. |
| CAR-7 Care with a budget line of its own | **29** | The care budget (leaders' Chapter 14). Ch. 29: two parts rose more than a tenth. |
| GOV-1 An operating model: who decides what | **27** | No lab: the roles chart and the release's named roles (Chapter 27). |
| GOV-2 A risk register and an incident plan, rehearsed | **28** | The risk register and the incident plan's exercises (leaders' Chapter 15). Ch. 28: the empty transcript alarm fires in the first minute. |
| GOV-3 An audit trail that can reproduce any call | **26** | Ch. 18: the record explains the turn on its own. Ch. 27: the same parts in another order give the same id. |
| GOV-4 Liability, insurance, and customer terms reviewed | 18, 23 | No lab: the reviewed customer terms and insurance (leaders' Chapter 15). |
| GOV-5 Shared agents and tools owned, versioned, and revocable | **14**, **17**, **27** | The inventory of agents and shared tools (leaders' Chapters 10 and 15). Ch. 14: a tool outside the flow is refused. |
| VAL-1 Total cost of ownership, hidden costs included | **15**, 24, 29 | Ch. 15: the model is a small share of the business case. Ch. 24: an unresolved handover adds its cost and nothing to the count. |
| VAL-2 The business case checked against reality on a schedule | 24 | Ch. 24: the cost per resolved case is above the plan. |
| VAL-3 What the calls reveal reaches someone who acts | 24, 26 | The weekly review's decisions (Chapter 26). Ch. 26: every flagged call named a known layer. |
| VAL-4 A roadmap with gates between stages | 27 | No lab: the roadmap and its gates (leaders' Chapter 16). |

The interludes exercise checkpoints without proving them, on simulated evidence only. Interlude B's four acceptance scenarios are the release gate for JDG-7, JDG-8, INT-7, and TRU-2, and the book's Appendix M gives them in the scenario format.
