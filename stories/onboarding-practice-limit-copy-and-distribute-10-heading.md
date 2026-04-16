# User story: Onboarding practice limit copy + “Distribute 10 points” voting heading

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Onboarding *(practice prompting — prompt limit reached state)*  
- [ ] Lobby  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [x] Voting screen *(allocation / point distribution: `#voting-screen` and `#onboarding-practice-voting-screen`)*  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [ ] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> **Onboarding practice prompting:** When the player hits the practice prompt cap, the user-facing message must **not** mention a numeric cap or parenthetical like “(3 prompts)”. It should only communicate that they have **reached the practice limit** (wording can be short and neutral, e.g. “Practice limit reached.” — exact punctuation is flexible as long as the number and “prompts” parenthetical are gone).  
> **Voting / point distribution (onboarding practice + live allocation):** Where the instruction line currently begins with **“Distribute points”** (e.g. “Distribute points among the following images”), change it so it begins with **“Distribute 10 points”** (e.g. “Distribute 10 points among the following images”). Apply this consistently for **live** allocation voting on `#voting-screen` and for **onboarding** practice voting on `#onboarding-practice-voting-screen` if any copy there still says “Distribute points” without “10” (today onboarding practice HTML may already include “10”; align any JS-set strings so both flows match).

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] At the practice prompt limit, **server-originated** and **client-shown** messages do **not** include “3”, “(3 prompts)”, or a dynamic `"(${max} prompts)"` style parenthetical; the user only sees that the **practice limit** was reached.  
- [ ] On `#voting-screen`, `#allocation-instructions` (and any code that overwrites it, e.g. when `allocation_vote_started` runs) reads **“Distribute 10 points…”** not **“Distribute points…”**.  
- [ ] On `#onboarding-practice-voting-screen`, the same **“Distribute 10 points…”** opening applies wherever the instruction line is defined or updated; no regression to the old wording.

**Do not change** (optional — what to leave alone):  
> Do not change the **actual** practice prompt cap (still 3 unless a separate story changes it). Do not change round counts, point rules (still 10 total to allocate), or unrelated onboarding/voting behavior. Only the **copy** above.

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (practice prompt limit `emit('error', {'message': ...})` for onboarding), `static/js/game.js` (`applyOnboardingGenerateState` / `#onboarding-limit-hint`; `allocation_vote_started` instruction text for `#allocation-instructions`), `templates/index.html` (default text for `#allocation-instructions` and `#ob-practice-instructions` if adjusted for parity).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
