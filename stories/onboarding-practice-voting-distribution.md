# User story: Onboarding practice voting — distribute 100 points across three images

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [x] Onboarding (**only** — this entire story is scoped to the onboarding flow)  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster *(only as needed for onboarding, e.g. Round Controls during practice)*  
- [x] Other: **Dedicated onboarding practice “distribute points” UI** (new screen or onboarding-only branch — not the production voting screen)

**What to do** (one or two sentences in plain language):  
> **Scope: onboarding only.** After the existing onboarding practice **prompting** phase, add an onboarding-only **practice voting** step: players distribute **exactly 100 points** across **three** image options, with a **target image** shown alongside (reuse the **same onboarding practice target** as the prompting phase). Under each of the three options, a numeric input collects points; under the target, show **points remaining** (100 minus the sum of the three inputs), updating live as values change. Players must not be able to assign **more than 100** total across the three boxes. For now use **clear placeholders** for the three option images; real assets will be provided later. While players are in **onboarding**, the Gamemaster dashboard should expose **End Round Early** (in Round Controls) to **leave practice prompting** and **open this onboarding practice voting UI** for everyone. **Do not change the real (live round) voting screen or its flow** as part of this story.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] During onboarding **prompting**, the Gamemaster sees **Round Controls** with **End Round Early** available; using it moves **non-admin** players to the **new onboarding-only** practice voting UI (not selection, not the live `#voting-screen` flow).  
- [ ] That UI matches the wireframe intent: heading about distributing points, three option placeholders with inputs, larger **target** using the **onboarding target image**, **points remaining** under the target updating with inputs; total cannot exceed 100; submit (or equivalent) enforces a valid **100-point** total per product choice.  
- [ ] **No changes** to the production voting screen (`#voting-screen` markup, styling, or live-round voting socket/game logic). **Start Game**, live **playing / selection / voting**, pre-survey, and lobby group assignment behave as before aside from minimal onboarding state hooks if required.

**Do not change** (optional — what to leave alone):  
> **The live voting experience is out of scope:** do not edit the real voting screen, shared voting gallery logic for scored rounds, or `skip_voting` / live voting transitions for this story. Do not change selection, results, or game-over flows for live play. Implement practice distribution as **onboarding-only** (separate DOM section or screen, onboarding-gated JS, onboarding handlers in `app.py`). Only the onboarding + admin-onboarding areas described above.

**Depends on** (optional — other stories or data that must exist first):  
> **Onboarding practice prompting** (e.g. Start Onboarding, onboarding target image path) must already exist so the same target can be shown on this screen.

**Files likely involved** (optional — helps the AI and you focus):  
> Prefer **new** onboarding-specific markup (e.g. a dedicated screen `div` in `templates/index.html`) and **new** CSS classes in `static/css/style.css` — **not** the existing voting-screen block. `static/js/game.js`: onboarding phase transitions, input validation, socket events **without** altering live voting handlers. `app.py`: onboarding sub-phase or status, admin **End Round Early** behavior **only while `status` is onboarding**, optional server validation for submitted practice points. Placeholder assets under `static/images/` only when you add real images later.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
