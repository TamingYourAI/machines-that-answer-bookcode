# The evidence manifest

Every number that goes into a decision travels with its **evidence manifest**: the kind of evidence it is, what produced it, on what data, measured where, how many times, how sure it is, what it leaves out, and when. Chapter 1 of *Machines That Answer* sets the rule that every number carries its evidence class. The manifest is how a team keeps that rule when the numbers start to pile up.

A team writes one for every row of the acceptance record (leaders' volume, Appendix A), every number on the board page (Chapter 24), every benchmark (Chapter 26), and every piece of evidence a release gate reads (Chapter 27). A number without a manifest stays off the page.

*Table 1. The eight fields of an evidence manifest, and the question each answers for a reviewer.*

| Field | What it says | The reviewer's question |
| --- | --- | --- |
| Evidence class | Simulated, recorded replay, live laboratory, or field (Chapter 1) | Did callers produce this, or a model of them? |
| Configuration | What ran: the release manifest's id (Chapter 27), or the lab and its mode, and any setting that differs | Is this the system we are deciding about? |
| Dataset provenance | Which calls, scenarios, or stand-ins, how they were chosen, and what was removed | Whose calls are these, and who is missing? |
| Measurement boundary | Where the clock or the count was taken: the caller's side or the server, the call or the case, and the window | Measured where the caller feels it? |
| Repetitions | How many runs, calls, or seeds, and whether they were independent | How many times did it happen? |
| Uncertainty | The interval, or the bound after clean runs, at a stated confidence (Chapter 25) | How wrong could it be? |
| Limitations | What the number cannot show, and the assumptions under it | What would change the conclusion? |
| Date | When it was measured, and when it expires: a date, or the next release that changes what it measured | Is it still true? |

## Two manifests, filled in

Table 2 fills in two manifests. The first is a lab's simulated result, as every number from the book's labs is. The second is a field result, as the Service Line's team records it for its board page. The Chapter 24 lab reproduces that week on stand-in calls, so the same number appears in the book as simulated evidence too.

*Table 2. Two manifests: Chapter 17's tracked promises, and the Service Line's week 8.*

| Field | Tracked promises (Chapter 17's lab) | Resolution that lasts, pilot week 8 |
| --- | --- | --- |
| The number | 99.8 percent of promises kept by their deadline, against 86.0 percent for fire and forget | 38.0 percent, against the business case's line of 30 and plan of 45 |
| Evidence class | Simulated | Field |
| Configuration | `tools_lab.py`, fixture mode; three send attempts, at 0, 5, and 20 minutes after the call | The release in production that week, by its manifest id; billing and visit flows |
| Dataset provenance | 400 stand-in receipts; a fault schedule generated from seed 17, kept in `fixtures/faults.json` | The 2,900 calls of pilot week 8; machine callers excluded, as Chapter 22 reports them apart |
| Measurement boundary | A promise counts as kept when delivered by the 30-minute deadline the caller heard | Account and task, from hang-up to day 7: the task done in the system of record, and no repeat, reversal, or complaint within seven days (Chapter 24) |
| Repetitions | One run of one seed | One week; each case counted once |
| Uncertainty | One seed: a binomial interval on 400 receipts is several points wide, so a rate needs more seeds before it is quoted | By group, with 95 percent intervals; the lowest, second-language callers, 31.1 percent of 450 (27.0 to 35.5), got its own item |
| Limitations | Send failures are independent at 15 percent, and real gateways fail in bursts; the deadline and retries are the lab's | The cost per resolved case assumes every handover ended resolved, so the saving is provisional (leaders' volume, Chapter 12); the 194 callers who gave up count as unresolved |
| Date | Checked 2026-10-02 on Python 3.12, 3.13, and 3.14; renewed when the lab changes | Final seven days after the week's last call; replaced by the next week's |

The second manifest is why the board saw a provisional saving. Its limitation names the assumption that would change the conclusion, and Chapter 24's lab shows how much: if 290 of the 1,604 handed-over and repeat cases had not ended resolved, a resolved case would cost more than a person's call. The two counts stay apart when both appear: the 38 percent is the agent's own rate on 2,900 calls, and the 2,706 cases behind the cost are every case resolved that week, by the agent or by a person.

## Rules for using manifests

- **The producer writes it, with the number.** A manifest written later is reconstructed from memory, and its limitations shrink.
- **Two numbers are compared only when their manifests agree** on the boundary and the window. A p95 taken at the server and one taken at the caller's side are different numbers (Chapter 1).
- **A number moves up the evidence classes only on new evidence.** Rewording a simulated result as "our testing shows" changes nothing about its class.
- **Expired evidence is unverified.** When a release changes what a number measured, its manifest expires, and the acceptance record's row goes back to unverified until the evidence is renewed.
- **Manifests are kept with the evidence**: beside the run's output, the release's evidence, or the board page they back, in a store whose retention matches the evidence's (Chapter 26).
