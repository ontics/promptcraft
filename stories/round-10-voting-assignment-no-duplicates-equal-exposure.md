# User story: Round 10 voting assignment — no duplicates, equal exposure, randomized

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [x] Voting screen *(Round 10 only: final player-submission voting assignment)*  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster *(only insofar as status/progression depends on assignment completeness)*  
- [x] Other: **Server-side voting assignment logic** for round 10

**What to do** (one or two sentences in plain language):  
> Replace/fix the **round-10 voting assignment logic** so each voter sees a fair, randomized set of other players’ submissions with no duplicates. The assignment must ensure equal exposure for all submissions, no self-votes, and no repeated submitter within a voter’s ballot.
>  
> Scope is **only** the assignment logic that maps voters to round-10 submissions; do not change unrelated gameplay, UI text, scoring rules, or non-round-10 behavior.

**Requirements** (must all hold):  
- [ ] There are **N players**, each with exactly **one** submission available for round 10 assignment.  
- [ ] Each voter sees exactly **k = 3** other players’ submissions (**k = 2** only if `N` makes 3 impossible; with `N >= 4`, this should be 3).  
- [ ] No voter ever sees their **own** submission.  
- [ ] No voter sees **two submissions from the same player** (no per-voter duplicates).  
- [ ] Every submission is shown to **exactly the same number of voters** (equal exposure, no exceptions).  
- [ ] Assignment is **randomized** each session/run.

**Algorithm to implement** (exact):  
1. Randomly **shuffle** the list of `N` players once at assignment start.  
2. For voter at shuffled index `i`, assign submissions from player indices:  
   - `(i + 1) % N`  
   - `(i + 2) % N`  
   - `(i + 3) % N`  
3. Surface those submissions to the voter as their round-10 ballot.

**Why this algorithm** (acceptance rationale):  
- Guarantees no self-assignment (offsets start at +1).  
- Guarantees no duplicate submitter per voter (distinct offsets).  
- Guarantees equal exposure (each submission appears in exactly 3 voters’ ballots for `N >= 4`).  
- Keeps randomization via initial shuffle.

**Done when** (how we know it’s finished — 1–3 bullets):  
- [ ] For a test run with `N >= 4`, every voter receives exactly 3 distinct submitters, never including self.  
- [ ] Exposure counts are uniform: each submitter appears in exactly 3 ballots (or exactly `k` ballots if fallback `k=2`).  
- [ ] No duplicate-submitter bug appears in round 10; voters do not see the same player twice in their ballot.

**Do not change** (optional — what to leave alone):  
> Only update round-10 assignment construction and how ballots are sourced from that mapping. Do not change scoring formulas, prompt generation, earlier rounds, onboarding, survey flow, admin controls, or copy.

**Depends on** (optional — other stories or data that must exist first):  
> Existing round-10 pipeline where each active player contributes one submission candidate. If missing submissions/disconnections are already handled elsewhere, preserve that behavior and apply this algorithm to the eligible voter/submitter set.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (round-10 assignment function/path that currently maps voters to submitters), any helper used by round-10 ballot generation (e.g. assignment/plan builder). `static/js/game.js` only if payload shape must remain consistent; avoid UI changes.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
