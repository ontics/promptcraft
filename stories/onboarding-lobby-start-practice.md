# User story: Admin “Start Onboarding” — practice prompting before the game

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Lobby  
- [x] Onboarding  
- [x] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster  
- [x] Other: **Static asset for practice target image** (`static/images/` — see below)

**What to do** (one or two sentences in plain language):  
> Add a **blue** button in the **Gamemaster** lobby controls labeled **Start Onboarding**. When clicked, move **non-admin** players into an **Onboarding** experience that **looks like the normal prompting (game) screen**: same layout as the prompting round, with the **timer area showing a fixed `5:00`** (no countdown — stagnant display only), and each player may submit **at most three prompts**. The **target image** for this practice session is the **designated onboarding image** (e.g. Gritty mascot — add the image file to the repo under `static/images/` with a stable URL and wire it as the onboarding target). The **Gamemaster dashboard** should **reflect player activity during onboarding** (e.g. prompt counts / status) the same way it helps during live play. The existing **Start Game** control must **still start the real game** (round 1, timers, scoring flow) unchanged in purpose; onboarding is a separate phase before that.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Lobby shows a blue **Start Onboarding** for the Gamemaster; only the Gamemaster can start onboarding; players leave the lobby UI and see a prompting-style screen with the correct target image, the timer display **stuck at `5:00`** (not running), and the generate action **stops after three submissions** per player (with clear UX when the limit is reached).  
- [ ] Gamemaster view **tracks onboarding activity** (at minimum: per-player practice prompt count or equivalent) without breaking existing lobby/game admin behavior.  
- [ ] **Start Game** still transitions everyone into the normal game from the agreed state (lobby and/or after onboarding, as specified in implementation), with no regression to team assignment, restart, or round flow.

**Do not change** (optional — what to leave alone):  
> Do not change selection, voting, results, or game-over flows unless required to branch a new `onboarding` (or equivalent) session state. Preserve pre-survey and group-assignment behavior outside this story’s scope. Only the area(s) listed above.

**Depends on** (optional — other stories or data that must exist first):  
> None for the story text; implementation needs the **onboarding target image** file checked in (or a documented path). If the app enforces “assign groups before start,” align onboarding start rules with product choice (e.g. same as Start Game or explicitly documented).

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (lobby admin buttons, optional onboarding copy), `static/js/game.js` (screen flow, stagnant `5:00` timer display / no countdown, prompt limit, socket handlers), `static/css/style.css` (blue button if not reusing an existing class), `app.py` (session/game phase, `start_onboarding`-style event, prompt handling separate from scored rounds, admin status payloads), `static/images/onboarding-target.png` (or chosen filename).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
